"""One local worker, durable stage/cue checkpoints, append-only subtitle versions."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from .storage import ID, MediaError, no_symlink
from .subtitles import MAX_SUBTITLE_BYTES, parse_caption, validate_cues, webvtt, translation_units, korean_text, korean_language
from .subtitle_layout import generated_layout
from . import asr_checkpoints, gemini, qwen

TRANSLATION_WARNINGS = {'translation_truncated', 'translation_empty', 'translation_input_too_long'}
PROVIDED_PROFILE = 'provided-cues-v1'


def speech_preflight(root, profile, cloud):
    from .models import local_models
    if profile in qwen.PROFILES and cloud:
        return qwen.local_models(root, check_packages=True)
    if profile is not None:
        raise MediaError('processing_config_changed', 409)
    return local_models(root, check_packages=True, asr_only=cloud)


def source_units(transcript, profile):
    # Qwen phrases retain exact original spacing; never rejoin Japanese subwords
    # with artificial spaces or erase the new alignment's phrase boundaries.
    return [dict(c) for c in transcript] if profile in (*qwen.PROFILES, PROVIDED_PROFILE) else translation_units(transcript)


def retranslation_identity(model_sha, row):
    values = ['saved-transcript-v1',model_sha,row['source_track_id'],
              row['input_sha'],row['audio_index'],row['transcript_sha']]
    if row.get('speech_profile') in (*qwen.PROFILES, PROVIDED_PROFILE):
        values.append(row['speech_profile'])
    return hashlib.sha256(document(values).encode()).hexdigest()


def saved_transcript(db, media, track_id):
    """Verify the selected version and return its exact stored ASR bytes/hash."""
    if not ID.fullmatch(track_id):
        raise MediaError('subtitle_not_found', 404)
    track = db.execute('SELECT * FROM subtitle_tracks WHERE id=? AND item_id=?', (track_id,media['id'])).fetchone()
    if not track or track['source'] not in ('generated', 'supplied'):
        raise MediaError('subtitle_not_found', 404)
    digest = hashlib.sha256((track['cues']+(track['warnings'] or '')+(track['presentation'] or '')+(track['presentation_summary'] or '')).encode()).hexdigest()
    if track['input_sha'] != media['sha256'] or digest != track['sha256']:
        raise MediaError('subtitle_changed', 409)
    audio = json.loads(media['audio_tracks']) if media['audio_tracks'] is not None else None
    if not 0 <= track['audio_index'] < 128 or (audio is not None and track['audio_index'] >= len(audio)):
        raise MediaError('subtitle_changed', 409)
    if track['source'] == 'supplied':
        cues = validate_cues(json.loads(track['cues']), media['duration'])
        if not cues or korean_language(track['language']):
            raise MediaError('subtitle_not_found', 404)
        return {'source_track_id':track_id, 'input_sha':track['input_sha'], 'audio_index':track['audio_index'],
                'transcript':track['cues'], 'transcript_sha':hashlib.sha256(track['cues'].encode()).hexdigest(),
                'speech_profile':PROVIDED_PROFILE}
    job = db.execute('''SELECT transcript,transcript_sha,speech_profile FROM subtitle_jobs
        WHERE id=? AND item_id=? AND input_sha=? AND audio_index=?''',
        (track['job_id'],media['id'],track['input_sha'],track['audio_index'])).fetchone()
    if not job or job['transcript'] is None:
        raise MediaError('subtitle_not_found', 404)
    encoded = job['transcript'].encode()
    if len(encoded) > MAX_SUBTITLE_BYTES * 4 or hashlib.sha256(encoded).hexdigest() != job['transcript_sha']:
        raise MediaError('subtitle_changed', 409)
    try:
        cues = validate_cues(json.loads(job['transcript']), media['duration'])
        if not cues:
            raise ValueError('empty transcript')
    except (ValueError, MediaError):
        raise MediaError('subtitle_changed', 409) from None
    return {'source_track_id':track_id, 'input_sha':track['input_sha'], 'audio_index':track['audio_index'],
            'transcript':job['transcript'], 'transcript_sha':job['transcript_sha'], 'speech_profile':job['speech_profile']}


def document(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


@contextmanager
def worker_guard(root):
    """A kernel-owned worker lease outlives a server crash and Python GIL stalls."""
    path = root / 'worker.lock'
    no_symlink(path)
    stream = path.open('a+b')
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise MediaError('processing_worker_active', 409) from None
        yield
    finally:
        stream.close()


class Jobs:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.process = None
        self.active = None
        self.expected_attempt = None
        self.recovery_pending = False

    def init(self, recover=False):
        # Store initializes the complete schema before workers are started.
        if recover:
            self.recovery_pending = True
            self.recover()

    def recover(self):
        try:
            with worker_guard(self.store.root), self.store.db() as db:
                db.execute("UPDATE subtitle_jobs SET state='paused',error='processing_interrupted' WHERE state='running'")
                db.commit()
            self.recovery_pending = False
        except MediaError as exc:
            if exc.code != 'processing_worker_active':
                raise
            # Keep original watching available while an orphan releases its GPU.
            self.recovery_pending = True

    def start(self):
        self.init(recover=True)
        self.thread = threading.Thread(target=self._supervise, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        with self.lock:
            self._terminate()
        if self.thread:
            self.thread.join()
        if self.process:
            self.process.stdin.close()

    def _terminate(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def _supervise(self):
        while not self.stop.wait(.25):
            try:
                with self.lock:
                    if self.recovery_pending:
                        self.recover()
                        if self.recovery_pending:
                            continue
                    if self.process:
                        code = self.process.poll()
                        if code is None:
                            continue
                        with self.store.db() as db:
                            db.execute("UPDATE subtitle_jobs SET state='failed',error='worker_stopped' WHERE id=? AND state='running'", (self.active,))
                            db.commit()
                        self.process.stdin.close()
                        self.process, self.active = None, None
                    with self.store.db() as db:
                        row = db.execute("SELECT id FROM subtitle_jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
                    if not row or self.stop.is_set():
                        continue
                    self.active = row['id']
                    # No title, text, diagnostic traceback or model output reaches logs.
                    self.process = subprocess.Popen(
                        [sys.executable, '-m', 'media_clarity.worker', str(self.store.root), self.active],
                        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        env={**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                             'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1',
                             'ORT_DISABLE_TELEMETRY': '1'})
            except (OSError, sqlite3.Error):
                # A launch/storage failure is visible and retryable; never hot-loop.
                if self.active:
                    try:
                        self.update(self.active, state='failed', error='worker_unavailable')
                    except (OSError, sqlite3.Error):
                        pass
                self.stop.wait(1)

    def update(self, job_id, **values):
        allowed = {'state','stage','attempt','completed','total','error','config_sha','transcript','translation','transcript_sha','translation_sha'}
        if not values or not set(values) <= allowed:
            raise ValueError('invalid job fields')
        with self.store.db() as db:
            where = 'id=?'
            params = (*values.values(), job_id)
            if self.expected_attempt is not None:
                where += " AND state='running' AND attempt=?"
                params += (self.expected_attempt,)
            changed = db.execute('UPDATE subtitle_jobs SET '+','.join(f'{k}=?' for k in values)+' WHERE '+where, params).rowcount
            if self.expected_attempt is not None and changed != 1:
                raise MediaError('processing_interrupted', 409)
            db.commit()

    def row(self, job_id):
        if not ID.fullmatch(job_id):
            raise MediaError('job_not_found', 404)
        with self.store.db() as db:
            row = db.execute('SELECT * FROM subtitle_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise MediaError('job_not_found', 404)
        return dict(row)

    def status(self, item_id):
        media = self.store._row(item_id)
        with self.store.db() as db:
            jobs = db.execute('SELECT id,state,stage,attempt,completed,total,error,fallback_count,audio_index,asr_completed,asr_until,source_track_id,translation_config FROM subtitle_jobs WHERE item_id=? ORDER BY created_at DESC,id DESC', (item_id,)).fetchall()
            tracks = db.execute('''SELECT t.id,t.source,t.input_sha,t.warnings,t.presentation_summary,t.audio_index,t.language,
                EXISTS(SELECT 1 FROM subtitle_jobs j WHERE j.id=t.job_id AND j.item_id=t.item_id
                    AND j.input_sha=t.input_sha AND j.audio_index=t.audio_index
                    AND j.transcript IS NOT NULL AND j.transcript_sha IS NOT NULL) AS has_transcript
                ,(SELECT j.translation_config FROM subtitle_jobs j WHERE j.id=t.job_id) AS translation_config
                FROM subtitle_tracks t WHERE t.item_id=? ORDER BY t.created_at DESC,t.id DESC''', (item_id,)).fetchall()
        def label(config):
            return 'local' if config is None else 'gemini' if config in gemini.PROFILES else 'unknown'
        result = []
        for r in tracks:
            if r['input_sha'] != media['sha256']:
                continue
            summary = json.loads(r['presentation_summary'] or '{}')
            result.append({'id':r['id'], 'source':r['source'], 'language':r['language'], 'audio_index':r['audio_index'],
                           'provider':label(r['translation_config']),
                           'has_transcript':r['source'] == 'generated' and bool(r['has_transcript']),
                           'can_retranslate':(r['source'] == 'generated' and bool(r['has_transcript'])) or (r['source'] == 'supplied' and not korean_language(r['language'])),
                           'fallback_count':len(json.loads(r['warnings'] or '[]')),
                           'layout':summary.get('layout'), 'review_count':summary.get('review_count',0),
                           'timing_review_count':summary.get('timing_review_count',0),
                           'fast_count':summary.get('fast_count',0), 'import_notes':summary.get('import_notes')})
        public_jobs = []
        for r in jobs:
            value = dict(r)
            value['provider'] = label(value.pop('translation_config'))
            public_jobs.append(value)
        return {'jobs':public_jobs, 'tracks':result, 'gemini_configured':gemini.configured()}

    def saved_results(self, row, units, duration):
        """Read each completed batch once. Legacy prefix bytes remain untouched."""
        if row['translation'] != '[]' and hashlib.sha256(row['translation'].encode()).hexdigest() != row['translation_sha']:
            raise MediaError('processing_checkpoint_invalid', 409)
        cues = validate_cues(json.loads(row['translation']), duration)
        warnings = []
        with self.store.db() as db:
            batches = db.execute('SELECT * FROM subtitle_batches WHERE job_id=? ORDER BY first_index', (row['id'],)).fetchall()
        for batch in batches:
            if batch['first_index'] != len(cues) or hashlib.sha256(batch['payload'].encode()).hexdigest() != batch['sha256']:
                raise MediaError('processing_checkpoint_invalid', 409)
            payload = json.loads(batch['payload'])
            if type(payload) is not dict or set(payload) != {'cues','warnings'}:
                raise MediaError('processing_checkpoint_invalid', 409)
            part = validate_cues(payload['cues'], duration)
            codes = payload['warnings']
            if (not part or type(codes) is not list or len(codes) != len(part)
                    or any(c is not None and (type(c) is not str or c not in TRANSLATION_WARNINGS) for c in codes)):
                raise MediaError('processing_checkpoint_invalid', 409)
            warnings.extend({'index':len(cues)+i, 'code':code} for i,code in enumerate(codes) if code)
            cues.extend(part)
        if (len(cues) != row['completed'] or len(warnings) != row['fallback_count'] or len(cues) > len(units)
                or any((c['start'],c['end']) != (units[i]['start'],units[i]['end']) for i,c in enumerate(cues))):
            raise MediaError('processing_checkpoint_invalid', 409)
        return cues, warnings

    def checkpoint(self, job_id, first_index, cues, codes):
        payload = document({'cues':cues, 'warnings':codes})
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute("UPDATE subtitle_jobs SET completed=completed+?,fallback_count=fallback_count+? WHERE id=? AND state='running' AND attempt=? AND completed=?",
                                 (len(cues),sum(c is not None for c in codes),job_id,self.expected_attempt,first_index)).rowcount
            if changed != 1:
                raise MediaError('processing_interrupted', 409)
            db.execute('INSERT INTO subtitle_batches(job_id,first_index,payload,sha256) VALUES(?,?,?,?)',
                       (job_id,first_index,payload,hashlib.sha256(payload.encode()).hexdigest()))
            db.commit()

    def enqueue(self, item_id, force=False, audio_index=None, provider='local', speech_profile=None):
        if provider not in ('local', 'gemini'):
            raise MediaError('invalid_request', 422)
        translation_config = gemini.CONFIG if provider == 'gemini' else None
        row = self.store._row(item_id)
        index = row['audio_index'] if audio_index is None else audio_index
        tracks = json.loads(row['audio_tracks']) if row['audio_tracks'] is not None else None
        if type(index) is not int or not 0 <= index < 128 or (tracks is not None and index >= len(tracks)):
            raise MediaError('invalid_audio_track', 422)
        # Supplied Korean subtitles should avoid needless expensive ASR.
        with self.lock, self.store.db() as db:
            existing = db.execute("SELECT id,audio_index,source_track_id,translation_config,speech_profile FROM subtitle_jobs WHERE item_id=? AND state IN ('queued','running','paused')", (item_id,)).fetchone()
            if existing:
                if existing['audio_index'] != index:
                    raise MediaError('processing_audio_conflict', 409)
                if (existing['source_track_id'] or existing['translation_config'] != translation_config
                        or existing['speech_profile'] != speech_profile):
                    raise MediaError('processing_busy', 409)
                return self.row(existing['id'])['id']
            if not force and any(korean_language(t['language']) for t in db.execute(
                    'SELECT language FROM subtitle_tracks WHERE item_id=? AND audio_index=?', (item_id,index))):
                raise MediaError('subtitles_already_available', 409)
            if provider == 'gemini':
                gemini.api_key()
            speech_preflight(self.store.root, speech_profile, provider == 'gemini')
            self.store.open_verified(row).close()
            job_id = uuid.uuid4().hex
            db.execute('INSERT INTO subtitle_jobs(id,item_id,input_sha,state,audio_index,translation_config,speech_profile) VALUES(?,?,?,?,?,?,?)',
                       (job_id,item_id,row['sha256'],'queued',index,translation_config,speech_profile))
            db.commit()
            return job_id

    def _queue_translation(self, db, media, seed, translation_config=None):
        from .models import translation_identity
        cloud = gemini.provider(translation_config) == 'gemini'
        if cloud:
            gemini.api_key()
        config = retranslation_identity(gemini.identity(translation_config) if cloud else translation_identity(self.store.root), seed)
        self.store.open_verified(media).close()
        job_id = uuid.uuid4().hex
        db.execute('''INSERT INTO subtitle_jobs(id,item_id,input_sha,state,stage,audio_index,
            source_track_id,transcript,transcript_sha,config_sha,translation_config,speech_profile) VALUES(?,?,?,'queued','translation',?,?,?,?,?,?,?)''',
            (job_id,media['id'],seed['input_sha'],seed['audio_index'],seed['source_track_id'],
             seed['transcript'],seed['transcript_sha'],config,translation_config,seed['speech_profile']))
        return job_id

    def retranslate(self, item_id, track_id, provider='local'):
        if provider not in ('local', 'gemini'):
            raise MediaError('invalid_request', 422)
        translation_config = gemini.CONFIG if provider == 'gemini' else None
        media = self.store._row(item_id)
        with self.lock, self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            seed = saved_transcript(db, media, track_id)
            active = db.execute("SELECT id,source_track_id,translation_config FROM subtitle_jobs WHERE item_id=? AND state IN ('queued','running','paused')", (item_id,)).fetchone()
            if active:
                if active['source_track_id'] != track_id or active['translation_config'] != translation_config:
                    raise MediaError('processing_busy', 409)
                return active['id']
            job_id = self._queue_translation(db, media, seed, translation_config)
            db.commit()
            return job_id

    def action(self, job_id, action):
        with self.lock:
            if self.recovery_pending:
                raise MediaError('processing_worker_active', 409)
            row = self.row(job_id)
            cloud = gemini.provider(row['translation_config']) == 'gemini'
            if action == 'restart':
                if row['state'] not in ('failed','paused'):
                    raise MediaError('processing_busy', 409)
                from .models import local_models
                if not row['source_track_id']:
                    if cloud:
                        gemini.api_key()
                    speech_preflight(self.store.root, row['speech_profile'], cloud)
                media = self.store._row(row['item_id'])
                self.store.open_verified(media).close()
                with self.store.db() as db:
                    db.execute('BEGIN IMMEDIATE')
                    other = db.execute("SELECT 1 FROM subtitle_jobs WHERE item_id=? AND id<>? AND state IN ('queued','running','paused')", (row['item_id'],job_id)).fetchone()
                    if other:
                        raise MediaError('processing_busy', 409)
                    seed = saved_transcript(db, media, row['source_track_id']) if row['source_track_id'] else None
                    db.execute("UPDATE subtitle_jobs SET state='superseded' WHERE id=?", (job_id,))
                    if seed:
                        self._queue_translation(db, media, seed, row['translation_config'])
                    else:
                        db.execute('INSERT INTO subtitle_jobs(id,item_id,input_sha,state,audio_index,translation_config,speech_profile) VALUES(?,?,?,?,?,?,?)',
                                   (uuid.uuid4().hex,row['item_id'],media['sha256'],'queued',row['audio_index'],row['translation_config'],row['speech_profile']))
                    db.commit()
                return
            if action == 'pause':
                if row['state'] not in ('running','queued'):
                    return
                if self.active == job_id:
                    self._terminate()
                # A worker may have committed success before termination; retain it.
                with self.store.db() as db:
                    db.execute("UPDATE subtitle_jobs SET state='paused',error=NULL WHERE id=? AND state IN ('running','queued')", (job_id,))
                    db.commit()
            elif action == 'resume':
                if row['state'] not in ('paused','failed'):
                    return
                from .models import local_models
                if cloud:
                    gemini.api_key()
                    if not row['source_track_id']:
                        speech_preflight(self.store.root, row['speech_profile'], True)
                else:
                    local_models(self.store.root, check_packages=True, translation_only=bool(row['source_track_id']))
                with self.store.db() as db:
                    other = db.execute("SELECT 1 FROM subtitle_jobs WHERE item_id=? AND id<>? AND state IN ('queued','running','paused')", (row['item_id'],job_id)).fetchone()
                if other:
                    raise MediaError('processing_busy', 409)
                self.update(job_id, state='queued', error=None)
            else:
                raise MediaError('invalid_request', 422)

    def import_srt(self, item_id, data, audio_index=None, *, language='ko', format='srt'):
        # Preserve the historical Korean/SRT defaults; explicit imports also accept VTT.
        row = self.store._row(item_id)
        if audio_index is not None:
            self.store.playback_row(item_id, audio_index)  # Must refer to a ready playback choice.
            row['audio_index'] = audio_index
        cues, notes = parse_caption(data, row['duration'], format, language)
        if not cues:
            raise MediaError('invalid_subtitles', 422)
        self.store.open_verified(row).close()
        return self.publish(row, cues, 'supplied', None, source_srt=data,
                            presentation={'profile':'supplied-v1', 'import':notes}, language=language)

    def import_provided(self, item_id, data, file_id, file_sha256, content_sha256, format, language, timebase):
        if (timebase != 'original-file'
                or any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v)
                       for v in (file_sha256, content_sha256))):
            raise MediaError('invalid_request', 422)
        if not data or len(data) > MAX_SUBTITLE_BYTES:
            raise MediaError('subtitles_too_large', 413)
        try:
            data.decode('utf-8-sig')
        except UnicodeError:
            raise MediaError('subtitle_encoding_unsupported', 422) from None
        if hashlib.sha256(data).hexdigest() != content_sha256:
            raise MediaError('subtitle_changed', 409)
        row = self.store._row(item_id)
        if row['file_id'] != file_id or row['sha256'] != file_sha256:
            raise MediaError('processing_input_changed', 409)
        row['audio_index'] = 0  # Explicit original-file timeline, not selected rendition.
        self.store.open_verified(row).close()
        cues, notes = parse_caption(data, row['duration'], format, language)
        metadata = {'file_id':file_id, 'file_sha256':file_sha256, 'content_sha256':content_sha256,
                    'format':format, 'language':language, 'timebase':timebase, 'audio_index':0}
        identity = hashlib.sha256(document(metadata).encode()).hexdigest()
        receipt = self.publish(row, cues, 'supplied', None, source_srt=data,
            presentation={'profile':'provided-v1', 'import':notes, 'provided':metadata},
            language=language, import_identity=identity)
        self.track(item_id, receipt['id'])  # Validate a reused track too.
        return {**receipt, **metadata, 'item_id':item_id, 'ready':True, 'import_notes':notes}

    def publish(self, media, cues, source, job_id, source_srt=None, warnings=None, presentation=None,
                language='ko', import_identity=None):
        cues = validate_cues(cues, media['duration'])
        encoded = document(cues)
        if source == 'generated':
            presentation = generated_layout(cues, media['duration'], {w['index'] for w in warnings or []})
            job = self.row(job_id)
            if job['source_track_id']:
                with self.store.db() as db:
                    original = db.execute('SELECT presentation_summary FROM subtitle_tracks WHERE id=?', (job['source_track_id'],)).fetchone()
                presentation['timing_review_count'] = json.loads(original[0] or '{}').get('timing_review_count',0)
            elif job['speech_profile'] in qwen.PROFILES:
                parts = asr_checkpoints.load(self.store, job, media['duration'])
                presentation['timing_review_count'] = sum(
                    p['evidence']['boundary'] == 'forced' or any(
                        u['start'] == u['end'] or u['start'] != u['raw_start'] or u['end'] != u['raw_end']
                        or u['end'] > p['evidence'].get('recognition_end',p['clip'][1])-p['clip'][0]
                        for u in p['evidence']['units']) for p in parts)
        presentation_json = document(presentation) if presentation is not None else None
        summary_json = None
        if presentation is not None:
            issues = presentation.get('issues', [])
            # Polling status never loads/parses every version's full display cues.
            summary_json = document({'layout':presentation['profile'], 'review_count':len(issues),
                                     'fast_count':sum('reading_speed' in issue['codes'] for issue in issues),
                                     'timing_review_count':presentation.get('timing_review_count',0),
                                     'import_notes':presentation.get('import')})
        if len(encoded.encode()) > MAX_SUBTITLE_BYTES * 4:
            raise MediaError('subtitles_too_large', 422)
        if presentation_json and len(presentation_json.encode()) > MAX_SUBTITLE_BYTES * 8:
            raise MediaError('subtitles_too_large', 422)
        track_id = uuid.uuid4().hex
        warning_json = document(warnings or [])
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if import_identity is not None:
                existing = db.execute('SELECT id FROM subtitle_tracks WHERE item_id=? AND import_identity=?',
                                      (media['id'], import_identity)).fetchone()
                if existing:
                    return {'id':existing['id'], 'duplicate':True}
            digest = hashlib.sha256((encoded+warning_json+(presentation_json or '')+(summary_json or '')).encode()).hexdigest()
            db.execute('INSERT INTO subtitle_tracks(id,item_id,input_sha,job_id,source,cues,sha256,source_srt,warnings,presentation,presentation_summary,audio_index,language,import_identity) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (track_id,media['id'],media['sha256'],job_id,source,encoded,digest,source_srt,warning_json,presentation_json,summary_json,media['audio_index'],language,import_identity))
            if job_id:
                changed = db.execute("UPDATE subtitle_jobs SET state='succeeded',stage='ready',error=NULL WHERE id=? AND state='running' AND attempt=?", (job_id,self.expected_attempt)).rowcount
                if changed != 1:
                    raise MediaError('processing_interrupted', 409)
            db.commit()
        return {'id':track_id, 'duplicate':False} if import_identity is not None else track_id

    def track(self, item_id, track_id, *, transcript=False, offset_ms=0):
        from .caption_view import check_offset, shifted
        check_offset(offset_ms)
        if not ID.fullmatch(track_id):
            raise MediaError('subtitle_not_found', 404)
        media = self.store._row(item_id)
        with self.store.db() as db:
            row = db.execute('SELECT * FROM subtitle_tracks WHERE id=? AND item_id=?', (track_id,item_id)).fetchone()
        if not row:
            raise MediaError('subtitle_not_found', 404)
        if row['input_sha'] != media['sha256'] or hashlib.sha256((row['cues']+(row['warnings'] or '')+(row['presentation'] or '')+(row['presentation_summary'] or '')).encode()).hexdigest() != row['sha256']:
            raise MediaError('subtitle_changed', 409)
        self.store.open_verified(media).close()
        if transcript:
            # Read the saved ASR for this version, never the newest job or audio.
            with self.store.db() as db:
                seed = saved_transcript(db, media, track_id)
            return webvtt(shifted(validate_cues(json.loads(seed['transcript']), media['duration']), media['duration'], offset_ms))
        warning_json = row['warnings'] or '[]'
        warnings = json.loads(warning_json)
        fallback = {w['index'] for w in warnings}
        presentation = json.loads(row['presentation'] or '{}')
        if 'cues' in presentation:
            cues = validate_cues(presentation['cues'], media['duration'])
            fallback = {i for i, unit in enumerate(presentation['units']) if unit in fallback}
        else:
            cues = validate_cues(json.loads(row['cues']), media['duration'])
        # Keep fallback indices paired with their cues when shifting removes a cue
        # outside the video. Only this response changes; canonical rows stay intact.
        adjusted = shifted([cue | {'fallback': i in fallback} for i, cue in enumerate(cues)], media['duration'], offset_ms)
        return webvtt(adjusted, {i for i, cue in enumerate(adjusted) if cue['fallback']})


def execute(store, job_id, backend_factory=None):
    """Serialize actual workers, including survivors of a crashed parent."""
    with worker_guard(store.root):
        _execute(store, job_id, backend_factory)


def translate_chunk(backend, units, neighbors=None, previous=None):
    """Only known content failures use marked source text; runtime/storage errors stop."""
    results = [None] * len(units)
    foreign = [i for i,cue in enumerate(units) if not korean_text(cue['text'])]
    if foreign:
        texts = [units[i]['text'] for i in foreign]
        if hasattr(backend, 'translate_context'):
            context = [neighbors[i] for i in foreign]
            values = (backend.translate_context(texts, context, previous=previous)
                      if previous is not None else backend.translate_context(texts, context))
        elif hasattr(backend, 'translate_many'):
            values = backend.translate_many(texts)
        else:
            values = []
            for text in texts:
                try:
                    values.append(backend.translate(text))
                except MediaError as exc:
                    if exc.code not in TRANSLATION_WARNINGS:
                        raise
                    values.append(exc)
        if len(values) != len(foreign):
            raise MediaError('processing_failed', 500)
        for i, value in zip(foreign, values):
            # Model output is plain text, but MADLAD sometimes emits HTML entities.
            # Decode once before validation; webvtt() still escapes all markup.
            # Source passthrough/fallback text never takes this path.
            results[i] = html.unescape(value) if isinstance(value, str) and not hasattr(backend, 'translate_context') else value
    cues, codes = [], []
    for index, (unit, value) in enumerate(zip(units, results)):
        code = None
        if isinstance(value, MediaError):
            if value.code not in TRANSLATION_WARNINGS:
                raise value
            code = value.code
        elif index in foreign and (not isinstance(value, str) or not value.strip()):
            code = 'translation_empty'
        elif isinstance(value, str) and (len(value) > 4000 or any(ord(c) < 32 and c not in '\n\t' for c in value) or '\x7f' in value):
            code = 'translation_truncated'
        cues.append({**unit, 'text':unit['text'] if code or value is None else value})
        codes.append(code)
    return cues, codes


def _execute(store, job_id, backend_factory):
    """The parent keeps the Store lock; this child keeps worker_guard throughout."""
    from .models import LocalModels
    jobs = Jobs(store)
    with store.db() as db:
        claimed = db.execute("UPDATE subtitle_jobs SET state='running',attempt=attempt+1,error=NULL WHERE id=? AND state='queued' RETURNING attempt", (job_id,)).fetchone()
        db.commit()
    if claimed is None:
        return
    jobs.expected_attempt = claimed['attempt']
    backend = speech = None
    try:
        row = jobs.row(job_id)
        if row['attempt'] != jobs.expected_attempt or row['state'] != 'running':
            return
        media = store._row(row['item_id'])
        media['audio_index'] = row['audio_index']  # Frozen job input, independent of current watching.
        if media['sha256'] != row['input_sha']:
            raise MediaError('processing_input_changed', 409)
        store.open_verified(media).close()
        if row['source_track_id']:
            with store.db() as db:
                seed = saved_transcript(db, media, row['source_track_id'])
            if any(row[k] != seed[k] for k in seed) or row['asr_completed'] or row['asr_until']:
                raise MediaError('processing_checkpoint_invalid', 409)
        cloud = gemini.provider(row['translation_config']) == 'gemini'
        backend = gemini.Gemini(row['translation_config']) if cloud else (
            backend_factory(store.root) if backend_factory else LocalModels(store.root, translation_only=bool(row['source_track_id'])))
        if (row['speech_profile'] not in (None, *qwen.PROFILES, PROVIDED_PROFILE)
                or (row['speech_profile'] == PROVIDED_PROFILE and not row['source_track_id'])
                or (row['speech_profile'] and not cloud)):
            raise MediaError('processing_config_changed', 409)
        speech = (backend_factory(store.root) if backend_factory else
                  qwen.QwenSpeech(store.root) if row['speech_profile'] == qwen.PROFILE else
                  qwen.QwenSpeech(store.root, profile=qwen.LEGACY_PROFILE) if row['speech_profile'] == qwen.LEGACY_PROFILE else
                  LocalModels(store.root, asr_only=True)) if cloud and not row['source_track_id'] else backend
        def input_identity():
            value = backend.identity()
            if row['source_track_id']:
                return retranslation_identity(value, row)
            if cloud:
                value = hashlib.sha256(document(['local-asr-gemini-v1',speech.identity(),value]).encode()).hexdigest()
            # Keep completed legacy transcripts resumable; only new span-based ASR
            # includes this profile. Saved spans retain it during translation too.
            if hasattr(speech, 'transcribe_parts') and (row['transcript'] is None or row['asr_completed']):
                value = hashlib.sha256(document([value,speech.asr_profile]).encode()).hexdigest()
            timing = getattr(speech, 'audio_timing', None)
            # A saved pre-upgrade transcript needs no re-decode; keep its original
            # timing and model identity. New decodes include the timestamp policy.
            if not row['audio_index'] and (timing is None or (row['transcript'] is not None and row['config_sha'] == value)):
                return value
            return hashlib.sha256(document([value,row['audio_index'],timing]).encode()).hexdigest()
        identity = input_identity()
        saved_asr = asr_checkpoints.load(store, row, media['duration'])
        for part in saved_asr:
            if row['speech_profile'] in qwen.PROFILES and part.get('evidence', {}).get('profile') != row['speech_profile']:
                raise MediaError('processing_checkpoint_invalid', 409)
            if part.get('error'):
                raise MediaError(part['error'], 422)
        if row['source_track_id'] and saved_asr:
            raise MediaError('processing_checkpoint_invalid', 409)
        has_checkpoint = row['transcript'] is not None or row['translation'] != '[]' or row['completed'] or row['total'] or saved_asr
        if has_checkpoint and not row['config_sha']:
            raise MediaError('processing_checkpoint_invalid', 409)
        if row['config_sha'] and row['config_sha'] != identity:
            raise MediaError('processing_config_changed', 409)
        if row['transcript'] is None and (row['translation'] != '[]' or row['total']):
            raise MediaError('processing_checkpoint_invalid', 409)
        jobs.update(job_id, config_sha=identity)
        if row['transcript'] is None:
            jobs.update(job_id, stage='asr')
            verified = store.open_verified(media)
            try:
                # FFmpeg reads the app-owned original without another video copy.
                # Revalidate after decode and before publishing any ready result.
                if hasattr(speech, 'transcribe_parts'):
                    transcript = [c for part in saved_asr for c in part['cues']]
                    size = sum(len(document(p).encode()) for p in saved_asr)
                    until = row['asr_until']
                    parts = speech.transcribe_parts(store.file_path(media), media['duration'], row['audio_index'], saved_asr)
                    try:
                        for ordinal, part in enumerate(parts, len(saved_asr)):
                            part = asr_checkpoints.validate_part(part, media['duration'])
                            if row['speech_profile'] in qwen.PROFILES and part.get('evidence', {}).get('profile') != row['speech_profile']:
                                raise MediaError('processing_checkpoint_invalid', 409)
                            size += len(document(part).encode())
                            if len(transcript) + len(part['cues']) > asr_checkpoints.MAX_CUES or size > MAX_SUBTITLE_BYTES * 4:
                                raise MediaError('subtitles_too_large', 422)
                            part = asr_checkpoints.save(store, job_id, jobs.expected_attempt, ordinal, part, until, media['duration'])
                            if part.get('error'):
                                raise MediaError(part['error'], 422)
                            until = part['clip'][1]
                            transcript.extend(part['cues'])
                    finally:
                        parts.close()
                    transcript = validate_cues(transcript, media['duration'])
                else:
                    if saved_asr:
                        raise MediaError('processing_config_changed', 409)
                    transcript = validate_cues(speech.transcribe(store.file_path(media), media['duration'], row['audio_index']), media['duration'])
            finally:
                verified.close()
            store.open_verified(media).close()
            if not transcript:
                raise MediaError('no_speech_detected', 422)
            encoded = document(transcript)
            if len(encoded.encode()) > MAX_SUBTITLE_BYTES * 4:
                raise MediaError('subtitles_too_large', 422)
            jobs.update(job_id, transcript=encoded, transcript_sha=hashlib.sha256(encoded.encode()).hexdigest(), total=len(source_units(transcript, row['speech_profile'])), stage='translation')
        else:
            if hashlib.sha256(row['transcript'].encode()).hexdigest() != row['transcript_sha']:
                raise MediaError('processing_checkpoint_invalid', 409)
            transcript = validate_cues(json.loads(row['transcript']), media['duration'])
            if saved_asr and transcript != [c for part in saved_asr for c in part['cues']]:
                raise MediaError('processing_checkpoint_invalid', 409)
        units = source_units(transcript, row['speech_profile'])
        translated, warnings = jobs.saved_results(row, units, media['duration'])
        jobs.update(job_id, stage='translation', total=len(units))
        batch_size = min(8 if cloud else 2, max(1, getattr(backend, 'batch_size', 1)))
        checkpoint_size = min(20, max(1, getattr(backend, 'checkpoint_size', 1)))
        saved = len(translated); pending_cues, pending_codes = [], []
        encoded_bytes = sum(len(document(c).encode())+1 for c in translated)
        last_save = time.monotonic()
        try:
            for start in range(saved, len(units), batch_size):
                # Only dialogue leaves the worker. IDs, timing, paths and media stay local.
                neighbors = [(units[i-1]['text'][-400:] if i else '',
                              units[i+1]['text'][:400] if i+1 < len(units) else '')
                             for i in range(start, min(start+batch_size, len(units)))] if cloud else None
                # Rebuild continuity from the verified prefix, including after a
                # process restart. No mutable backend conversation or other track.
                previous = ([{'source':units[i]['text'], 'translation':translated[i]['text']}
                             for i in range(max(0, start-backend.previous_units), start)]
                            if cloud and backend.previous_units else None)
                part, codes = translate_chunk(backend, units[start:start+batch_size], neighbors, previous)
                part = validate_cues(part, media['duration'])
                encoded_bytes += sum(len(document(c).encode())+1 for c in part)
                if encoded_bytes + 2 > MAX_SUBTITLE_BYTES * 4:
                    raise MediaError('subtitles_too_large', 422)
                warnings.extend({'index':len(translated)+i,'code':code} for i,code in enumerate(codes) if code)
                translated.extend(part);pending_cues.extend(part);pending_codes.extend(codes)
                if len(pending_cues) >= checkpoint_size or time.monotonic()-last_save >= 5:
                    jobs.checkpoint(job_id,saved,pending_cues,pending_codes)
                    saved += len(pending_cues);pending_cues, pending_codes = [], []
                    last_save = time.monotonic()
        finally:
            # Preserve completed outputs on a runtime failure; hard kill loses at most 20 units.
            if pending_cues:
                jobs.checkpoint(job_id,saved,pending_cues,pending_codes)
        if identity != input_identity():
            raise MediaError('processing_config_changed', 409)
        store.open_verified(media).close()
        jobs.publish(media, translated, 'generated', job_id, warnings=warnings)
    except MediaError as exc:
        try:
            jobs.update(job_id, state='failed', error=exc.code)
        except MediaError:
            pass  # A newer attempt owns the row; never overwrite its state.
    except Exception:
        try:
            jobs.update(job_id, state='failed', error='processing_failed')
        except MediaError:
            pass
    finally:
        if speech is not None and speech is not backend:
            speech.close()
        if backend is not None:
            backend.close()
