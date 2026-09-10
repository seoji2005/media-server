"""Explicit setup download only. The application itself never downloads models."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_clarity.qwen import ASR_REPO, ASR_REVISION, ALIGNER_REPO, ALIGNER_REVISION, local_models
from media_clarity.storage import default_data_dir, no_symlink


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=default_data_dir())
    args = parser.parse_args()
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
