"""Completed speech spans; reuse existing job identity and attempt ownership."""
import hashlib
import json
import math

from .storage import MediaError
from .subtitles import MAX_CUES, MAX_SUBTITLE_BYTES, validate_cues

PROFILE = 'vad-spans-v1:source-sample-offset:previous-text-200-tokens'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def validate_part(part, duration):
    try:
        if type(part) is not dict or set(part) != {'clip', 'cues'}:
            raise ValueError()
        clip = part['clip']
        if (type(clip) is not list or len(clip) != 2 or
            any(type(x) not in (float, int) or not math.isfinite(x) for x in clip) or
            not 0 <= clip[0] < clip[1] <= duration + .05):
            raise ValueError()
        cues = validate_cues(part['cues'], duration)
        if any(c['start'] < clip[0] - .05 or c['end'] > clip[1] + .05 for c in cues):
            raise ValueError()
        return {'clip': clip, 'cues': cues}
    except (ValueError, TypeError, KeyError, MediaError):
        raise MediaError('processing_checkpoint_invalid', 409) from None


def load(store, row, duration):
    with store.db() as db:
        records = db.execute('SELECT * FROM asr_spans WHERE job_id=? ORDER BY ordinal', (row['id'],)).fetchall()
    parts, until, count, size = [], 0., 0, 0
    for ordinal, record in enumerate(records):
        if record['ordinal'] != ordinal or hashlib.sha256(record['payload'].encode()).hexdigest() != record['sha256']:
            raise MediaError('processing_checkpoint_invalid', 409)
        try:
            part = validate_part(json.loads(record['payload']), duration)
        except (ValueError, TypeError):
            raise MediaError('processing_checkpoint_invalid', 409) from None
        if part['clip'][0] < until:
            raise MediaError('processing_checkpoint_invalid', 409)
        until = part['clip'][1]
        count += len(part['cues']); size += len(record['payload'].encode())
        if count > MAX_CUES or size > MAX_SUBTITLE_BYTES * 4:
            raise MediaError('processing_checkpoint_invalid', 409)
        parts.append(part)
    if len(parts) != row['asr_completed'] or until != row['asr_until']:
        raise MediaError('processing_checkpoint_invalid', 409)
    return parts


def save(store, job_id, attempt, ordinal, part, previous_until, duration):
    part = validate_part(part, duration)
    if part['clip'][0] < previous_until:
        raise MediaError('processing_checkpoint_invalid', 409)
    payload = encoded(part)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute("""UPDATE subtitle_jobs SET asr_completed=asr_completed+1,asr_until=?
            WHERE id=? AND state='running' AND attempt=? AND asr_completed=? AND asr_until=?""",
            (part['clip'][1], job_id, attempt, ordinal, previous_until)).rowcount
        if changed != 1:
            raise MediaError('processing_interrupted', 409)
        db.execute('INSERT INTO asr_spans(job_id,ordinal,payload,sha256) VALUES(?,?,?,?)',
                   (job_id, ordinal, payload, hashlib.sha256(payload.encode()).hexdigest()))
        db.commit()
    return part
