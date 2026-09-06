#!/usr/bin/env python3
"""Offline SwinIR-S x2 experiment; never imports results into the application."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
import warnings


NETWORK_SHA256 = "9e143898679ebeebc5d2fc94ad1b89c38aa4a4d43da4e0fcba0f93e476994913"
WEIGHTS_SHA256 = "193b229909ca89cd8b55de9c9e7fce146ae759d59dfcd78d8feb9dd1d6fa0fd7"
ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_network(path):
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != NETWORK_SHA256:
        raise ValueError("candidate_digest_mismatch")
    namespace = {"__name__": "pinned_swinir"}
    # Execute the checked bytes, never a neighboring cached .pyc.
    exec(compile(source, "<pinned_swinir>", "exec"), namespace)
    return namespace["SwinIR"]


def deny_network(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError("network_disabled")


def predict(model, source, tile):
    # Tiling adapted from SwinIR main_test_swinir.py, Copyright 2021 SwinIR Authors.
    # Apache-2.0: licenses/SwinIR-Apache-2.0.txt. Here counts use one channel,
    # sizes may be non-window-aligned, and inputs/outputs remain experiment-local.
    if not tile:
        return model(source)
    height, width = source.shape[-2:]
    tile = min(tile, height, width) // 8 * 8
    if tile <= 16 or tile % 8:
        raise ValueError("invalid_tile")
    rows = list(range(0, height - tile, tile - 16)) + [height - tile]
    columns = list(range(0, width - tile, tile - 16)) + [width - tile]
    output = source.new_zeros(1, 3, height * 2, width * 2)
    counts = source.new_zeros(1, 1, height * 2, width * 2)
    for y in rows:
        for x in columns:
            patch = model(source[..., y:y + tile, x:x + tile])
            output[..., y * 2:(y + tile) * 2, x * 2:(x + tile) * 2] += patch
            counts[..., y * 2:(y + tile) * 2, x * 2:(x + tile) * 2] += 1
    return output / counts


def run(args):
    # These guards cover Python networking, not a native network sandbox.
    for name in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        os.environ[name] = "1"
    sys.addaudithook(deny_network)
    warnings.filterwarnings("ignore", category=FutureWarning, module=r"timm\..*")
    warnings.filterwarnings("ignore", message="torch.meshgrid:.*")
    import numpy as np
    from PIL import Image
    import torch

    if args.output.resolve().is_relative_to(ROOT):
        raise ValueError("output_must_be_outside_checkout")
    if digest(args.weights) != WEIGHTS_SHA256:
        raise ValueError("candidate_digest_mismatch")
    paths = sorted(args.reference.glob("*.png"))
    if not paths or not 1 <= len(paths) <= 240 or not 1 <= args.threads <= 32:
        raise ValueError("invalid_probe_size")
    if args.tile and (args.tile <= 16 or args.tile % 8):
        raise ValueError("invalid_tile")
    if args.inputs and {p.name for p in args.inputs.glob("*.png")} != {p.name for p in paths}:
        raise ValueError("unpaired_frames")
    before = {p: digest(p) for p in paths}
    if args.inputs:
        before.update({args.inputs / p.name: digest(args.inputs / p.name) for p in paths})
    torch.set_num_threads(args.threads)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_unavailable")
    network = load_network(args.network)
    model = network(upscale=2, in_chans=3, img_size=64, window_size=8,
                          img_range=1., depths=[6, 6, 6, 6], embed_dim=60,
                          num_heads=[6, 6, 6, 6], mlp_ratio=2,
                          upsampler="pixelshuffledirect", resi_connection="1conv")
    model.load_state_dict(torch.load(args.weights, map_location="cpu", weights_only=True)["params"], strict=True)
    model.eval().to(device)
    args.output.mkdir(exist_ok=False)
    names = ("reference", "input", "bicubic", "lanczos", "swinir", "blend50")
    for name in names:
        (args.output / name).mkdir()
    errors = {name: [] for name in names[2:]}
    temporal = {name: [] for name in names[2:]}
    previous = {}
    elapsed = []
    shape = None
    started = time.perf_counter()

    def synchronize():
        if device.type == "cuda":
            torch.cuda.synchronize()

    with torch.inference_mode():
        for index, path in enumerate(paths):
            with Image.open(path) as image:
                reference = image.convert("RGB")
            width, height = reference.size
            if min(width, height) < 64 or max(width, height) > 4096 or width % 2 or height % 2:
                raise ValueError("reference_dimensions_must_be_even")
            if shape is not None and shape != reference.size:
                raise ValueError("varying_frame_dimensions")
            shape = reference.size
            if args.inputs:
                with Image.open(args.inputs / path.name) as image:
                    low = image.convert("RGB")
                if low.size != (width // 2, height // 2):
                    raise ValueError("invalid_input_scale")
            else:
                low = reference.resize((width // 2, height // 2), Image.Resampling.BICUBIC)
            source = torch.from_numpy(np.array(low).astype(np.float32) / 255.).permute(2, 0, 1).unsqueeze(0).to(device)
            if index == 0:
                synchronize()
                warm_started = time.perf_counter()
                warm = predict(model, source, args.tile)
                synchronize()
                warmup_seconds = time.perf_counter() - warm_started
                del warm
                if device.type == "cuda":
                    torch.cuda.reset_peak_memory_stats()
            synchronize()
            tick = time.perf_counter()
            prediction = predict(model, source, args.tile)
            synchronize()
            elapsed.append(time.perf_counter() - tick)
            if not torch.isfinite(prediction).all().item():
                raise ValueError("nonfinite_output")
            pixels = prediction.squeeze(0).clamp(0, 1).permute(1, 2, 0).cpu().numpy()
            enhanced = Image.fromarray(np.round(pixels * 255.).astype(np.uint8))
            # Do not retain a previous GPU result during the next timed inference.
            del prediction, source
            cubic = low.resize(reference.size, Image.Resampling.BICUBIC)
            images = dict(reference=reference, input=low, bicubic=cubic,
                          lanczos=low.resize(reference.size, Image.Resampling.LANCZOS),
                          swinir=enhanced, blend50=Image.blend(cubic, enhanced, .5))
            truth = np.asarray(reference, dtype=np.float32)
            for name, image in images.items():
                image.save(args.output / name / f"{index:04d}.png")
                if name in errors:
                    residual = np.asarray(image, dtype=np.float32) - truth
                    mse = float(np.mean(residual ** 2))
                    errors[name].append(None if mse == 0 else float(10 * np.log10(255. ** 2 / mse)))
                    if name in previous:
                        temporal[name].append(float(np.mean(np.abs(residual - previous[name]))))
                    previous[name] = residual
    unchanged = all(digest(path) == value for path, value in before.items())
    if not unchanged:
        raise RuntimeError("inputs_changed")
    report = {
        "candidate": "SwinIR-S lightweight x2", "network_sha256": NETWORK_SHA256,
        "weights_sha256": WEIGHTS_SHA256, "system": platform.system(),
        "python": platform.python_version(), "device": args.device, "precision": "float32",
        "device_name": torch.cuda.get_device_name() if device.type == "cuda" else "CPU",
        "torch_cuda": torch.version.cuda, "threads": args.threads, "tile": args.tile,
        "tile_overlap": 16 if args.tile else 0,
        "packages": {p: importlib.metadata.version(p) for p in ("torch", "torchvision", "timm", "Pillow", "numpy")},
        "frames": len(paths), "reference_size": shape, "input_size": [v // 2 for v in shape],
        "input_mode": "paired_local_frames" if args.inputs else "Pillow_RGB_bicubic_half",
        "input_bytes_unchanged": unchanged, "warmup_seconds": warmup_seconds,
        "inference_seconds": elapsed, "inference_fps": len(elapsed) / sum(elapsed),
        "wall_seconds_including_warmup_and_png_io": time.perf_counter() - started,
        "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device.type == "cuda" else None,
        "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved() if device.type == "cuda" else None,
        "rgb_psnr_db_per_frame": errors,
        "temporal_residual_mae_8bit_per_transition": temporal,
        "limits": "Synthetic degradation, full-frame RGB PSNR; temporal residual is not motion-compensated or a flicker verdict. No browser, target-fit or human quality acceptance.",
    }
    report_path = args.output / "report.partial.json"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    report_path.replace(args.output / "report.json")
    print(json.dumps({"status": "completed", "frames": len(paths), "inference_fps": report["inference_fps"]}))


def main():
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            self.exit(2, "invalid_arguments\n")

    parser = Parser(description=__doc__)
    for name in ("network", "weights", "reference", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--tile", type=int, default=128, help="Input tile with overlap 16; 0 means whole frame.")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        # Fixed diagnostics only; partial output has no report.json and is never adopted.
        code = str(error) if str(error) in {"cuda_unavailable", "inputs_changed", "candidate_digest_mismatch", "output_must_be_outside_checkout", "network_disabled", "nonfinite_output"} else "enhancement_probe_failed"
        if type(error).__name__ == "OutOfMemoryError":
            code = "cuda_out_of_memory"
        print(code, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
