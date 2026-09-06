"""Opt-in, local title matching from explicit feedback. No watch/subtitle learning."""
from __future__ import annotations

import math
import re
import unicodedata

from .storage import MediaError

PREFERENCES = {'neutral', 'like', 'dislike', 'less'}
STOP_WORDS = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'video', 'mp4', 'webm',
              '영상', '동영상', 'episode', '시즌', '에피소드'}


def title_terms(title):
    return {word for word in re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', title).casefold())
            if len(word) > 1 and not word.isdigit() and word not in STOP_WORDS}


class Recommendations:
    def __init__(self, store):
        self.store = store

    def init(self):
        # Schema belongs to Store's versioned migration transaction.
        pass

    def preference(self, item_id):
        self.store._row(item_id)
        with self.store.db() as db:
            row = db.execute('SELECT included,preference,revision FROM item_preferences WHERE item_id=?', (item_id,)).fetchone()
        return {'included': bool(row['included']), 'preference': row['preference'], 'revision': row['revision']} if row else {
            'included': False, 'preference': 'neutral', 'revision': 0}

    def save(self, item_id, included, preference, revision):
        if (type(included) is not bool or type(preference) is not str or preference not in PREFERENCES
                or type(revision) is not int or not 0 <= revision < 2**53 - 1):
            raise MediaError('invalid_preference', 422)
        self.store._row(item_id)
        with self.store.db() as db:
            db.execute('INSERT INTO item_preferences(item_id) VALUES(?) ON CONFLICT DO NOTHING', (item_id,))
            saved = db.execute("""UPDATE item_preferences SET included=?,preference=?,revision=revision+1
                WHERE item_id=? AND revision=? RETURNING revision""",
                (int(included), preference, item_id, revision)).fetchone()
            if saved is None:
                raise MediaError('preference_changed', 409)
            db.commit()
        return {'included': included, 'preference': preference, 'revision': saved['revision']}

    def suggest(self):
        # Filter participation before collecting any title features, including seeds.
        # Existing/new imports have no preference row and are excluded by default.
        with self.store.db() as db:
            rows = db.execute("""SELECT items.id,items.title,p.preference FROM items
                JOIN item_preferences p ON p.item_id=items.id WHERE p.included=1
                ORDER BY items.created_at DESC,items.id DESC""").fetchall()
        signals = {key: set() for key in ('like', 'dislike', 'less')}
        for row in rows:
            if row['preference'] in signals:
                signals[row['preference']].update(title_terms(row['title']))
        ranked = []
        for row in rows:
            if row['preference'] != 'neutral':
                continue  # Rated items supply feedback; propose other included items.
            terms = title_terms(row['title'])
            positive = len(terms & signals['like'])
            negative = len(terms & signals['dislike']) + .5 * len(terms & signals['less'])
            score = (positive - negative) / math.sqrt(max(1, len(terms)))
            reason = 'liked_title' if score > 0 else 'lower_priority' if negative else 'explore'
            ranked.append({'id': row['id'], 'score': score, 'reason': reason,
                           'explore': not positive and not negative})
        ranked.sort(key=lambda entry: entry['score'], reverse=True)  # Stable recent-import tie order.
        selected = []
        while ranked and len(selected) < 12:
            # Reserve every fourth place for an unrelated candidate, when available.
            # Unwatched/unrated never counts as negative feedback.
            index = 0
            if len(selected) % 4 == 3:
                index = next((i for i, entry in enumerate(ranked) if entry['explore']), 0)
            entry = ranked.pop(index)
            item = self.store.item(entry['id'])
            if item['available']:
                selected.append(item | {'recommendation_reason': entry['reason']})
        return {'items': selected, 'included_count': len(rows)}
