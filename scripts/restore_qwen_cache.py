"""Restore the owner's pinned public Qwen cache archives, offline and without overwrite."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from time import monotonic
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_clarity.qwen import ASR_REPO, ASR_REVISION, ALIGNER_REPO, ALIGNER_REVISION
from media_clarity.storage import MediaError, RESERVE, default_data_dir, file_signature, no_symlink, open_lock
from media_clarity.model_check import diagnose, ERRORS as MODEL_ERRORS
from scripts.check_setup import collect, run_setup, worker_output

TOTAL_SECONDS = 1200
IDLE_SECONDS = 90
BUFFER = 8 * 1024 * 1024
SPECS = {
    'asr': (ASR_REPO, ASR_REVISION, '30a9018550ee63d6447dc5d089c35bc1291f4a2b458815146b7e4407556a16d4'),
    'aligner': (ALIGNER_REPO, ALIGNER_REVISION, '4fa24cbec4e43863ca2f8c8671ada340ee210648028780a2d9cd9b7e1c0c4c66'),
}
ERRORS = {'unsafe_storage', 'already_running', 'processing_worker_active',
          'custom_model_paths_configured', 'model_cache_manifest_invalid',
          'model_cache_changed', 'model_cache_missing', 'model_restore_conflict',
          'model_archive_invalid', 'insufficient_space', 'model_restore_failed'}


def regular(path):
    no_symlink(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise MediaError('model_cache_missing', 503)
    return path


def digest_file(path, expected, tick, consume=None):
    digest = hashlib.sha256()
    with regular(path).open('rb') as stream:
        signature = file_signature(stream)
        if signature[2] != expected['bytes']:
            raise MediaError('model_cache_changed', 503)
        while block := stream.read(BUFFER):
            digest.update(block)
            if consume:
                consume(block)
            tick()
        if file_signature(stream) != signature or digest.hexdigest() != expected['sha256']:
            raise MediaError('model_cache_changed', 503)


def manifest_for(kind, bundle):
    path = regular(bundle / 'model-cache-manifest.json')
    if path.stat().st_size > 65536:
        raise MediaError('model_cache_manifest_invalid', 503)
    with path.open('rb') as stream:
        raw = stream.read(65537)
    repo, revision, digest = SPECS[kind]
    if hashlib.sha256(raw).hexdigest() != digest:
        raise MediaError('model_cache_manifest_invalid', 503)
    value = json.loads(raw)
    if value['repo'] != repo or value['revision'] != revision:
        raise MediaError('model_cache_manifest_invalid', 503)
    return value


def preflight(kind, bundle, parts_dir, destination, verify_only, tick):
    manifest = manifest_for(kind, bundle)
    no_symlink(parts_dir)
    no_symlink(destination)
    for part in manifest['parts']:
        archive = regular(parts_dir / part['archive_name'])
        if archive.stat().st_size != part['archive_bytes']:
            raise MediaError('model_cache_changed', 503)
    files = {**manifest['metadata'], 'model.safetensors':manifest['model']}
    for name, expected in manifest['metadata'].items():
        digest_file(bundle / 'model-cache-metadata' / name, expected, tick)
    missing_bytes = 0
    if not verify_only:
        for name, expected in files.items():
            target = destination / name
            no_symlink(target)
            if target.exists():
                try:
                    digest_file(target, expected, tick)
                except MediaError as exc:
                    if exc.code == 'unsafe_storage':
                        raise
                    raise MediaError('model_restore_conflict', 409) from None
            else:
                missing_bytes += expected['bytes']
    return manifest, missing_bytes


def publish(temporary, target):
    no_symlink(target)
    try:
        # Atomic fail-if-exists, including a destination created after preflight.
        os.link(temporary, target)
    except FileExistsError:
        raise MediaError('model_restore_conflict', 409) from None
    Path(temporary).unlink()


def restore_one(kind, bundle, parts_dir, destination, manifest, verify_only, emit, tick):
    target = destination / 'model.safetensors'
    output = temporary = None
    model_exists = target.exists() if not verify_only else False
    if not verify_only:
        no_symlink(destination)
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not verify_only and not model_exists:
        descriptor, temporary = tempfile.mkstemp(prefix='.model-restore-', suffix='.partial', dir=destination)
        output = os.fdopen(descriptor, 'wb')
    digest = hashlib.sha256()
    count = 0
    try:
        for part in manifest['parts']:
            archive = regular(parts_dir / part['archive_name'])
            # Hash and consume the same open archive, checking its file signature.
            with archive.open('rb') as stream:
                signature = file_signature(stream)
                archive_digest = hashlib.sha256()
                while block := stream.read(BUFFER):
                    archive_digest.update(block); tick()
                if (signature[2] != part['archive_bytes'] or
                        archive_digest.hexdigest() != part['archive_sha256']):
                    raise MediaError('model_cache_changed', 503)
                stream.seek(0)
                with zipfile.ZipFile(stream) as zipped:
                    entries = zipped.infolist()
                    if len(entries) != 1:
                        raise MediaError('model_archive_invalid', 503)
                    entry = entries[0]
                    if (entry.filename != part['member_name'] or entry.is_dir() or
                            entry.compress_type != zipfile.ZIP_STORED or entry.flag_bits & 1 or
                            entry.file_size != part['bytes'] or entry.compress_size != part['bytes'] or
                            stat.S_ISLNK(entry.external_attr >> 16)):
                        raise MediaError('model_archive_invalid', 503)
                    member_digest = hashlib.sha256(); member_bytes = 0
                    with zipped.open(entry) as incoming:
                        while block := incoming.read(BUFFER):
                            member_bytes += len(block)
                            if member_bytes > part['bytes']:
                                raise MediaError('model_archive_invalid', 503)
                            member_digest.update(block); digest.update(block); count += len(block)
                            if output:
                                output.write(block)
                            tick()
                    if member_bytes != part['bytes'] or member_digest.hexdigest() != part['sha256']:
                        raise MediaError('model_cache_changed', 503)
                if file_signature(stream) != signature:
                    raise MediaError('model_cache_changed', 503)
            emit({'check':{'name':kind, 'state':'ready', 'part':part['index']}})
        if count != manifest['model']['bytes'] or digest.hexdigest() != manifest['model']['sha256']:
            raise MediaError('model_cache_changed', 503)
        if output:
            output.flush(); os.fsync(output.fileno()); output.close(); output = None
            publish(temporary, target)
        elif model_exists:
            # A destination appearing/changing after preflight is not trusted.
            digest_file(target, manifest['model'], tick)
        if not verify_only:
            for name, expected in manifest['metadata'].items():
                target = destination / name
                no_symlink(target)
                if target.exists():
                    digest_file(target, expected, tick)
                    continue
                descriptor, partial = tempfile.mkstemp(prefix='.metadata-restore-', suffix='.partial', dir=destination)
                with os.fdopen(descriptor, 'wb') as outgoing:
                    digest_file(bundle / 'model-cache-metadata' / name, expected, tick, outgoing.write)
                    outgoing.flush(); os.fsync(outgoing.fileno())
                publish(partial, target)
        emit({'check':{'name':kind, 'state':'ready', 'model_sha256':digest.hexdigest(),
                      'bytes':count, 'status':'verified_only' if verify_only else
                      ('reused' if model_exists else 'restored')}})
    finally:
        if output:
            output.close()
        # Incomplete files are intentionally retained; they are never runtime assets.


def restore(args, emit):
    last = [0.]
    active = ['asr']
    def tick():
        now = monotonic()
        if now - last[0] >= 5:
            emit({'progress':active[0]}); last[0] = now
    root = args.data_dir.absolute()
    if not args.verify_only:
        if not collect(root, emit, models=False):
            raise MediaError('model_restore_prerequisites_missing', 503)
        no_symlink(root)
        custom = root / 'models' / 'qwen-paths.json'
        no_symlink(custom)
        if custom.exists():
            raise MediaError('custom_model_paths_configured', 409)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Same OS locks used by the app and its model workers, without opening the DB.
    with ExitStack() as locks:
        if not args.verify_only:
            locks.enter_context(open_lock(root / 'instance.lock', 'already_running', 503))
            emit({'progress':'models'})
            runtime = diagnose(root, runtime_only=True)
            emit({'check':{'name':'models', **runtime}})
            if runtime['state'] != 'ready':
                raise MediaError(runtime['error'] or 'model_restore_failed', 503)
            # The isolated native probe released its worker lease at process exit.
            # Retake it before hashing/writing while the app lock remains held.
            locks.enter_context(open_lock(root / 'worker.lock', 'processing_worker_active', 409))
        plans = []
        needed = 0
        for kind, bundle in (('asr', args.asr_bundle), ('aligner', args.aligner_bundle)):
            active[0] = kind
            parts = args.parts_dir if args.parts_dir is not None else bundle
            destination = root / 'models' / ('qwen-' + kind)
            manifest, missing = preflight(kind, bundle, parts, destination, args.verify_only, tick)
            plans.append((kind, bundle, parts, destination, manifest)); needed += missing
        if not args.verify_only and needed and shutil.disk_usage(root).free < needed + RESERVE:
            raise MediaError('insufficient_space', 507)
        for kind, bundle, parts, destination, manifest in plans:
            active[0] = kind
            restore_one(kind, bundle, parts, destination, manifest, args.verify_only, emit, tick)
    emit({'state':'ready'})


def worker(args):
    output = worker_output()
    def emit(value):
        os.write(output, (json.dumps(value, ensure_ascii=True) + '\n').encode('ascii'))
    def audit(event, values):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto'):
            raise MediaError('model_restore_failed', 503)
    sys.addaudithook(audit)
    try:
        restore(args, emit)
        return 0
    except Exception as exc:
        code = exc.code if isinstance(exc, MediaError) and exc.code in ERRORS | MODEL_ERRORS | {'model_restore_prerequisites_missing'} else 'model_restore_failed'
        emit({'state':'blocked', 'error':code})
        return 1
    finally:
        os.close(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asr-bundle', type=Path, required=True)
    parser.add_argument('--aligner-bundle', type=Path, required=True)
    parser.add_argument('--parts-dir', type=Path, help='Optional shared directory containing all 15 ZIP archives')
    parser.add_argument('--data-dir', type=Path, default=default_data_dir())
    parser.add_argument('--verify-only', action='store_true', help='Check source caches without runtime preflight or destination writes')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args)
    def show(check):
        if check['name'] in ('asr', 'aligner'):
            label = '음성 인식 모델' if check['name'] == 'asr' else '시간 정렬 모델'
            detail = ('조각 ' + str(check['part']) + ' 검증') if 'part' in check else {
                'restored':'복원 완료', 'reused':'기존 파일 검증 완료', 'verified_only':'원본 캐시 검증 완료'}.get(check.get('status'), '검증 중')
            print(label + ': ' + detail, flush=True)
        else:
            from scripts.check_setup import show as show_prerequisite
            show_prerequisite(check)
    result = run_setup([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], '--worker'],
                       total_seconds=TOTAL_SECONDS, idle_seconds=IDLE_SECONDS,
                       expected_checks=17 if args.verify_only else 22, progress=None if args.json else show)
    result.update(api_connection='not_checked', actual_inference='not_checked', verify_only=args.verify_only)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print('캐시 검증 완료.' if result['state'] == 'ready' and args.verify_only else
              '모델 복원 완료. check-media-clarity.cmd로 실행 환경을 확인하세요.' if result['state'] == 'ready' else
              '복원이 중단됐습니다. 완료 파일과 .partial 파일은 보존됩니다. 진단 코드: ' + result.get('error', 'model_restore_failed'))
        print('Gemini 연결·실제 추론·감상 품질은 별도 확인이 필요합니다.')
    return 0 if result['state'] == 'ready' else 1


if __name__ == '__main__':
    raise SystemExit(main())
