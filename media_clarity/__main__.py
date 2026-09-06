"""python -m media_clarity: safe local launch, diagnostics or read-only source import."""
import argparse
import json
import logging
from pathlib import Path
import sys

from .storage import MediaError, Store, default_data_dir


class SafeServerLog(logging.Filter):
    def filter(self, record):
        # Uvicorn transport failures may carry private paths/URLs in exception text.
        if record.exc_info or record.levelno >= logging.ERROR:
            record.msg, record.args = "Local server operation failed; check the in-app diagnostic.", ()
            record.exc_info = record.exc_text = None
        return True


def main():
    parser = argparse.ArgumentParser(description="Media Clarity · local viewing")
    parser.add_argument("command", nargs="?", choices=("serve", "doctor", "import"), default="serve")
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--models", action="store_true", help="doctor: also check the optional subtitle model runtime")
    args = parser.parse_args()
    if args.models and args.command != 'doctor':
        parser.error('--models is only available with doctor')
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    try:
        if args.command == "serve":
            import uvicorn
            from .app import create_app
            for name in ("uvicorn", "uvicorn.error", "uvicorn.asgi"):
                logging.getLogger(name).addFilter(SafeServerLog())
            uvicorn.run(create_app(args.data_dir), host="127.0.0.1", port=args.port,
                        access_log=False, log_level="warning", timeout_keep_alive=5,
                        limit_concurrency=32, h11_max_incomplete_event_size=16384)
            return 0
        store = Store(args.data_dir)
        store.start()
        try:
            if args.command == "doctor":
                from .model_check import configuration, diagnose
                models = configuration(store.root)
                if args.models:
                    models = diagnose(store.root)
                print(json.dumps({**store.diagnostics(), 'models':models}, ensure_ascii=False))
                if args.models and models['state'] != 'ready':
                    return 1
            elif args.source is None:
                print("ERROR: source_required", file=sys.stderr)
                return 2
            else:
                result = store.import_path(args.source)
                if result['item']['unavailable_reason'] == 'rendition_required':
                    from .renditions import prepare
                    prepare(store, result['item']['id'])
                print(json.dumps({"id": result["item"]["id"], "duplicate": result["duplicate"]}))
        finally:
            store.close()
        return 0
    except MediaError as exc:
        print("ERROR: " + exc.code, file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: local_operation_failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
