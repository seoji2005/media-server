# Conservative enhancement feasibility

An experiment, not an adopted preset or completed enhancement feature. The application
still plays the original; these outputs never enter its library, jobs or versions.
Windows/RTX 4070 SUPER 12 GB and human moving-video acceptance remain required.

## Candidate and permitted inputs

One candidate: **SwinIR-S lightweight x2**, official `v0.0` asset
`002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth` (17,147,989 bytes). The
[paper's loss description](https://arxiv.org/html/2108.10257v1#S3.SS1.SSS4)
uses pixel L1 loss for lightweight SR; the separate real-world/GAN branch is not used.
This does not guarantee faithful texture or temporal stability. No face restoration,
diffusion, frame interpolation or generated video is involved.

[Official code](https://github.com/JingyunLiang/SwinIR/tree/6545850fbf8df298df73d81f3e8cba638787c8bd)
is pinned at `6545850fbf8df298df73d81f3e8cba638787c8bd`. The project declares
[Apache-2.0](https://github.com/JingyunLiang/SwinIR/blob/6545850fbf8df298df73d81f3e8cba638787c8bd/LICENSE);
retain upstream and dependency notices if later distributing it. No weights or upstream
network code are vendored here, and no gated-license prompt was accepted. The probe's
tile traversal/overlap averaging adapts the upstream test routine; its copyright and
[license copy](../licenses/SwinIR-Apache-2.0.txt) are retained. The probe verifies:

| File | SHA-256 of retrieved bytes |
| --- | --- |
| `models/network_swinir.py` | `9e143898679ebeebc5d2fc94ad1b89c38aa4a4d43da4e0fcba0f93e476994913` |
| Official x2 asset | `193b229909ca89cd8b55de9c9e7fce146ae759d59dfcd78d8feb9dd1d6fa0fd7` |

These identify the downloaded artifacts, not an independently signed publisher digest.

Public footage: **Tears of Steel — (CC) Blender Foundation | mango.blender.org**,
[CC BY 3.0 attribution](https://media.xiph.org/tearsofsteel/README.txt), from the
[1080p WebM mirror](https://media.xiph.org/tearsofsteel/tears_of_steel_1080p.webm).
It combines live action and CG. Only short local excerpts were decoded: dialogue at
25–27 s, close-up at 320–322 s, 1920×800 / 24 fps. The initial 45–47 s title-card/CG
pilot was inspected and excluded from live-action evaluation. Crops are deliberately
small: dialogue `768:512:416:48`, close-up `768:512:768:128` (width:height:x:y).
The dialogue includes a CG prosthetic; it cannot validate natural hand anatomy there.

The reference is already lossy WebM, not a camera master. Inputs halve each crop to
384×256 with Pillow RGB bicubic. A separate compressed case adds H.264 CRF 28,
medium preset, yuv420p at 24 fps. Neither is a broad real-world degradation benchmark
or the paper's exact MATLAB benchmark pipeline.

## Reproduce and measure the target

Use an empty directory **outside the checkout** for all inputs/models/results and a
separate Python 3.12 environment. These are developer probe dependencies, not new app
requirements. The CPU run used Torch 2.8.0+cpu / TorchVision 0.23.0+cpu, timm 1.0.20,
NumPy 2.5.2, Pillow 12.3.0 and FFmpeg 6.1.1. `pip check` passed.

For the target, install matching Torch/TorchVision from the
[official CUDA 12.8 wheel index](https://pytorch.org/get-started/previous-versions/#v280)
in that separate environment; the driver and actual CUDA availability still need checking:

```powershell
python -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install timm==1.0.20 numpy==2.5.2 Pillow==12.3.0
python -m pip check
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv
```

Fetch `models/network_swinir.py` at the pinned official commit and the named official
release asset to that external directory. The CLI does no fetching. Decode a permitted
local clip into up to 240 **consecutive, zero-padded PNGs**; for example, from an
already-local copy (create `D:\MediaClarityProbe\reference` first):

```powershell
ffmpeg -v error -nostdin -ss 320 -i "D:\Samples\tears_of_steel_1080p.webm" -vf "crop=768:512:768:128" -frames:v 48 -an -n "D:\MediaClarityProbe\reference\%04d.png"
python scripts/probe_enhancement.py --network "D:\MediaClarityProbe\network_swinir.py" --weights "D:\MediaClarityProbe\swinir-x2.pth" --reference "D:\MediaClarityProbe\reference" --output "D:\MediaClarityProbe\result" --device cuda --tile 128
```

`--device cpu --threads 4` selects the observed CPU path. An optional `--inputs` directory
provides corresponding half-size PNGs with exactly matching names, useful after local
compression/decode. All reference frames must have the same even dimensions, each
side 64–4096 pixels. For a full-size target measurement, decode without the crop
and use a fresh output directory. A 1920×1080 reference tests 960×540→1920×1080;
3840×2160 tests 1920×1080→3840×2160. Neither was executed here.

The probe loads checked source bytes directly and uses `torch.load(weights_only=True)`.
It reads inputs, creates a new output directory, checks their bytes again, and writes
reference/input/bicubic/Lanczos/model/50%-blend PNGs plus `report.json` on completion.
Existing output is refused. Failure leaves partial diagnostics without a success report;
use a new directory when retrying. Paths, titles and frame content are absent from
console output. Python socket calls are denied and HF offline/telemetry opt-outs set;
this is not native network tracing or a sandbox against arbitrary packages.

Inference is float32, one frame at a time, 128-pixel input tiles with 16-pixel overlap
and averaged overlaps; `--tile 0` measures a whole frame. The report separates warm-up,
synchronized inference timing, and PNG-loop wall time (the latter excludes startup/model
loading). CUDA allocated/reserved peaks describe this process, not total GPU use or
simultaneous ASR/translation capacity. Record idle/peak total GPU use separately on the
target. OOM exits without publishing a result; original playback remains independent.

Metrics compare saved 8-bit RGB output to the reference, with no border crop. PSNR is
reported per frame. Temporal residual is mean absolute change of `(output-reference)`
between consecutive frames in 8-bit units. It is not motion compensated and is **not a
flicker verdict**. Inspect actual motion and tile seams; higher PSNR cannot accept faces,
identity, texture or human viewing quality.

## Observations and next decision

Actual runs on 2026-09-06: Linux/Python 3.12.13, exposed AMD EPYC 9V74 CPU,
four Torch threads, no CUDA. Three serial runs completed **72 frames plus three warm-ups**,
all finite. Clean close-up used 48 consecutive frames (2 s); compressed close-up and
clean dialogue used their first 12 frames each (0.5 s). Each output was 768×512.

Mean per-frame RGB PSNR, dB (higher means closer pixels under this narrow comparison):

| Case | Frames | Bicubic | Lanczos | SwinIR | 50% blend |
| --- | ---: | ---: | ---: | ---: | ---: |
| Close-up, bicubic half-size | 48 | 44.036 | 44.589 | 46.278 | 45.509 |
| Same close-up, additional CRF 28 | 12 | 35.461 | 35.445 | 35.319 | 35.359 |
| Dialogue, bicubic half-size | 12 | 37.138 | 37.936 | 40.457 | 39.334 |

Inference was **0.0866–0.0882 frames/s**, roughly 11.3–11.6 s per small frame.
PNG-loop wall times, including warm-up, were 594.53 s, 154.93 s and 159.27 s respectively.
These are individual shared-cloud CPU observations, not controlled performance benchmarks.
No full-frame/movie or GPU extrapolation is made. Temporal residual MAE for bicubic/model
was 1.277/1.075, 2.923/2.988 and 2.192/1.740 respectively; the compressed case also regressed
on this limited signal. It does not establish visible flicker or its absence.

Inspected static comparisons: close-up frames 0/23/47, compressed frames 0/11, dialogue
frame 11 face/hand crops. Clean-input eye/mouth and clothing edges are clearer; fine skin
texture remains lost. Compressed eye/nose detail remains damaged and its edges are more
pronounced. A 48-frame/24-fps side-by-side H.264 video was encoded and probed, but **not
watched in a real browser here**. No claim of human motion, identity or seamless-tiling
acceptance follows from sampled images or metrics.

**Decision: do not adopt this candidate as a general video preset.** Its clean synthetic
downscale gain does not carry to the compressed case, and 50% blending did not cure that
regression. Evaluate one compression-aware pixel-loss candidate against these same inputs;
keep target measurement and human moving-output review ahead of app adoption. Original
playback stays independent. Fast action, darkness, camera motion, full-size 12 GB fit,
browser switching and a resumable derivative pipeline remain open October work.

Verification: all three probe processes exited 0 and rechecked unchanged input PNG bytes;
both source clip hashes also matched before/after. CLI checks for existing output,
unavailable CUDA and a missing private-named input exited 2 with fixed diagnostics and
preserved the prior report. `pip check`, compile and documentation-link checks passed.
The app code/dependencies are untouched; the existing 61-test application and DOM4
evidence in [current](current.md) was reused, not rerun or counted as enhancement coverage.

Fresh review of local `d95394e` found that Python could execute cached network bytecode
despite the source hash. `87b3cb9` executes the verified bytes directly; an independent
stale-cache canary and altered-source check passed. Final code review at `84c1683` found
no further actionable findings and independently checked 12 cheap tiling boundary cases.
An author's initial bitwise-float tiling assertion failed; the measured overlap rounding
error was only `5.96e-8`, and explicit `1e-6` tolerance passed. These geometry checks use
a nearest-neighbor stub, not model-quality evidence. The 48-frame run used `d95394e`;
the subsequent two runs used `84c1683` (same verified network, weights and crop tiling).

Public decoded clip SHA-256 values for reproducing this exact evidence:

- Dialogue excerpt: `a5caeaf54be4c570a989092c56fc6f67a48de9aa8df5df56fc55507cc64866f7`.
- Close-up excerpt: `91a4e0fd862a64af67ca4626227e65e64a388f3f09f7b526d6f95ecc43e9b771`.

They identify the local FFV1 decodes, not a full-movie publisher checksum. Media,
models, frame outputs and raw reports remain outside Git.
