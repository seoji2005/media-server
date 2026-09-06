"""Internal, quiet child entry point. Only opaque error codes are persisted."""
import os
from pathlib import Path
import sys
import threading


def main():
    for name in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK','ORT_DISABLE_TELEMETRY'):
        os.environ[name] = '1'
    # EOF follows parent death, even on an abrupt Windows/Linux server exit.
    # No private payload is passed through this liveness pipe.
    def parent_gone():
        sys.stdin.buffer.read()
        os._exit(1)
    threading.Thread(target=parent_gone, daemon=True).start()
    from .jobs import execute
    from .storage import Store
    execute(Store(Path(sys.argv[1])), sys.argv[2])


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit(1)
