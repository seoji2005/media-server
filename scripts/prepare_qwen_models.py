"""Explicit setup download only. The application itself never downloads models."""
import argparse
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_clarity.qwen import ASR_REPO, ASR_REVISION, ALIGNER_REPO, ALIGNER_REVISION, local_models
from media_clarity.storage import default_data_dir, no_symlink


def system_https_proxy():
    """Use only the existing HTTPS route; never fall back to ALL_PROXY or direct."""
    proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
    try:
        parsed = urlsplit(proxy or '')
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or any(c.isspace() or ord(c) < 32 for c in proxy)
                or (parsed.port is not None and not 1 <= parsed.port <= 65535)):
            raise ValueError()
    except (ValueError, TypeError):
        # Do not echo a configured proxy URL or its credentials.
        raise ValueError('A valid existing HTTP/HTTPS proxy is required in https_proxy or HTTPS_PROXY.') from None
    return proxy


def https_client(proxy, request_hook):
    import httpx
    return httpx.Client(proxy=proxy, trust_env=True, follow_redirects=True,
                        event_hooks={'request': [request_hook]},
                        timeout=httpx.Timeout(30.0, connect=10.0))


def configure_system_https_proxy():
    proxy = system_https_proxy()
    from huggingface_hub import set_client_factory
    # Keep HF's offline guard and request handling from the installed version.
    # An unavailable hook/API is a setup error, not a reason to change packages.
    from huggingface_hub.utils._http import hf_request_event_hook
    set_client_factory(lambda: https_client(proxy, hf_request_event_hook))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=default_data_dir())
    parser.add_argument('--use-system-https-proxy', action='store_true',
                        help='Use the existing HTTPS proxy only for this model setup process; preserve TLS settings.')
    args = parser.parse_args()
    if args.use_system_https_proxy:
        try:
            configure_system_https_proxy()
        except ValueError as error:
            parser.error(str(error))
        except ImportError:
            parser.error('Installed huggingface_hub lacks the required client API; check the existing environment.')
    from huggingface_hub import snapshot_download
    for kind, repo, revision in (('asr', ASR_REPO, ASR_REVISION), ('aligner', ALIGNER_REPO, ALIGNER_REVISION)):
        destination = args.data_dir / 'models' / ('qwen-' + kind)
        no_symlink(destination)
        # Only explicit model assets. No Python, remote code, telemetry or media.
        snapshot_download(repo, revision=revision, local_dir=destination,
                          allow_patterns=['*.json', '*.safetensors', '*.jinja'])
    local_models(args.data_dir, check_packages=True)
    print('Qwen3-ASR-1.7B and Qwen3-ForcedAligner-0.6B files are ready. Run doctor --models next.')


if __name__ == '__main__':
    main()
