"""On-demand, isolated model diagnostics; never inspect media or emit raw errors."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading

from .storage import MediaError

ERRORS = {'local_models_missing', 'model_runtime_missing', 'model_settings_invalid',
          'model_privacy_setup_required', 'model_torch_unavailable', 'model_cuda_unavailable',
          'model_bf16_unavailable', 'model_asr_cuda_unavailable', 'model_asr_runtime_unavailable',
          'model_asr_precision_unavailable', 'model_audio_runtime_unavailable',
          'model_runtime_incompatible', 'model_check_failed', 'model_check_timeout',
          'unsafe_storage', 'storage_unavailable', 'processing_worker_active'}


def configuration(root):
    from .models import device_configuration
    try:
        return {**device_configuration(root), 'state':'unchecked', 'error':None}
    except (MediaError, OSError) as exc:
        code = exc.code if isinstance(exc, MediaError) and exc.code in ERRORS else 'model_check_failed'
        return {'device':None, 'selection':None, 'state':'blocked', 'error':code}


def inspect_runtime(root):
    result = configuration(root)
    if result['error']:
        return result
    try:
        from .models import LocalModels
        # Constructor checks packages/device, but loads no ASR/translation weights.
        backend = LocalModels(root)
        result['device'] = backend.device
        result['state'] = 'ready'
    except Exception as exc:
        result['state'] = 'blocked'
        result['error'] = exc.code if isinstance(exc, MediaError) and exc.code in ERRORS else 'model_check_failed'
    return result


def run_probe(root, timeout=60):
    # Keep stdin open as a parent-liveness pipe. Only the fixed, small result can
    # use stdout; native imports and their children inherit redirected null output.
    process = subprocess.Popen([sys.executable, '-m', 'media_clarity.model_check', str(root)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
            raise MediaError('model_check_timeout', 503) from None
        raw = process.stdout.read(4097)
        if process.returncode or len(raw) > 4096:
            raise MediaError('model_check_failed', 503)
        return raw
    finally:
        if process.poll() is None:
            process.kill(); process.wait()
        process.stdin.close(); process.stdout.close()


def diagnose(root):
    """Bounded child output and timeout; no heavyweight imports in the server."""
    result = configuration(root)
    if result['error']:
        return result
    try:
        raw = run_probe(root)
        value = json.loads(raw)
        if (type(value) is not dict or set(value) != {'device','selection','state','error'}
                or value['device'] not in ('cpu','cuda',None)
                or value['selection'] not in ('default','configured',None)
                or value['state'] not in ('ready','blocked')
                or (value['state'] == 'ready' and (value['error'] is not None or value['device'] is None))
                or (value['state'] == 'blocked' and value['error'] not in ERRORS)):
            raise ValueError('invalid diagnostic response')
        return value
    except Exception as exc:
        result['state'] = 'blocked'
        result['error'] = 'model_check_timeout' if isinstance(exc, MediaError) and exc.code == 'model_check_timeout' else 'model_check_failed'
        return result


def main():
    # Suppress Python and native-library stdout/stderr. Only the fixed JSON result
    # uses the original pipe; exception messages/paths never cross this boundary.
    output = os.dup(1)
    with open(os.devnull, 'wb') as quiet:
        os.dup2(quiet.fileno(), 1)
        os.dup2(quiet.fileno(), 2)
    def parent_gone():
        os.read(sys.stdin.fileno(), 1)
        os._exit(1)
    threading.Thread(target=parent_gone, daemon=True).start()
    def finish(result):
        os.write(output, json.dumps(result, separators=(',', ':')).encode('ascii'))
        # No native atexit/destructor can outlive the lease or hang after a result.
        # Process exit closes the pipe, OS lease and unloaded-model CUDA context.
        os._exit(0)
    try:
        from .jobs import worker_guard
        root = Path(sys.argv[1])
        with worker_guard(root):
            finish(inspect_runtime(root))
    except Exception as exc:
        code = exc.code if isinstance(exc, MediaError) and exc.code in ERRORS else 'model_check_failed'
        finish({'device':None, 'selection':None, 'state':'blocked', 'error':code})


if __name__ == '__main__':
    main()
