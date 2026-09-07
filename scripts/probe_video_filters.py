#!/usr/bin/env python3
"""Bounded, offline moving-video comparison; no application adoption or model needed."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FILTER = 'hqdn3d=0.75:0.5:1.0:0.75,scale=iw*2:ih*2:flags=lanczos,unsharp=3:3:0.2:3:3:0'


def digest(path):
    with path.open('rb') as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
        return value.hexdigest()


def command(args, cwd=None, stage='media'):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=240)
    except subprocess.TimeoutExpired:
        raise ValueError(f'{stage}_timeout') from None
    if result.returncode:
        raise ValueError(f'{stage}_exit_{result.returncode}')
    return result.stdout


def inspect(path):
    data = json.loads(command(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-select_streams', 'v:0', '-count_frames', '-show_entries',
        'stream=width,height,pix_fmt,avg_frame_rate,nb_read_frames:format=duration',
        '-of', 'json', str(path)], stage='inspect'))
    stream = data['streams'][0]
    return dict(width=int(stream['width']), height=int(stream['height']),
                frames=int(stream['nb_read_frames']), fps=float(Fraction(stream['avg_frame_rate'])),
                duration=float(data['format']['duration']), pixel_format=stream['pix_fmt'])


def encode(source, output, filters, codec):
    start = time.perf_counter()
    command(['ffmpeg', '-v', 'error', '-nostdin', '-threads', '4', '-filter_threads', '4',
        '-protocol_whitelist', 'file,pipe', '-i', str(source), '-map', '0:v:0', '-an',
        '-map_metadata', '-1', '-vf', 'setpts=PTS-STARTPTS,' + filters,
        '-fps_mode', 'passthrough', *codec, '-threads', '4', '-n', str(output)], stage='encode')
    return time.perf_counter() - start


def score(reference, output, directory, name, metric, expected_frames):
    filename = f'{name}.{metric}'
    # Pair decoded presentation order, independent of MP4/MKV timestamp rounding.
    graph = f'[0:v]settb=1/1000,setpts=N[a];[1:v]settb=1/1000,setpts=N[b];[a][b]{metric}=stats_file={filename}:shortest=1'
    command(['ffmpeg', '-v', 'error', '-nostdin', '-filter_complex_threads', '4',
        '-protocol_whitelist', 'file,pipe', '-i', str(output),
        '-protocol_whitelist', 'file,pipe', '-i', str(reference),
        '-lavfi', graph, '-an', '-f', 'null', '-'], directory, stage=f'score_{metric}')
    lines = (directory / filename).read_text().splitlines()
    if len(lines) != expected_frames:
        raise ValueError('metric_frame_mismatch')
    key = 'psnr_avg' if metric == 'psnr' else 'All'
    values = [float(dict(token.split(':', 1) for token in line.split() if ':' in token)[key]) for line in lines]
    if not all(math.isfinite(value) for value in values):
        raise ValueError('nonfinite_metric')
    return {'mean': sum(values) / len(values), 'min': min(values), 'frames': len(values)}


def run(reference, directory):
    reference, directory = reference.resolve(strict=True), directory.resolve()
    if not reference.is_file() or directory.is_relative_to(ROOT):
        raise ValueError('invalid_probe_location')
    before = digest(reference)
    info = inspect(reference)
    if (not 1 <= info['duration'] <= 20 or not 1 <= info['fps'] <= 60 or
        not 2 <= info['frames'] <= 1200 or info['width'] % 4 or info['height'] % 4 or
        not 64 <= min(info['width'], info['height']) or max(info['width'], info['height']) > 1920 or
        info['pixel_format'] != 'yuv420p'):
        raise ValueError('unsupported_probe_clip')
    directory.mkdir(exist_ok=False)
    protocol = {'reference_sha256': before, 'reference': info, 'candidate_filter': FILTER,
                'input': 'half-size FFmpeg bicubic, H.264 CRF28 medium yuv420p',
                'limits': 'One fixed filter, synthetic degradation; metrics cannot accept motion or human quality.'}
    (directory / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    low = directory / 'input.mp4'
    encode(reference, low, 'scale=iw/2:ih/2:flags=bicubic',
           ['-c:v', 'libx264', '-preset', 'medium', '-crf', '28', '-pix_fmt', 'yuv420p'])
    results = {}
    for name, filters in [('lanczos', 'scale=iw*2:ih*2:flags=lanczos'), ('filtered', FILTER)]:
        output = directory / f'{name}.mkv'
        elapsed = encode(low, output, filters, ['-c:v', 'ffv1', '-pix_fmt', 'yuv420p'])
        observed = inspect(output)
        if (any(observed[k] != info[k] for k in ('width', 'height', 'frames', 'pixel_format')) or
            abs(observed['fps'] - info['fps']) > .001 or abs(observed['duration'] - info['duration']) > .05):
            raise ValueError('output_timeline_mismatch')
        results[name] = {'output_sha256': digest(output), 'decode_filter_lossless_encode_seconds': elapsed,
            'pipeline_fps': info['frames'] / elapsed,
            **{metric: score(reference, output, directory, name, metric, info['frames']) for metric in ('psnr', 'ssim')}}
    if digest(reference) != before:
        raise ValueError('reference_changed')
    report = {**protocol, 'python': platform.python_version(), 'system': platform.system(),
              'ffmpeg': command(['ffmpeg', '-version']).decode().splitlines()[0],
              'input_sha256': digest(low), 'reference_unchanged': True, 'results': results}
    (directory / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': 'completed', 'frames': info['frames']}))


def main():
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            self.exit(2, 'invalid_arguments\n')
    parser = Parser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.reference, args.output)
    except Exception as error:
        safe = {'invalid_probe_location', 'unsupported_probe_clip', 'metric_frame_mismatch',
                'nonfinite_metric', 'output_timeline_mismatch', 'reference_changed'}
        code = str(error) if isinstance(error, ValueError) and (str(error) in safe or
            re.fullmatch(r'(inspect|encode|score_psnr|score_ssim|media)_(exit_-?\d+|timeout)', str(error))) else 'filter_probe_failed'
        if isinstance(error, FileNotFoundError):
            code = 'input_or_tool_missing'
        elif isinstance(error, FileExistsError):
            code = 'output_exists'
        print(code, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
