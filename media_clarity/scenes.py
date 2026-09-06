"""Selected-video visual candidates from saved previews; queries are never stored."""
import hashlib
from contextlib import suppress
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading

from .previews import Previews, MAX_FRAMES, MAX_IMAGE
from .storage import MediaError, no_symlink

PROFILE = 'siglip2-base-224-v1:rgb-preview:slow:lowercase64:float32'
DIM = 768
BATCH = 4
PER_REQUEST = 20
FILES = ('config.json', 'model.safetensors', 'preprocessor_config.json',
         'tokenizer.json', 'tokenizer.model', 'tokenizer_config.json', 'special_tokens_map.json')
ERRORS = {'scene_model_missing', 'scene_runtime_missing', 'scene_model_changed',
          'scene_previews_required', 'scene_index_required', 'scene_index_changed',
          'scene_failed', 'scene_timeout', 'scene_query_invalid', 'scene_query_too_long',
          'scene_network_disabled', 'model_cuda_unavailable', 'model_settings_invalid', 'processing_worker_active',
          'preview_changed', 'preview_input_changed', 'managed_file_changed',
          'unsafe_storage', 'storage_unavailable', 'insufficient_space', 'item_not_found'}


def query_text(value):
    if type(value) is not str or not 1 <= len(value.strip()) <= 200 or any(not c.isprintable() for c in value):
        raise MediaError('scene_query_invalid', 422)
    return value.strip()


def identity(root):
    from .models import device_configuration
    path = root / 'models' / 'scene'
    no_symlink(path)
    entries = []
    for name in FILES:
        file = path / name
        no_symlink(file)
        if not file.is_file():
            raise MediaError('scene_model_missing', 503)
        stat = file.stat()
        if stat.st_size > (2 * 1024**3 if name.endswith('.safetensors') else 64 * 1024**2):
            raise MediaError('scene_model_changed', 503)
        entries.append((name, stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino,
                        hashlib.sha256(file.read_bytes()).hexdigest() if stat.st_size <= 65536 else None))
    try:
        packages = [importlib.metadata.version(n) for n in ('torch','transformers','Pillow','sentencepiece')]
    except importlib.metadata.PackageNotFoundError:
        raise MediaError('scene_runtime_missing', 503) from None
    device = device_configuration(root)['device']
    # Local invalidation identity, not proof of the downloaded weight revision.
    data = json.dumps([PROFILE,str(path),entries,packages,device],separators=(',',':'))
    return path, device, hashlib.sha256(data.encode()).hexdigest()


def snapshot(store, item_id):
    source, preview = Previews(store)._set(item_id)
    if preview is None:
        raise MediaError('scene_previews_required', 409)
    with store.db() as db:
        rows = [dict(r) for r in db.execute('SELECT * FROM preview_frames WHERE set_id=? ORDER BY ordinal',(preview['id'],))]
    if len(rows) != preview['total'] or not 1 <= len(rows) <= MAX_FRAMES:
        raise MediaError('scene_previews_required', 409)
    usable = [r for r in rows if r['error'] is None]
    if not usable:
        raise MediaError('scene_previews_required', 409)
    for row in usable:
        raw = row['image']
        if (not raw or len(raw) > MAX_IMAGE or hashlib.sha256(raw).hexdigest() != row['sha256']
                or not math.isfinite(row['time']) or not 0 <= row['time'] < source['duration']):
            raise MediaError('preview_changed', 409)
    return source, preview, usable


def unpack(raw):
    if not isinstance(raw, bytes) or len(raw) != 4 * DIM:
        raise MediaError('scene_index_changed', 409)
    values = struct.unpack('<'+'f'*DIM,raw)
    if not all(math.isfinite(x) for x in values) or not .99 <= sum(x*x for x in values) <= 1.01:
        raise MediaError('scene_index_changed', 409)
    return values


def saved(store, preview, frames, model_sha):
    with store.db() as db:
        rows = {r['ordinal']:r for r in db.execute('SELECT * FROM scene_vectors WHERE set_id=?',(preview['id'],))}
    result = {}
    for frame in frames:
        row = rows.get(frame['ordinal'])
        if row is None or row['model_sha'] != model_sha or row['frame_sha'] != frame['sha256']:
            continue
        if hashlib.sha256(row['vector']).hexdigest() != row['sha256']:
            continue  # Rebuild just this derived vector on the next prepare.
        try:
            result[frame['ordinal']] = unpack(row['vector'])
        except MediaError:
            pass
    return result


def status(store, item_id):
    _, _, model_sha = identity(store.root)
    _, preview, frames = snapshot(store,item_id)
    done = saved(store,preview,frames,model_sha)
    return {'state':'ready' if len(done)==len(frames) else 'partial',
            'completed':len(done), 'total':len(frames), 'sampled':preview['total']}


def offline():
    from .models import require_private_runtime
    require_private_runtime()
    for name in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK'):
        os.environ[name] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    def audit(event, args):
        if event in ('socket.connect','socket.getaddrinfo','socket.sendto'):
            raise MediaError('scene_network_disabled',503)
    sys.addaudithook(audit)


class Encoder:
    def __init__(self, path, device):
        import torch
        from transformers import SiglipModel, SiglipProcessor, SiglipConfig
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        if device == 'cuda' and not torch.cuda.is_available():
            raise MediaError('model_cuda_unavailable',503)
        config = SiglipConfig.from_pretrained(path, local_files_only=True)
        if (config.vision_config.hidden_size != DIM or config.text_config.hidden_size != DIM
                or config.vision_config.image_size != 224 or config.vision_config.patch_size != 16):
            raise MediaError('scene_model_changed',503)
        self.device, self.torch = device, torch
        self.model = SiglipModel.from_pretrained(path,config=config,local_files_only=True,
                                               use_safetensors=True,torch_dtype=torch.float32).to(device).eval()
        self.processor = SiglipProcessor.from_pretrained(path,local_files_only=True,use_fast=False)

    def images(self, frames):
        from PIL import Image
        pictures = []
        for frame in frames:
            with Image.open(io.BytesIO(frame['image'])) as picture:
                if not 0 < picture.width <= 320 or not 0 < picture.height <= 180:
                    raise MediaError('preview_changed',409)
                pictures.append(picture.convert('RGB'))
        with self.torch.inference_mode():
            inputs = self.processor(images=pictures,return_tensors='pt').to(self.device)
            return self.torch.nn.functional.normalize(self.model.get_image_features(**inputs),dim=-1).cpu().tolist()

    def text(self, query):
        tokens = self.processor(text=[query.lower()],padding='max_length',max_length=64,
                                truncation=False,return_tensors='pt')
        if tokens['input_ids'].shape[-1] > 64:
            raise MediaError('scene_query_too_long',422)
        with self.torch.inference_mode():
            return self.torch.nn.functional.normalize(self.model.get_text_features(**tokens.to(self.device)),dim=-1).cpu().tolist()[0]


def execute(store, item_id, query=None, encoder_type=Encoder):
    source, preview, frames = snapshot(store,item_id)
    path, device, model_sha = identity(store.root)
    vectors = saved(store,preview,frames,model_sha)
    if query is not None:
        query = query_text(query)
        if len(vectors) != len(frames):
            raise MediaError('scene_index_required',409)
    pending = [f for f in frames if f['ordinal'] not in vectors][:PER_REQUEST]
    if query is None and not pending:
        return status(store,item_id)
    # Analyze the already saved/hashed images, without rescanning a long video
    # in every short-lived model process. Image serving keeps its existing checks.
    encoder = encoder_type(path,device)
    if query is None:
        for first in range(0,len(pending),BATCH):
            batch = pending[first:first+BATCH]
            encoded = encoder.images(batch)
            if len(encoded) != len(batch):
                raise MediaError('scene_failed',503)
            if identity(store.root)[2] != model_sha:
                raise MediaError('scene_model_changed',409)
            store.ensure_space(256*1024)
            with store.db() as db:
                for frame, vector in zip(batch,encoded):
                    raw = struct.pack('<'+'f'*DIM,*vector)
                    unpack(raw)
                    current = db.execute('SELECT sha256,error FROM preview_frames WHERE set_id=? AND ordinal=?',
                                         (preview['id'],frame['ordinal'])).fetchone()
                    if current is None or current['error'] is not None or current['sha256'] != frame['sha256']:
                        raise MediaError('preview_changed',409)
                    db.execute('INSERT OR REPLACE INTO scene_vectors VALUES(?,?,?,?,?,?)',
                               (preview['id'],frame['ordinal'],model_sha,frame['sha256'],raw,hashlib.sha256(raw).hexdigest()))
                db.commit()  # Four-image checkpoint; failure keeps earlier batches.
        return status(store,item_id)
    text = encoder.text(query)
    unpack(struct.pack('<'+'f'*DIM,*text))
    if identity(store.root)[2] != model_sha:
        raise MediaError('scene_model_changed',409)
    # Discard results if a saved preview changed while the text model was running.
    _, latest, current = snapshot(store,item_id)
    if latest != preview or [(f['ordinal'],f['sha256'],f['time']) for f in current] != [(f['ordinal'],f['sha256'],f['time']) for f in frames]:
        raise MediaError('preview_changed',409)
    scores = {f['ordinal']:sum(a*b for a,b in zip(text,vectors[f['ordinal']])) for f in frames}
    ranked = sorted(frames,key=lambda f:(-scores[f['ordinal']],f['ordinal']))[:5]
    return {'sampled':preview['total'], 'searched':len(frames), 'candidates':[
        {'ordinal':f['ordinal'],'time':f['time'],
         'image':f"/api/library/{item_id}/previews/{preview['id']}/{f['ordinal']}.jpg"} for f in ranked]}


class Scenes:
    """One bounded child shares the subtitle lease. Watching remains independent."""
    def __init__(self, store, jobs):
        self.store, self.jobs = store, jobs
        self.lock = threading.Lock()
        self.closed = False
        self.process = None

    def close(self):
        with self.lock:
            self.closed = True
            if self.process and self.process.poll() is None:
                self.process.kill(); self.process.wait()

    def run(self, item_id, query=None, timeout=120):
        if query is not None:
            query = query_text(query)
        self.store._row(item_id)
        if not self.jobs.lock.acquire(blocking=False):
            raise MediaError('processing_worker_active',409)
        process = None
        try:
            if self.jobs.process and self.jobs.process.poll() is None:
                raise MediaError('processing_worker_active',409)
            with self.lock:
                if self.closed:
                    raise MediaError('scene_failed',503)
                process = self.process = subprocess.Popen(
                    [sys.executable,'-m','media_clarity.scenes',str(self.store.root),item_id],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            process.stdin.write(json.dumps({'query':query},ensure_ascii=False).encode()+b'\n');process.stdin.flush()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
                raise MediaError('scene_timeout',503) from None
            raw = process.stdout.read(8193)
            if process.returncode or len(raw)>8192:
                raise MediaError('scene_failed',503)
            result = json.loads(raw)
            if 'error' in result:
                code = result['error'] if result['error'] in ERRORS else 'scene_failed'
                raise MediaError(code,422 if code in {'scene_query_invalid','scene_query_too_long'} else 409)
            return result
        except (OSError,ValueError):
            raise MediaError('scene_failed',503) from None
        finally:
            try:
                if process:
                    try:
                        if process.poll() is None:
                            process.kill();process.wait()
                    finally:
                        for stream in (process.stdin,process.stdout):
                            # close() may retry a buffered write to an already dead
                            # child. That must never retain the supervisor's lock.
                            with suppress(OSError):
                                stream.close()
            finally:
                with self.lock:
                    self.process = None
                self.jobs.lock.release()


def main():
    output = os.dup(1)
    with open(os.devnull,'wb') as quiet:
        os.dup2(quiet.fileno(),1);os.dup2(quiet.fileno(),2)
    def finish(result):
        os.write(output,json.dumps(result,separators=(',',':'),allow_nan=False).encode())
        os._exit(0)  # Release lease only with the native model process.
    try:
        payload = json.loads(sys.stdin.buffer.readline(2049))
        def parent_gone():
            os.read(sys.stdin.fileno(),1);os._exit(1)
        threading.Thread(target=parent_gone,daemon=True).start()
        offline()
        from .jobs import worker_guard
        from .storage import Store
        store = Store(Path(sys.argv[1]))
        with worker_guard(store.root):
            finish(execute(store,sys.argv[2],payload['query']))
    except Exception as exc:
        finish({'error':exc.code if isinstance(exc,MediaError) and exc.code in ERRORS else 'scene_failed'})


if __name__ == '__main__':
    main()
