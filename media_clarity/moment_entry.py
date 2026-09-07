"""Proposed original-file entry only; no mapping to renditions or automatic history write."""
import math

from .storage import MediaError
from .migrations import companion_identity


def reference(store, recommendations, item_id):
    preference = recommendations.preference(item_id)
    if not preference['included']:
        raise MediaError('moment_not_available', 404)
    row = store._row(item_id)
    if row['preparation'] != 'original' or row['audio_index'] != 0 or row['audio_tracks'] is None:
        raise MediaError('moment_timeline_unsupported', 409)
    # Verify the immutable source identity before returning a time reference.
    store.open_verified(row).close()
    latest = recommendations.preference(item_id)
    if not latest['included']:
        raise MediaError('moment_not_available', 404)
    if latest['revision'] != preference['revision']:
        raise MediaError('moment_reference_changed', 409)
    with store.db() as db:
        identity = companion_identity(db)
    return {'version': 2, 'server_id': identity['server_id'], 'library_id': identity['library_id'],
            'item_id': item_id,
            'timeline': {'basis': 'original-file', 'unit': 'milliseconds',
                         'zero': 'HTMLMediaElement.currentTime=0',
                         'file_id': row['file_id'], 'sha256': row['sha256']},
            'duration_ms': math.floor(row['duration'] * 1000)}


def validate(store, recommendations, item_id, value):
    if (type(value) is not dict or set(value) != {'version', 'server_id', 'library_id', 'item_id', 'timeline', 'duration_ms', 'start_ms', 'end_ms'}
            or type(value['version']) is not int or type(value['duration_ms']) is not int
            or type(value['start_ms']) is not int
            or (value['end_ms'] is not None and type(value['end_ms']) is not int)):
        raise MediaError('invalid_moment_entry', 422)
    latest = reference(store, recommendations, item_id)
    if any(value[key] != latest[key] for key in latest):
        raise MediaError('moment_reference_changed', 409)
    if (not 0 <= value['start_ms'] < latest['duration_ms']
            or (value['end_ms'] is not None and not value['start_ms'] < value['end_ms'] <= latest['duration_ms'])):
        raise MediaError('invalid_moment_entry', 422)
    return {'start_ms': value['start_ms'], 'end_ms': value['end_ms']}
