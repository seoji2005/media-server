"""Read-only companion entry bound to this library and the original file."""
import re

from .migrations import companion_identity
from .storage import MediaError


def validate(store, item_id, value):
    fields = {'version', 'server_id', 'library_id', 'item_id', 'file_id', 'sha256'}
    if (type(value) is not dict or set(value) != fields
            or type(value['version']) is not int or value['version'] != 1
            or any(type(value[key]) is not str or not re.fullmatch(
                '[a-f0-9]{64}' if key == 'sha256' else '[a-f0-9]{32}', value[key])
                for key in fields - {'version'})):
        raise MediaError('invalid_item_entry', 422)
    with store.db() as db:
        identity = companion_identity(db)
    if (value['item_id'] != item_id
            or any(value[key] != identity[key] for key in ('server_id', 'library_id'))):
        raise MediaError('item_reference_changed', 409)
    original = store._row(item_id)
    if any(value[key] != original[key] for key in ('file_id', 'sha256')):
        raise MediaError('item_reference_changed', 409)
    store.open_verified(original).close()
    item = store.item(item_id)
    if not item['available'] and item['unavailable_reason'] != 'rendition_required':
        raise MediaError(item['unavailable_reason'], 409)
    if item['available']:
        # A ready selected audio may use different bytes/duration from the original.
        store.open_verified(store.playback_row(item_id, item['audio_index'])).close()
    return {'version': 1, 'server_id': identity['server_id'],
            'library_id': identity['library_id'], 'item': item}
