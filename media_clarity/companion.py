"""Small, opt-in companion library reads; no access to another app's database."""
import base64
import binascii
import json
import re

from .storage import ID, MediaError


def cursor_value(value):
    if value is None:
        return None
    try:
        if not isinstance(value, str) or len(value) > 256 or not re.fullmatch('[A-Za-z0-9_-]+', value):
            raise ValueError()
        key = json.loads(base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)))
        if (type(key) is not list or len(key) != 2
                or not isinstance(key[0], str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', key[0])
                or not isinstance(key[1], str) or not ID.fullmatch(key[1])):
            raise ValueError()
        return key
    except (ValueError, UnicodeError, binascii.Error):
        raise MediaError('invalid_request', 422) from None


SELECT = '''SELECT i.id,i.file_id,i.title,i.created_at,f.sha256,f.duration,
    f.preparation,p.revision,p.preference FROM items i
    JOIN files f ON f.id=i.file_id JOIN item_preferences p ON p.item_id=i.id
    WHERE p.included=1'''


def entry(row):
    return {**dict(row), 'included':True, 'timebase':'original-file', 'audio_index':0}


def page(store, limit=20, cursor=None):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise MediaError('invalid_request', 422)
    key = cursor_value(cursor)
    clause, params = (' AND (i.created_at,i.id) < (?,?)', key) if key else ('', [])
    with store.db() as db:
        rows = db.execute(SELECT + clause + ' ORDER BY i.created_at DESC,i.id DESC LIMIT ?',
                          [*params, limit+1]).fetchall()
    selected = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = selected[-1]
        raw = json.dumps([last['created_at'], last['id']], separators=(',', ':')).encode()
        next_cursor = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    return {'items':[entry(r) for r in selected], 'next_cursor':next_cursor}


def lookup(store, ids):
    if (type(ids) is not list or not 1 <= len(ids) <= 20
            or any(not isinstance(i, str) or not ID.fullmatch(i) for i in ids)
            or len(set(ids)) != len(ids)):
        raise MediaError('invalid_request', 422)
    with store.db() as db:
        rows = db.execute(SELECT + ' AND i.id IN (' + ','.join('?' for _ in ids) + ')', ids).fetchall()
    found = {r['id']:entry(r) for r in rows}
    # Excluded and missing IDs share one result, without title or preference leakage.
    return {'items':[found[i] for i in ids if i in found], 'unavailable':[i for i in ids if i not in found]}
