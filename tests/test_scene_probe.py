import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.probe_scene_retrieval import load_manifest, model_files, rank_results

ROOT = Path(__file__).resolve().parents[1]


class SceneProbeTests(unittest.TestCase):
    def test_ranking_multiple_relevant_and_absent_queries(self):
        frames = [{'id': 'a', 'time': 1}, {'id': 'b', 'time': 2}, {'id': 'c', 'time': 3}]
        queries = [{'id': 'ko', 'language': 'ko', 'relevant': ['b', 'c']},
                   {'id': 'none', 'language': 'ko', 'relevant': []},
                   {'id': 'en', 'language': 'en', 'relevant': ['c']}]
        rows, summary = rank_results(frames, queries, [[.9, .8, .7], [.5, .5, .5], [.1, .2, .8]])
        self.assertEqual(rows[0]['rank'], 2)
        self.assertEqual(rows[1]['rank'], None)
        self.assertEqual([r['id'] for r in rows[1]['top']], ['a', 'b', 'c'])
        self.assertEqual(summary['ko'], {'positive_queries': 1, 'absent_queries': 1, 'hit_at_1': 0, 'hit_at_3': 1})
        self.assertEqual(summary['en']['hit_at_1'], 1)
        for scores in ([[float('nan'), 0, 0]], [[1, 2]]):
            with self.assertRaisesRegex(ValueError, 'invalid_scores'):
                rank_results(frames, queries[:1], scores)

    def test_manifest_requires_existing_evidence_and_unique_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a.jpg').write_bytes(b'fixture')
            manifest = {'frames': [{'id': 'a', 'time': 1, 'image': 'a.jpg'}, {'id': 'b', 'time': 2, 'image': 'a.jpg'}],
                        'queries': [{'id': 'q', 'language': 'ko', 'text': '장면', 'relevant': ['a']}]}
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest))
            self.assertEqual(load_manifest(path), manifest)
            for relevant in (['missing'], ['a', 'a']):
                manifest['queries'][0]['relevant'] = relevant
                path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'invalid_manifest'): load_manifest(path)
            manifest['queries'][0]['relevant'] = ['a']
            manifest['frames'][1]['id'] = 'a'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'invalid_manifest'): load_manifest(path)

    def test_cli_errors_do_not_disclose_supplied_paths_or_content(self):
        with tempfile.TemporaryDirectory(prefix='private-scene-') as folder:
            root = Path(folder);path = root / 'private-query.json';path.write_text('sensitive title invalid JSON')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/probe_scene_retrieval.py'),
                                     '--model', str(root / 'model'), '--revision', 'a' * 40,
                                     '--manifest', str(path), '--output', str(root / 'result')],capture_output=True,text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, '')
            self.assertEqual(json.loads(result.stdout), {'error': 'scene_probe_failed'})
            self.assertFalse((root / 'result').exists())

    def test_network_audit_denies_outbound_request(self):
        result = subprocess.run([sys.executable, '-c',
            "from scripts.probe_scene_retrieval import offline; attempts=offline(); import socket; "
            "\ntry: socket.create_connection(('example.com',443),timeout=.1)"
            "\nexcept RuntimeError as e: assert str(e)=='network_disabled'"
            "\nelse: raise AssertionError('network permitted')"
            "\nassert attempts"],cwd=ROOT,capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'')

    def test_local_model_description_distinguishes_changed_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);config = root / 'config.json';config.write_bytes(b'config one')
            before = model_files(root)
            config.write_bytes(b'config two')
            after = model_files(root)
            self.assertNotEqual(before[0]['sha256'], after[0]['sha256'])
            self.assertEqual(after[0]['name'], 'config.json')
            self.assertNotIn(str(root), json.dumps(after))
