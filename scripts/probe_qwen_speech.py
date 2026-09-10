"""Measure the unchanged local Qwen speech path; no translation or library writes."""
import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_clarity.qwen import PACKAGES, QwenSpeech, SpeechTimings, private_runtime
from media_clarity.storage import MediaError, no_symlink


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def atomic_write(path, data):
    """A killed writer leaves either the old checkpoint or the complete new one."""
    no_symlink(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_saved(directory):
    checkpoint = directory / 'checkpoint.json'
    no_symlink(checkpoint)
    if checkpoint.exists():
        if checkpoint.stat().st_size > 17 * 1024 * 1024:
            raise ValueError('invalid_saved_parts')
        value = json.loads(checkpoint.read_text(encoding='utf-8'))
        if type(value) is not dict or value.get('version') != 1:
            raise ValueError('invalid_saved_parts')
        saved, prior = value.get('parts'), value.get('summary')
    else:
        # Previous probes have only the final two-file export. Their binding
        # remains mandatory; never fall back from a rejected new checkpoint.
        prior_parts, prior_summary = directory / 'parts.json', directory / 'summary.json'
        no_symlink(prior_parts)
        no_symlink(prior_summary)
        if prior_parts.stat().st_size > 16 * 1024 * 1024 or prior_summary.stat().st_size > 65536:
            raise ValueError('invalid_saved_parts')
        saved = json.loads(prior_parts.read_text(encoding='utf-8'))
        prior = json.loads(prior_summary.read_text(encoding='utf-8'))
    if (type(saved) is not list or type(prior) is not dict or prior.get('resumable') is not True
            or hashlib.sha256(canonical(saved)).hexdigest() != prior.get('parts_sha256')):
        raise ValueError('invalid_saved_parts')
    return saved, prior


def run(args):
    if args.output.resolve().is_relative_to(ROOT):
        raise ValueError('output_must_be_outside_checkout')
    no_symlink(args.output)
    no_symlink(args.input)
    if (not math.isfinite(args.duration) or not 0 < args.duration <= 24 * 3600
            or not 0 <= args.audio_index < 128 or not 1 <= args.threads <= 32):
        raise ValueError('invalid_probe_settings')
    saved, prior = [], None
    if args.resume_from:
        saved, prior = load_saved(args.resume_from)
    if args.reuse_spans is not None:
        if prior is None or not 0 <= args.reuse_spans <= len(saved):
            raise ValueError('invalid_saved_prefix')
        saved = saved[:args.reuse_spans]
    # Claim a fresh destination before model work. Never overwrite prior evidence.
    args.output.mkdir(exist_ok=False)
    timings = SpeechTimings()
    report = {'complete': False, 'profile': None, 'input_sha256': digest(args.input),
              'duration': args.duration, 'audio_index': args.audio_index,
              'threads': args.threads, 'saved_spans': 0, 'new_spans': 0, 'resumable': False,
              'network_attempts': 0, 'phases': timings.phases, 'checkpoint_seconds': 0.,
              'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                  cwd=ROOT, text=True).strip(),
              'scope': 'Local speech only. No Gemini, database or playback. Failed timings are partial.'}

    def audit(event, _):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto'):
            report['network_attempts'] += 1
            raise RuntimeError('network_disabled')

    private_runtime()
    sys.addaudithook(audit)
    parts = []
    speech = None
    accepted = False
    started = time.perf_counter()
    progress = sys.stdout

    def checkpoint():
        nonlocal parts, accepted
        began = time.perf_counter()
        # Each published prefix is bound to the still-current input and runtime.
        # Failed validation revokes this run's earlier prefix; no relabeling.
        if accepted:
            try:
                report['resumable'] = (digest(args.input) == report['input_sha256']
                    and speech.identity() == identity and not report['network_attempts'])
            except (Exception, KeyboardInterrupt):
                report['resumable'] = False
            if not report['resumable']:
                parts = []
                accepted = False
                report.update(complete=False, error='inputs_changed')
        report.update(elapsed_seconds=time.perf_counter() - started,
                      retained_spans=len(parts), parts_sha256=hashlib.sha256(canonical(parts)).hexdigest())
        atomic_write(args.output / 'checkpoint.json', canonical({'version': 1, 'summary': report, 'parts': parts}) + b'\n')
        report['checkpoint_seconds'] += time.perf_counter() - began

    try:
        # Model libraries can print paths/text on failures; retain only safe summary.
        with open(os.devnull, 'w') as quiet, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            import torch
            torch.set_num_threads(args.threads)
            torch.set_num_interop_threads(1)
            speech = QwenSpeech(args.data_dir, timings=timings)
            identity = speech.identity()
            report.update(profile=speech.asr_profile, device=speech.device,
                          runtime_identity=identity,
                          packages={name: importlib.metadata.version(name) for name in PACKAGES},
                          setup_seconds=time.perf_counter() - started)
            if prior is not None and any(prior.get(key) != report[key] for key in
                    ('input_sha256', 'runtime_identity', 'profile', 'duration', 'audio_index')):
                raise MediaError('processing_config_changed', 409)
            parts = list(saved)
            report['saved_spans'] = len(saved)
            accepted = True
            began_speech = time.perf_counter()
            previous_checkpoint_seconds = report['checkpoint_seconds']
            try:
                for part in speech.transcribe_parts(args.input, args.duration, args.audio_index, saved):
                    parts.append(part)
                    report['new_spans'] += 1
                    report['speech_seconds'] = (time.perf_counter() - began_speech
                        - (report['checkpoint_seconds'] - previous_checkpoint_seconds))
                    checkpoint()
                    if not report['resumable']:
                        raise MediaError('inputs_changed', 409)
                    print(json.dumps({'new_spans': report['new_spans'],
                        'through_seconds': part['clip'][1], 'unresolved': bool(part['error'])}),
                        file=progress, flush=True)
                    if part['error']:
                        raise MediaError(part['error'], 422)
            finally:
                report['speech_seconds'] = (time.perf_counter() - began_speech
                    - (report['checkpoint_seconds'] - previous_checkpoint_seconds))
            if any(part['error'] for part in saved):
                raise MediaError('alignment_unresolved', 422)
            if report['network_attempts']:
                raise RuntimeError('network_disabled')
        report['complete'] = True
    except (Exception, KeyboardInterrupt) as exc:
        report['error'] = exc.code if isinstance(exc, MediaError) else type(exc).__name__
        if isinstance(exc, MediaError) and exc.code == 'processing_checkpoint_invalid':
            parts = []
            accepted = False
            report['resumable'] = False
    finally:
        checkpoint()
        # Raw text stays only in the explicitly requested, fresh local directory.
        # These convenient final exports are not the source for new recovery.
        atomic_write(args.output / 'parts.json', canonical(parts) + b'\n')
        atomic_write(args.output / 'summary.json', json.dumps(report, indent=2).encode() + b'\n')
    return 0 if report['complete'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--duration', type=float, required=True)
    parser.add_argument('--audio-index', type=int, default=0)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume-from', type=Path)
    parser.add_argument('--reuse-spans', type=int)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        print(exc.code if isinstance(exc, MediaError) else type(exc).__name__)
        return 1


if __name__ == '__main__':
    sys.exit(main())
