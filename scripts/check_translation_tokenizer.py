"""Offline regression against installed MADLAD tokenizer files; no weight loading."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_clarity.models import require_private_runtime, translation_tokenizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    args = parser.parse_args()
    for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK'):
        os.environ[key] = '1'
    require_private_runtime()
    began = time.monotonic()
    attempts = []
    def audit(event, unused):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            attempts.append(event)
            raise RuntimeError('network_blocked_in_tokenizer_check')
    sys.addaudithook(audit)
    from transformers import AutoTokenizer
    native = translation_tokenizer(args.model_dir)
    fast = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True, trust_remote_code=False)
    fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/translation_compare.json'
    cases = json.loads(fixture.read_text())['cases']
    differences = [r['id'] for r in cases if
        native('<2ko> '+r['text'])['input_ids'] != fast('<2ko> '+r['text'])['input_ids']]
    controls = []
    for text in ('찼어요.', 'GPU 메모리가 찼어요.', '원문에 <0xEC><0xB0><0xBC>라고 쓰였습니다.', '😀 𠮷'):
        ids = native.encode(text)
        actual = native.decode(ids, skip_special_tokens=True)
        controls.append({'text':text, 'actual':actual, 'unknown_tokens':ids.count(native.unk_token_id)})
    byte_ids = fast.convert_tokens_to_ids(['<0xEC>', '<0xB0>', '<0xBC>'])
    decoded = native.decode(byte_ids, skip_special_tokens=True)
    passed = not differences and decoded == '찼' and not attempts and all(
        c['text'] == c['actual'] and c['unknown_tokens'] == 0 for c in controls)
    report = {'passed':passed, 'seconds':round(time.monotonic()-began, 3),
        'versions':{p:importlib.metadata.version(p) for p in ('transformers','sentencepiece','protobuf','tokenizers')},
        'sha256':{n:hashlib.sha256((args.model_dir/n).read_bytes()).hexdigest() for n in
                  ('tokenizer.json','spiece.model','tokenizer_config.json')},
        'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
        'inputs':len(cases), 'different_input_ids':differences,
        'byte_ids':byte_ids, 'native_decode':decoded, 'fast_decode':fast.decode(byte_ids, skip_special_tokens=True),
        'controls':controls, 'network_attempts':attempts,
        'limit':'Tokenizer behavior only; no generation, semantic quality or target CUDA measurement.'}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
