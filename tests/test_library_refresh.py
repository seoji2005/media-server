"""Real HTTP snapshots around an import; delayed output is an isolated fixture."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from media_clarity.storage import Store
from tests.test_position_recovery import live_server


class LibraryRefreshTests(unittest.TestCase):
    def test_old_http_snapshot_can_arrive_after_new_import_without_losing_stored_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'새 보관함'
            sources=[]
            for color in ('red','blue'):
                source=Path(directory)/(color+'.mp4')
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color={color}:size=32x32:rate=1',
                    '-t','3','-c:v','libx264',str(source)],check=True,capture_output=True,timeout=30)
                sources.append(source.read_bytes())
            with live_server(root) as client:
                headers={'X-Media-Token':client.get('/api/session').json()['token'],
                         'X-Media-Filename':'same-title.mp4','Content-Type':'application/octet-stream'}
                first=client.post('/api/import',content=sources[0],headers=headers)
                self.assertEqual(first.status_code,201,first.text)
                a=first.json()['item']['id'];prefix='/api/library/'+a
                self.assertEqual(client.put(prefix+'/position',json={'position':1.25,'expected_revision':0},headers=headers).status_code,200)
                caption=client.post(prefix+'/subtitles',content=b'1\n00:00:00,500 --> 00:00:02,000\nPreserved user caption.\n',headers=headers)
                self.assertEqual(caption.status_code,201,caption.text)
                view={'audio_index':0,'selection':caption.json()['id'],'offset_ms':-500,'revision':0}
                self.assertEqual(client.put(prefix+'/caption-view',json=view,headers=headers).status_code,200)
                entered,release=threading.Event(),threading.Event()
                read=Store.list_items
                def delayed(store):
                    snapshot=read(store)
                    if not entered.is_set():
                        entered.set()
                        if not release.wait(5):raise AssertionError('fixture read delay exceeded five seconds')
                    return snapshot
                with patch.object(Store,'list_items',delayed), ThreadPoolExecutor(max_workers=1) as pool:
                    old=pool.submit(client.get,'/api/library')
                    try:
                        self.assertTrue(entered.wait(5))
                        second=client.post('/api/import',content=sources[1],headers=headers)
                        self.assertEqual(second.status_code,201,second.text)
                        b=second.json()['item']['id'];self.assertNotEqual(a,b)
                        latest=client.get('/api/library')
                        self.assertEqual({i['id'] for i in latest.json()['items']},{a,b})
                    finally:
                        release.set()
                    older=old.result(timeout=5)
                    self.assertEqual(older.status_code,200)
                    self.assertEqual([i['id'] for i in older.json()['items']],[a])
                self.assertEqual({i['id'] for i in client.get('/api/library').json()['items']},{a,b})
            with live_server(root) as client:
                self.assertEqual({i['id'] for i in client.get('/api/library').json()['items']},{a,b})
                restored=client.get(prefix).json()
                self.assertEqual((restored['position'],restored['position_revision']),(1.25,1))
                saved_view=client.get(prefix+'/subtitles').json()['view']
                self.assertEqual((saved_view['selection'],saved_view['offset_ms']),(caption.json()['id'],-500))
                for item,raw in zip((a,b),sources):
                    response=client.get(f'/api/media/{item}/content')
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(response.content,raw)
