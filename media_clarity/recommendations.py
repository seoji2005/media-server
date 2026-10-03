"""Opt-in, local title matching from explicit feedback. No watch/subtitle learning."""
from __future__ import annotations

import math
import re
import unicodedata

from .storage import MediaError

PREFERENCES = {'neutral', 'like', 'dislike', 'less'}
STOP_WORDS = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'video', 'mp4', 'webm',
              '영상', '동영상', 'episode', '시즌', '에피소드'}
PARTICLE_ENDINGS = ('에서', '에게', '으로', '은', '는', '을', '를')
CJK_RUNS = re.compile('[\u3400-\u4dbf\u4e00-\u9fff々]{2,}|[ァ-ヺー]{2,}')


def title_terms(title):
    return {word for word in re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', title).casefold())
            if len(word) > 1 and not word.isdigit() and word not in STOP_WORDS}


def term_aliases(word):
    values = {word}
    if re.fullmatch('[가-힣]+', word):
        for ending in PARTICLE_ENDINGS:
            if word.endswith(ending) and len(word) - len(ending) >= 2:
                values.add(word[:-len(ending)])
                break
    # Whole script runs only. 京都 must not match an interior of 東京都.
    values.update(CJK_RUNS.findall(word))
    return values - STOP_WORDS


def title_features(title):
    normal = unicodedata.normalize('NFKC', title).casefold()
    terms = title_terms(normal)
    groups = {word: term_aliases(word) for word in terms}
    words = list(re.finditer(r'[^\W_]+', normal))
    joins = []
    for left, right in zip(words, words[1:]):
        a, b = left.group(), right.group()
        if (a != b and a in terms and b in terms
                and normal[left.end():right.start()].isspace()
                and re.fullmatch('[가-힣]{2,}', a) and re.fullmatch('[가-힣]{2,}', b)):
            joins.append(({x + y for x in groups[a] for y in groups[b]}, {a, b}))
    return groups, joins


def feature_terms(features):
    groups, joins = features
    return set().union(*groups.values(), *(joined for joined, _ in joins))


def match_count(features, signals):
    groups, joins = features
    # Merge overlapping aliases before counting. A later full Japanese word
    # can connect two earlier script runs; lexical order must not award both.
    clusters = []
    for word, values in groups.items():
        words, aliases = {word}, set(values)
        separate = []
        for prior_words, prior_aliases in clusters:
            if aliases & prior_aliases:
                words.update(prior_words)
                aliases.update(prior_aliases)
            else:
                separate.append((prior_words, prior_aliases))
        clusters = separate + [(words, aliases)]
    matched = {i for i, (_, aliases) in enumerate(clusters) if aliases & signals}
    used_words = set().union(*(clusters[i][0] for i in matched))
    used_aliases = set().union(*(clusters[i][1] for i in matched))

    # A compound already present alongside its constituents is redundant when
    # either constituent earns credit. This only removes duplicate credit; new
    # spacing matches still require the adjacent whitespace joins above.
    owner = {word: i for i, (words, _) in enumerate(clusters) for word in words}
    by_alias = {alias: i for i, (_, aliases) in enumerate(clusters) for alias in aliases}
    hangul = [word for word in groups if re.fullmatch('[가-힣]{2,}', word)]
    redundant = set()
    for a in hangul:
        for b in hangul:
            parts = {owner[a], owner[b]}
            if len(parts) < 2 or not parts & matched:
                continue
            for x in groups[a]:
                for y in groups[b]:
                    compound = by_alias.get(x + y)
                    if compound in matched and compound not in parts:
                        redundant.add(compound)
    count = len(matched - redundant)
    for joined, words in joins:
        if not used_words & words and joined & signals and not joined & used_aliases:
            count += 1
            used_words.update(words)
            used_aliases.update(joined)
    return count


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
                signals[row['preference']].update(feature_terms(title_features(row['title'])))
        ranked = []
        for row in rows:
            if row['preference'] != 'neutral':
                continue  # Rated items supply feedback; propose other included items.
            features = title_features(row['title'])
            positive = match_count(features, signals['like'])
            negative = match_count(features, signals['dislike']) + .5 * match_count(features, signals['less'])
            # Aliases add no denominator terms or duplicate credit. Keep the
            # existing original-word normalization and feedback weights.
            score = (positive - negative) / math.sqrt(max(1, len(features[0])))
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
