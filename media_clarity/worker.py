"""Internal, quiet child entry point. Only opaque error codes are persisted."""
import os
from pathlib import Path
import sys


def main():
    for name in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK','ORT_DISABLE_TELEMETRY'):
        os.environ[name] = '1'
    if len(sys.argv) == 3:
        from .worker_lifecycle import supervise
        return supervise([sys.executable, '-m', 'media_clarity.worker', *sys.argv[1:], '--compute'])
    if len(sys.argv) != 4 or sys.argv[3] != '--compute' or os.read(sys.stdin.fileno(), 1) != b'1':
        return 1
    from .jobs import execute
    from .storage import Store
    execute(Store(Path(sys.argv[1])), sys.argv[2])


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
