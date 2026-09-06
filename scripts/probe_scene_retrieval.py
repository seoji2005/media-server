"""Offline scene-retrieval evaluation, separate from the application and its library."""
import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = re.compile(r'[a-zA-Z0-9_-]{1,64}')


def load_manifest(path):
    if path.stat().st_size > 256 * 1024:
        raise ValueError('invalid_manifest')
    document = json.loads(path.read_text(encoding='utf-8'))
    frames, queries = document['frames'], document['queries']
    if not 2 <= len(frames) <= 120 or not 1 <= len(queries) <= 128:
        raise ValueError('invalid_manifest')
    frame_ids = set()
    for frame in frames:
        if not IDENTIFIER.fullmatch(frame['id']) or frame['id'] in frame_ids:
            raise ValueError('invalid_manifest')
        frame_ids.add(frame['id'])
        if type(frame['time']) not in (int, float) or not math.isfinite(frame['time']) or frame['time'] < 0:
            raise ValueError('invalid_manifest')
        image = path.parent / frame['image']
        if image.is_symlink() or not image.is_file() or image.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('invalid_image')
    query_ids = set()
    for query in queries:
        if not IDENTIFIER.fullmatch(query['id']) or query['id'] in query_ids:
            raise ValueError('invalid_manifest')
        query_ids.add(query['id'])
        if (not isinstance(query['text'], str) or not query['text'].strip() or len(query['text']) > 512
                or any(not c.isprintable() for c in query['text'])
                or query.get('language') not in {'ko', 'en', 'ja'}):
            raise ValueError('invalid_manifest')
        relevant = query['relevant']
        if not isinstance(relevant, list) or len(relevant) != len(set(relevant)) or not set(relevant) <= frame_ids:
            raise ValueError('invalid_manifest')
    return document


def rank_results(frames, queries, scores):
    """Rank evidence IDs; absent queries have no invented positive/recall score."""
    if len(scores) != len(queries):
        raise ValueError('invalid_scores')
    rows = []
    for query, values in zip(queries, scores):
        if len(values) != len(frames) or not all(math.isfinite(v) for v in values):
            raise ValueError('invalid_scores')
        order = sorted(range(len(frames)), key=lambda i: (-values[i], frames[i]['id']))
        ranks = [n + 1 for n, index in enumerate(order) if frames[index]['id'] in query['relevant']]
        rows.append({'id': query['id'], 'language': query['language'], 'relevant': query['relevant'],
                     'rank': min(ranks) if ranks else None,
                     'top_score': values[order[0]], 'margin': values[order[0]] - values[order[1]],
                     'top': [{'id': frames[i]['id'], 'time': frames[i]['time'], 'score': values[i]} for i in order[:5]]})
    summary = {}
    for language in sorted({q['language'] for q in queries}):
        positives = [r for r in rows if r['language'] == language and r['relevant']]
        summary[language] = {'positive_queries': len(positives),
                             'absent_queries': sum(r['language'] == language and not r['relevant'] for r in rows),
                             'hit_at_1': sum(r['rank'] == 1 for r in positives) / len(positives) if positives else None,
                             'hit_at_3': sum(r['rank'] <= 3 for r in positives) / len(positives) if positives else None}
    return rows, summary


def offline():
    for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'DO_NOT_TRACK'):
        os.environ[key] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    attempts = []
    def audit(event, _):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto'}:
            attempts.append(event)
            raise RuntimeError('network_disabled')
    sys.addaudithook(audit)
    return attempts


def model_files(path):
    """Describe local inputs without treating a supplied revision as proof of bytes."""
    result = []
    for file in sorted(path.iterdir()):
        if not file.is_file():
            continue
        stat = file.stat()
        row = {'name': file.name, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
               'device': stat.st_dev, 'inode': stat.st_ino}
        # Small configuration/tokenizer files determine preprocessing. Large weight
        # identity stays metadata-based, as in the app; no repeated weight scan.
        if stat.st_size <= 64 * 1024 * 1024:
            with file.open('rb') as stream:
                row['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        result.append(row)
    return result


def run(args):
    # Refuse outputs within the checkout and all existing destinations. The probe
    # never imports into the app's library or changes its jobs/captions/history.
    if args.output.resolve().is_relative_to(ROOT):
        raise ValueError('output_must_be_outside_checkout')
    manifest_bytes = args.manifest.read_bytes()
    manifest = load_manifest(args.manifest)
    if args.manifest.read_bytes() != manifest_bytes:
        raise ValueError('inputs_changed')
    local_files = model_files(args.model)
    attempts = offline()
    import importlib.metadata
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('cuda_unavailable')
    args.output.mkdir(exist_ok=False)
    started = time.perf_counter()
    model = AutoModel.from_pretrained(args.model, local_files_only=True, trust_remote_code=False,
                                      use_safetensors=True).to(args.device).eval()
    if model.config.model_type != 'siglip':
        raise ValueError('unsupported_model')
    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True,
                                              trust_remote_code=False, use_fast=False)
    load_seconds = time.perf_counter() - started
    if args.device == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    frame_hashes, vectors = [], []
    started = time.perf_counter()
    with torch.inference_mode():
        for first in range(0, len(manifest['frames']), args.batch_size):
            images = []
            for frame in manifest['frames'][first:first + args.batch_size]:
                path = args.manifest.parent / frame['image']
                raw = path.read_bytes()
                frame_hashes.append(hashlib.sha256(raw).hexdigest())
                import io
                with Image.open(io.BytesIO(raw)) as image:
                    if not 0 < image.width <= 4096 or not 0 < image.height <= 4096:
                        raise ValueError('invalid_image')
                    image = image.convert('RGB')
                    # Match the app's saved-preview resolution, including JPEG input.
                    image.thumbnail((320, 180))
                    images.append(image.copy())
            inputs = processor(images=images, return_tensors='pt').to(args.device)
            vectors.append(torch.nn.functional.normalize(model.get_image_features(**inputs), dim=-1).cpu())
        image_vectors = torch.cat(vectors)
        image_seconds = time.perf_counter() - started
        started = time.perf_counter()
        text_vectors = []
        for first in range(0, len(manifest['queries']), args.batch_size):
            text = [q['text'].lower() for q in manifest['queries'][first:first + args.batch_size]]
            tokens = processor(text=text, padding='max_length', max_length=64, truncation=False, return_tensors='pt')
            if tokens['input_ids'].shape[-1] > 64:
                raise ValueError('query_too_long')
            text_vectors.append(torch.nn.functional.normalize(model.get_text_features(**tokens.to(args.device)), dim=-1).cpu())
        scores = (torch.cat(text_vectors) @ image_vectors.T).tolist()
        text_seconds = time.perf_counter() - started
    for frame, digest in zip(manifest['frames'], frame_hashes):
        if hashlib.sha256((args.manifest.parent / frame['image']).read_bytes()).hexdigest() != digest:
            raise ValueError('inputs_changed')
    if args.manifest.read_bytes() != manifest_bytes:
        raise ValueError('inputs_changed')
    if model_files(args.model) != local_files:
        raise ValueError('inputs_changed')
    if attempts:
        raise RuntimeError('network_disabled')
    rows, summary = rank_results(manifest['frames'], manifest['queries'], scores)
    report = {'declared_model_revision': args.revision, 'revision_verified': False,
              'local_model_files': local_files, 'large_weights_content_hashed': False,
              'model_type': model.config.model_type,
              'packages': {n: importlib.metadata.version(n) for n in ('torch', 'transformers', 'Pillow')},
              'device': args.device, 'threads': args.threads, 'batch_size': args.batch_size,
              'preprocessing': 'preview-320x180; slow processor; lowercase; max-length64; no truncation',
              'frames': len(frame_hashes), 'frame_sha256': frame_hashes,
              'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
              'load_seconds': load_seconds, 'image_seconds': image_seconds, 'text_seconds': text_seconds,
              'cuda_peak_allocated_mib': torch.cuda.max_memory_allocated() / 2**20 if args.device == 'cuda' else None,
              'network_attempts': len(attempts), 'summary': summary, 'results': rows}
    if sys.platform.startswith('linux'):
        import resource
        report['process_peak_rss_mib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    temporary = args.output / 'report.partial.json'
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.rename(args.output / 'report.json')
    return {'status': 'completed', 'frames': len(frame_hashes), 'summary': summary}


def main():
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError('invalid_arguments')
    try:
        parser = Parser(description=__doc__)
        for name in ('model', 'manifest', 'output'):
            parser.add_argument('--' + name, required=True, type=Path)
        parser.add_argument('--revision', required=True)
        parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
        parser.add_argument('--threads', type=int, choices=range(1, 17), default=4)
        parser.add_argument('--batch-size', type=int, choices=range(1, 17), default=4)
        args = parser.parse_args()
        if not re.fullmatch(r'[0-9a-f]{40}', args.revision):
            raise ValueError('invalid_arguments')
        with open(os.devnull, 'w') as quiet, contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            result = run(args)
        print(json.dumps(result))
        return 0
    except Exception as error:
        allowed = {'invalid_arguments', 'invalid_manifest', 'invalid_image', 'invalid_scores',
                   'output_must_be_outside_checkout', 'cuda_unavailable', 'unsupported_model',
                   'network_disabled', 'query_too_long', 'inputs_changed'}
        print(json.dumps({'error': str(error) if str(error) in allowed else 'scene_probe_failed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
