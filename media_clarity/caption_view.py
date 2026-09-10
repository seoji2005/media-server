"""Local viewing choices, separate from immutable subtitle evidence."""
import json
import re

from .storage import MediaError


def check_offset(value):
    if type(value) is not int or not -10000 <= value <= 10000:
        raise MediaError('invalid_caption_view', 422)


def shifted(cues, duration, offset_ms):
    check_offset(offset_ms)
    if not offset_ms:
        return cues
    seconds = offset_ms / 1000
    result = []
    for cue in cues:
        start, end = max(0, cue['start'] + seconds), min(duration, cue['end'] + seconds)
        # A clipped sub-millisecond remnant must not become a zero-length VTT cue.
        if round(start * 1000) < round(end * 1000):
            result.append(cue | {'start': start, 'end': end})
    return result


class CaptionView:
    def __init__(self, store):
        self.store = store

    def media(self, item_id, audio_index):
        media = self.store._row(item_id)
        tracks = json.loads(media['audio_tracks'] or '[]')
        index = media['audio_index'] if audio_index is None else audio_index
        if type(index) is not int or not 0 <= index < max(1, len(tracks)):
            raise MediaError('invalid_audio_track', 422)
        return media, index

    def read(self, item_id, audio_index=None):
        _, index = self.media(item_id, audio_index)
        with self.store.db() as db:
            row = db.execute('SELECT selection,offset_ms,revision FROM caption_views WHERE item_id=? AND audio_index=?',
                             (item_id, index)).fetchone()
        return dict(row) if row else {'selection': None, 'offset_ms': 0, 'revision': 0}

    def save(self, item_id, audio_index, selection, offset_ms, revision):
        check_offset(offset_ms)
        if (type(revision) is not int or not 0 <= revision < 2**53 - 1
                or (selection is not None and (type(selection) is not str
                    or (selection != '' and not re.fullmatch('[a-f0-9]{32}(:transcript)?', selection))))
                or (not selection and offset_ms != 0)):
            raise MediaError('invalid_caption_view', 422)
        media, index = self.media(item_id, audio_index)
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if selection:
                track_id, _, view = selection.partition(':')
                track = db.execute('''SELECT t.source, EXISTS(SELECT 1 FROM subtitle_jobs j
                    WHERE j.id=t.job_id AND j.item_id=t.item_id AND j.input_sha=t.input_sha
                    AND j.audio_index=t.audio_index AND j.transcript IS NOT NULL
                    AND j.transcript_sha IS NOT NULL) AS has_transcript
                    FROM subtitle_tracks t WHERE t.id=? AND t.item_id=? AND t.input_sha=?''',
                    (track_id, item_id, media['sha256'])).fetchone()
                if not track or (view and (track['source'] != 'generated' or not track['has_transcript'])):
                    raise MediaError('subtitle_not_found', 404)
            db.execute('INSERT INTO caption_views(item_id,audio_index) VALUES(?,?) ON CONFLICT DO NOTHING',
                       (item_id, index))
            saved = db.execute('''UPDATE caption_views SET selection=?,offset_ms=?,revision=revision+1
                WHERE item_id=? AND audio_index=? AND revision=? RETURNING revision''',
                (selection, offset_ms, item_id, index, revision)).fetchone()
            if saved is None:
                raise MediaError('caption_view_changed', 409)
            db.commit()
        return {'selection': selection, 'offset_ms': offset_ms, 'revision': saved['revision']}
