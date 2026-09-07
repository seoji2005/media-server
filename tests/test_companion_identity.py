"""Proposal contract: real SQLite rollback, abrupt exit, restore and fail-closed identity."""
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from media_clarity import migrations
from media_clarity.storage import MediaError, Store


class CompanionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'library'
        self.store = Store(self.root)
        self.addCleanup(self.store.close)
        self.store.start()

    def identity(self, store=None):
        with (store or self.store).db() as db:
            return migrations.companion_identity(db)

    def legacy_fixture(self):
        # A disposable v5-schema fixture. The separate handoff HTTP test upgrades
        # a database actually created by the unmodified pinned v5 server.
        self.store.close()
        with closing(sqlite3.connect(self.root/'library.sqlite3')) as db, db:
            db.execute('DROP TABLE companion_identity')
            db.execute('PRAGMA user_version=5')

    def snapshot(self):
        with closing(sqlite3.connect(self.root/'library.sqlite3')) as db:
            return db.execute('PRAGMA user_version').fetchone()[0], list(db.iterdump())

    def test_restart_separate_library_and_stopped_copy(self):
        identity = self.identity()
        self.store.close(); self.store.start()
        self.assertEqual(self.identity(), identity)
        other = Store(Path(self.temp.name)/'other')
        try:
            other.start()
            for key in ('server_id', 'library_id'):
                self.assertNotEqual(self.identity(other)[key], identity[key])
        finally:
            other.close()
        self.store.close()
        restored = Store(Path(self.temp.name)/'restored')
        shutil.copytree(self.root, restored.root)
        try:
            restored.start()
            self.assertEqual(self.identity(restored), identity)
        finally:
            restored.close()

    def test_failure_after_insert_rolls_back_and_releases_startup_lock(self):
        self.legacy_fixture(); before = self.snapshot()
        with patch.object(migrations, 'companion_identity', side_effect=MediaError('fixture_abort', 503)):
            with self.assertRaisesRegex(MediaError, 'fixture_abort'):
                self.store.start()
        self.assertIsNone(self.store.lock_file)
        self.assertEqual(self.snapshot(), before)
        self.store.start()
        self.assertEqual(self.identity()['version'], 1)

    def test_abrupt_exit_before_commit_keeps_v5_and_retry_succeeds(self):
        self.legacy_fixture(); before = self.snapshot()
        code = '''
import os,sys
from pathlib import Path
from media_clarity import migrations
from media_clarity.storage import Store
def exit_before_commit(db):
 assert db.execute('SELECT count(*) FROM companion_identity').fetchone()[0] == 1
 os._exit(23)
migrations.companion_identity=exit_before_commit
Store(Path(sys.argv[1])).start()
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.root)],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 23)
        self.assertEqual((result.stdout, result.stderr), (b'', b''))
        self.assertEqual(self.snapshot(), before)
        self.store.start()
        self.assertEqual(self.identity()['version'], 1)

    def test_current_missing_corrupt_or_duplicate_identity_never_recreated(self):
        self.store.close()
        for statement in (
            'DELETE FROM companion_identity',
            "UPDATE companion_identity SET server_id='invalid'",
            'DROP TABLE companion_identity',
            'CREATE TABLE duplicate AS SELECT * FROM companion_identity; '
            'DROP TABLE companion_identity; ALTER TABLE duplicate RENAME TO companion_identity; '
            'INSERT INTO companion_identity SELECT * FROM companion_identity',
        ):
            with self.subTest(statement=statement.split()[0]):
                fixture = Path(self.temp.name)/'corrupt'
                shutil.copytree(self.root, fixture)
                try:
                    with closing(sqlite3.connect(fixture/'library.sqlite3')) as db:
                        db.executescript(statement); db.commit()
                        before = list(db.iterdump())
                    broken = Store(fixture)
                    try:
                        with self.assertRaises((MediaError, sqlite3.Error)):
                            broken.start()
                        self.assertIsNone(broken.lock_file)
                        with closing(sqlite3.connect(fixture/'library.sqlite3')) as db:
                            self.assertEqual(list(db.iterdump()), before)
                    finally:
                        broken.close()
                finally:
                    shutil.rmtree(fixture)

    def test_future_schema_untouched(self):
        self.store.close()
        with closing(sqlite3.connect(self.root/'library.sqlite3')) as db:
            db.execute('PRAGMA user_version=999')
        before = self.snapshot()
        with self.assertRaisesRegex(MediaError, 'database_version_newer'):
            self.store.start()
        self.assertEqual(self.snapshot(), before)

    def test_unclassified_legacy_original_cannot_validate_before_basis_change(self):
        from media_clarity.moment_entry import reference, validate
        from media_clarity.recommendations import Recommendations
        from media_clarity.renditions import prepare
        source = Path(self.temp.name)/'synthetic.mkv'
        subprocess.run(['ffmpeg','-v','error','-nostdin',
                        '-f','lavfi','-i','color=c=blue:s=160x90:r=12:d=4',
                        '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4',
                        '-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=6',
                        '-map','0:v','-map','1:a','-map','2:a','-t','6',
                        '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)],
                       check=True, capture_output=True, timeout=20)
        original = source.read_bytes()
        item = self.store.import_path(source)['item']
        recommendations = Recommendations(self.store)
        preference = recommendations.save(item['id'], True, 'neutral', 0)
        # Explicit synthetic legacy state: startup leaves classification for first
        # normal playback. This is not evidence about a historical importer's output.
        with self.store.db() as db:
            db.execute("UPDATE files SET preparation='original',audio_tracks=NULL WHERE id=?", (item['file_id'],))
            db.commit()
        row = self.store._row(item['id'])
        identity = self.identity()
        old_entry = {'version':2, 'server_id':identity['server_id'], 'library_id':identity['library_id'],
                     'item_id':item['id'], 'duration_ms':int(row['duration']*1000),
                     'timeline':{'basis':'original-file','unit':'milliseconds',
                                 'zero':'HTMLMediaElement.currentTime=0',
                                 'file_id':row['file_id'],'sha256':row['sha256']},
                     'start_ms':5000, 'end_ms':None}
        for action in (lambda: reference(self.store, recommendations, item['id']),
                       lambda: validate(self.store, recommendations, item['id'], old_entry)):
            with self.assertRaisesRegex(MediaError, 'moment_timeline_unsupported'):
                action()
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM renditions').fetchone()[0], 0)
        ready = prepare(self.store, item['id'])  # Separate, explicit normal preparation.
        self.assertGreater(item['duration'] - ready['duration'], 1.5)
        with self.assertRaisesRegex(MediaError, 'moment_timeline_unsupported'):
            reference(self.store, recommendations, item['id'])
        self.assertEqual(recommendations.preference(item['id']), preference)
        self.assertEqual(self.store.item(item['id'])['position'], 0)
        self.assertEqual(self.store.file_path(row).read_bytes(), original)
