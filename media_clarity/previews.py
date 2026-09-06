"""On-demand time previews; each small image is a durable, independent checkpoint."""
import hashlib
import math
import threading
import uuid

from .storage import CHUNK, ID, MediaError, run_media

PROFILE = 'time-grid-v1'
MAX_FRAMES = 120
MAX_IMAGE = 192 * 1024
BATCH = 4


class Previews:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.closed = threading.Event()

    def close(self):
        self.closed.set()
        # At most one bounded FFmpeg frame is in flight. Finish/abort before Store closes.
        with self.lock:
            pass

    def _set(self, item_id):
        source = self.store._row(item_id)
        with self.store.db() as db:
            row = db.execute('SELECT * FROM preview_sets WHERE item_id=?',(item_id,)).fetchone()
        if row and (row['input_sha'] != source['sha256'] or row['profile'] != PROFILE):
            raise MediaError('preview_input_changed',409)
        return source, dict(row) if row else None

    def status(self, item_id):
        _, preview = self._set(item_id)
        if preview is None:
            return {'state':'empty','frames':[],'total':0,'completed':0,'failed':0}
        with self.store.db() as db:
            rows = db.execute('SELECT ordinal,time,error FROM preview_frames WHERE set_id=? ORDER BY ordinal',(preview['id'],)).fetchall()
        frames = [{'ordinal':r['ordinal'],'time':r['time'],'available':r['error'] is None,
                   'image':f"/api/library/{item_id}/previews/{preview['id']}/{r['ordinal']}.jpg" if r['error'] is None else None}
                  for r in rows]
        return {'state':'ready' if len(rows)==preview['total'] else 'partial', 'frames':frames,
                'total':preview['total'], 'completed':len(rows), 'failed':sum(r['error'] is not None for r in rows)}

    def prepare(self, item_id, retry=None):
        if not self.lock.acquire(blocking=False):
            raise MediaError('preview_busy',409)
        try:
            if self.closed.is_set():
                raise MediaError('preview_interrupted',409)
            source, preview = self._set(item_id)
            self.store.open_verified(source).close()
            if preview is None:
                if retry is not None:
                    raise MediaError('preview_not_found',404)
                metadata = self.store.probe(self.store.file_path(source))
                # Native originals retain their PTS; FFmpeg's compatible copies
                # subtract input start_time. Sample and seek in the same timeline.
                offset = 0 if metadata['preparation']=='original' else metadata['start_time']
                start = max(0,metadata['video_start']-offset)
                end = min(source['duration'], (metadata['video_duration']+metadata['start_time']-offset)
                          if metadata['video_duration'] is not None else source['duration'])
                duration = end-start
                if duration <= 0:
                    raise MediaError('preview_timing_unavailable',422)
                preview = {'id':uuid.uuid4().hex,'item_id':item_id,'input_sha':source['sha256'],
                           'duration':duration,'start':start,'seek_offset':offset,
                           'total':min(MAX_FRAMES,max(1,math.ceil(duration/10))), 'profile':PROFILE}
                with self.store.db() as db:
                    db.execute('INSERT INTO preview_sets(id,item_id,input_sha,duration,total,profile,start,seek_offset) VALUES(:id,:item_id,:input_sha,:duration,:total,:profile,:start,:seek_offset)',preview)
                    db.commit()
            with self.store.db() as db:
                done = {r['ordinal']:r['error'] for r in db.execute('SELECT ordinal,error FROM preview_frames WHERE set_id=?',(preview['id'],))}
            if retry is not None:
                if type(retry) is not int or retry not in done:
                    raise MediaError('preview_not_found',404)
                indices = [retry]
            else:
                indices = [n for n in range(preview['total']) if n not in done][:BATCH]
            for index in indices:
                if self.closed.is_set():
                    break
                stamp = preview['start']+(index+.5)*preview['duration']/preview['total']
                self.store.ensure_space(MAX_IMAGE + CHUNK)
                image, digest, error = None, None, None
                try:
                    image = run_media([
                        'ffmpeg','-v','error','-nostdin','-threads','1',
                        '-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm',
                        '-seek_timestamp','1','-ss',f"{stamp+preview['seek_offset']:.6f}",'-i',str(self.store.file_path(source)),
                        '-map','0:V:0','-an','-sn','-dn','-frames:v','1','-filter_threads','1',
                        '-vf',"scale=w='max(2,trunc(min(320,180*dar)/2)*2)':h='max(2,trunc(min(180,320/dar)/2)*2)',setsar=1",
                        '-c:v','mjpeg','-threads','1','-q:v','4','-f','image2pipe','pipe:1'],20,MAX_IMAGE)
                    if not image.startswith(b'\xff\xd8') or not image.endswith(b'\xff\xd9'):
                        raise MediaError('invalid_media',422)
                    digest = hashlib.sha256(image).hexdigest()
                except MediaError as exc:
                    if exc.code not in {'invalid_media','media_timeout'}:
                        raise
                    # A single undecodable sample does not block the rest of the grid.
                    image, error = None, 'preview_frame_unavailable'
                self.store.open_verified(source).close()
                with self.store.db() as db:
                    if retry is None:
                        db.execute('INSERT INTO preview_frames(set_id,ordinal,time,image,sha256,error) VALUES(?,?,?,?,?,?)',
                                   (preview['id'],index,stamp,image,digest,error))
                    else:
                        db.execute('UPDATE preview_frames SET image=?,sha256=?,error=? WHERE set_id=? AND ordinal=?',
                                   (image,digest,error,preview['id'],index))
                    db.commit()
            return self.status(item_id)
        finally:
            self.lock.release()

    def image(self, item_id, set_id, ordinal):
        if not ID.fullmatch(set_id) or type(ordinal) is not int or not 0 <= ordinal < MAX_FRAMES:
            raise MediaError('preview_not_found',404)
        source, preview = self._set(item_id)
        if preview is None or preview['id'] != set_id:
            raise MediaError('preview_not_found',404)
        with self.store.db() as db:
            row = db.execute('SELECT image,sha256,error FROM preview_frames WHERE set_id=? AND ordinal=?',(set_id,ordinal)).fetchone()
        if row is None or row['error'] is not None:
            raise MediaError('preview_not_found',404)
        image = row['image']
        if not image or len(image)>MAX_IMAGE or hashlib.sha256(image).hexdigest()!=row['sha256']:
            raise MediaError('preview_changed',409)
        self.store.open_verified(source).close()
        return image, row['sha256']
