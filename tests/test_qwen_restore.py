"""Offline cache restoration: corruption, interruption, no-overwrite and live leases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from media_clarity.storage import MediaError, open_lock
from scripts import check_setup, restore_qwen_cache as cache


def identity(data):
    return {'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()}


def fixture(root):
    parts = root / 'parts'; parts.mkdir()
    bundles = {}; specs = {}; weights = {}
    for kind, count in (('asr', 10), ('aligner', 5)):
        bundle = root / kind; bundle.mkdir(); bundles[kind] = bundle
        metadata = bundle / 'model-cache-metadata'; metadata.mkdir()
        data = b'{"synthetic":true}'
        (metadata / 'config.json').write_bytes(data)
        members = []; model = b''
        for index in range(1, count + 1):
            piece = (kind.encode() + bytes([index])) * 1024; model += piece
            name = f'{kind}-{index}.zip'; member = f'model.part{index:02d}.bin'
            with zipfile.ZipFile(parts / name, 'w', zipfile.ZIP_STORED) as z:
                z.writestr(member, piece)
            archive = (parts / name).read_bytes()
            members.append({'index':index, 'archive_name':name, 'member_name':member,
                            'archive_bytes':len(archive), 'archive_sha256':hashlib.sha256(archive).hexdigest(), **identity(piece)})
        repo, revision, _ = cache.SPECS[kind]
        manifest = {'repo':repo, 'revision':revision, 'metadata':{'config.json':identity(data)},
                    'model':{'name':'model.safetensors', **identity(model)}, 'parts':members}
        raw = json.dumps(manifest).encode(); (bundle / 'model-cache-manifest.json').write_bytes(raw)
        specs[kind] = (repo, revision, hashlib.sha256(raw).hexdigest()); weights[kind] = model
    args = argparse.Namespace(asr_bundle=bundles['asr'], aligner_bundle=bundles['aligner'],
                              parts_dir=parts, data_dir=root / 'library', verify_only=False)
    return args, specs, weights


class CacheRestoreTests(unittest.TestCase):
    def test_production_manifest_pins_are_complete_sha256_values(self):
        for repo, revision, digest in cache.SPECS.values():
            self.assertRegex(digest, r'^[0-9a-f]{64}$')
            self.assertRegex(revision, r'^[0-9a-f]{40}$')

    def run_fixture(self, args, specs, emit):
        with patch.object(cache, 'SPECS', specs), patch.object(cache, 'collect', return_value=True):
            return cache.restore(args, emit)

    def test_restore_reuse_preserves_database_settings_and_partial_files(self):
        with tempfile.TemporaryDirectory() as temp:
            args, specs, weights = fixture(Path(temp)); args.data_dir.mkdir()
            db = args.data_dir / 'library.sqlite3'; db.write_bytes(b'original database sentinel')
            models = args.data_dir / 'models'; models.mkdir()
            settings = models / 'settings.json'; settings.write_bytes(b'{"device":"cpu"}')
            partial = models / 'prior.partial'; partial.write_bytes(b'prior interruption')
            events = []
            self.run_fixture(args, specs, events.append)
            signatures = {}
            for kind, model in weights.items():
                path = models / ('qwen-' + kind) / 'model.safetensors'
                self.assertEqual(path.read_bytes(), model)
                signatures[kind] = (path.stat().st_ino, path.stat().st_mtime_ns)
            self.assertEqual(events[-1], {'state':'ready'})
            events = []; self.run_fixture(args, specs, events.append)
            self.assertEqual([e['check']['status'] for e in events if 'status' in e.get('check', {})], ['reused','reused'])
            for kind in weights:
                path = models / ('qwen-' + kind) / 'model.safetensors'
                self.assertEqual((path.stat().st_ino, path.stat().st_mtime_ns), signatures[kind])
            self.assertEqual(db.read_bytes(), b'original database sentinel')
            self.assertEqual(settings.read_bytes(), b'{"device":"cpu"}')
            self.assertEqual(partial.read_bytes(), b'prior interruption')

    def test_verify_only_never_creates_destination_or_requires_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            args, specs, _ = fixture(Path(temp)); args.verify_only = True
            with patch.object(cache, 'SPECS', specs), patch.object(cache, 'collect') as check:
                events = []; cache.restore(args, events.append)
            check.assert_not_called()
            self.assertFalse(args.data_dir.exists())
            self.assertEqual(len([e for e in events if 'check' in e]), 17)
            self.assertEqual(events[-1], {'state':'ready'})

    def test_prerequisite_failure_prevents_manifest_or_destination_work(self):
        with tempfile.TemporaryDirectory() as temp:
            args, specs, _ = fixture(Path(temp))
            with patch.object(cache, 'collect', return_value=False), patch.object(cache, 'manifest_for') as manifests:
                with self.assertRaisesRegex(MediaError, '^model_restore_prerequisites_missing$'):
                    cache.restore(args, lambda e:None)
            manifests.assert_not_called(); self.assertFalse(args.data_dir.exists())

    def test_changed_manifest_metadata_or_existing_other_model_prevents_publication(self):
        for mutation in ('manifest', 'metadata', 'existing', 'truncated'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                args, specs, _ = fixture(Path(temp))
                if mutation == 'manifest':
                    path = args.aligner_bundle / 'model-cache-manifest.json'; path.write_bytes(path.read_bytes() + b' ')
                elif mutation == 'metadata':
                    (args.aligner_bundle / 'model-cache-metadata/config.json').write_bytes(b'different')
                elif mutation == 'truncated':
                    (args.parts_dir / 'aligner-5.zip').write_bytes(b'truncated')
                else:
                    path = args.data_dir / 'models/qwen-aligner/model.safetensors'
                    path.parent.mkdir(parents=True); path.write_bytes(b'different existing model')
                with self.assertRaises(MediaError):
                    self.run_fixture(args, specs, lambda e:None)
                self.assertFalse((args.data_dir / 'models/qwen-asr/model.safetensors').exists())
                if mutation == 'existing':self.assertEqual(path.read_bytes(), b'different existing model')

    def test_corrupt_later_archive_retains_completed_model_and_unpublished_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            args, specs, weights = fixture(Path(temp))
            archive = args.parts_dir / 'aligner-2.zip'
            raw = bytearray(archive.read_bytes()); raw[50] ^= 1; archive.write_bytes(raw)
            with self.assertRaisesRegex(MediaError, '^model_cache_changed$'):
                self.run_fixture(args, specs, lambda e:None)
            self.assertEqual((args.data_dir / 'models/qwen-asr/model.safetensors').read_bytes(), weights['asr'])
            self.assertFalse((args.data_dir / 'models/qwen-aligner/model.safetensors').exists())
            partials = list((args.data_dir / 'models/qwen-aligner').glob('*.partial'))
            self.assertEqual(len(partials), 1); self.assertGreater(partials[0].stat().st_size, 0)

    def test_destination_race_never_overwrites_new_conflicting_file(self):
        with tempfile.TemporaryDirectory() as temp:
            args, specs, _ = fixture(Path(temp))
            target = args.data_dir / 'models/qwen-asr/model.safetensors'
            def emit(event):
                if event.get('check', {}).get('part') == 10:
                    target.write_bytes(b'concurrently created')
            with self.assertRaisesRegex(MediaError, '^model_restore_conflict$'):
                self.run_fixture(args, specs, emit)
            self.assertEqual(target.read_bytes(), b'concurrently created')
            self.assertEqual(len(list(target.parent.glob('*.partial'))), 1)

    def test_active_app_worker_and_custom_paths_are_preserved(self):
        for name in ('instance.lock', 'worker.lock', 'custom'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                args, specs, _ = fixture(Path(temp)); args.data_dir.mkdir()
                if name == 'custom':
                    models = args.data_dir / 'models'; models.mkdir()
                    config = models / 'qwen-paths.json'; config.write_bytes(b'private existing configuration')
                    with self.assertRaisesRegex(MediaError, '^custom_model_paths_configured$'):
                        self.run_fixture(args, specs, lambda e:None)
                    self.assertEqual(config.read_bytes(), b'private existing configuration')
                else:
                    with open_lock(args.data_dir / name, 'busy', 409):
                        with self.assertRaisesRegex(MediaError, '^already_running$|^processing_worker_active$'):
                            self.run_fixture(args, specs, lambda e:None)
                    self.assertFalse((args.data_dir / 'models').exists())

    def test_symlink_or_windows_junction_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); args, specs, _ = fixture(root)
            link = root / 'linked'
            if os.name == 'nt':
                subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(link),str(args.asr_bundle)],
                               check=True, capture_output=True, timeout=5)
            else:
                link.symlink_to(args.asr_bundle, target_is_directory=True)
            try:
                args.asr_bundle = link
                with self.assertRaisesRegex(MediaError, '^unsafe_storage$'):
                    self.run_fixture(args, specs, lambda e:None)
            finally:
                if os.name == 'nt':link.rmdir()
                else:link.unlink()

    def test_real_deadline_retains_completed_model_and_releases_owned_locks(self):
        with tempfile.TemporaryDirectory() as temp:
            args, specs, weights = fixture(Path(temp))
            code = '''import argparse,json,os,sys,time
from pathlib import Path
from scripts import restore_qwen_cache as c
root=Path(sys.argv[1])
for kind in c.SPECS:
 raw=(root/kind/'model-cache-manifest.json').read_bytes()
 c.SPECS[kind]=(*c.SPECS[kind][:2],c.hashlib.sha256(raw).hexdigest())
c.collect=lambda *a,**k:True
output=c.worker_output()
def emit(event):
 os.write(output,(json.dumps(event)+'\\n').encode())
 if event.get('check',{}).get('name')=='asr' and 'status' in event['check']:time.sleep(30)
c.restore(argparse.Namespace(data_dir=root/'library',asr_bundle=root/'asr',aligner_bundle=root/'aligner',parts_dir=root/'parts',verify_only=False),emit)
'''
            result = check_setup.run_setup([sys.executable,'-c',code,temp], total_seconds=3,
                                          idle_seconds=90, expected_checks=17)
            self.assertEqual(result['error'], 'setup_check_timeout')
            self.assertNotIn('cleanup_error', result)
            self.assertEqual(len(result['checks']), 11)
            self.assertEqual((args.data_dir / 'models/qwen-asr/model.safetensors').read_bytes(), weights['asr'])
            self.assertFalse((args.data_dir / 'models/qwen-aligner/model.safetensors').exists())
            with open_lock(args.data_dir / 'instance.lock', 'busy', 409), open_lock(args.data_dir / 'worker.lock', 'busy', 409):
                pass
