"""Display-only Korean subtitle layout; translation/checkpoint units stay intact."""
from __future__ import annotations

import math
import re
import unicodedata

from .subtitles import MAX_CUES, validate_cues

PROFILE = 'ko-readable-v2'
LINE_WIDTH = 16
MIN_MS = 834  # At least 5/6 second after millisecond quantization.
MAX_MS = 7000
MAX_CPS = 12
FALLBACK = '[원문] '


def width(text):
    """Korean guide's half-width Latin/space/punctuation accounting, not bytes."""
    result = 0
    for c in text:
        category = unicodedata.category(c)
        if category.startswith('M') or c == '\u200d':
            continue
        result += .5 if (ord(c) < 128 or c.isspace() or category.startswith('P')
                        or 'LATIN' in unicodedata.name(c, '')) else 1
    return result


def _lines(words, prefix):
    """Greedy lines never cut a word/name/number into arbitrary characters."""
    groups, lines, line, used = [], [], [], width(prefix)
    for word in words:
        needed = width(word) + (.5 if line else 0)
        if line and used + needed > LINE_WIDTH:
            lines.append(line)
            if len(lines) == 2:
                groups.append(lines)
                lines = []
            line, used = [], 0 if lines else width(prefix)
            needed = width(word)
        line.append(word)
        used += needed
        if re.search(r'[.!?。！？][\"\'”’」』)]*$', word):
            lines.append(line)
            groups.append(lines)
            lines, line, used = [], [], width(prefix)
    if line:
        lines.append(line)
    if lines:
        groups.append(lines)
    return groups


def _partition(words, count):
    """Balance bounded pieces at word boundaries, preferring nearby punctuation."""
    from bisect import bisect_left
    sums = [0]
    for word in words:
        sums.append(sums[-1] + width(word) + .5)
    parts, start = [], 0
    for remaining in range(count, 1, -1):
        target = (sums[-1] - sums[start]) / remaining
        near = bisect_left(sums, sums[start] + target)
        low, high = start + 1, len(words) - remaining + 1
        candidates = range(max(low, min(high, near - 2)), min(high, max(low, near + 2)) + 1)
        end = min(candidates, key=lambda i: (
            abs(sums[i]-sums[start]-target) / max(1, target)
            + (0 if re.search(r'[,.!?。！？][\"\'”’」』)]*$', words[i-1]) else .12), i))
        parts.append(words[start:end])
        start = end
    parts.append(words[start:])
    return parts


def _two_lines(words, prefix):
    text = ' '.join(words)
    if width(prefix + text) <= LINE_WIDTH or len(words) == 1:
        return text
    sums = [0]
    for word in words:
        sums.append(sums[-1] + width(word) + .5)
    def cost(i):
        first, second = width(prefix) + sums[i] - .5, sums[-1] - sums[i] - .5
        overflow = max(0, first-LINE_WIDTH) + max(0, second-LINE_WIDTH)
        return (overflow, abs(first-second) + max(0, first-second)*.1, i)
    split = min(range(1, len(words)), key=cost)
    return ' '.join(words[:split]) + '\n' + ' '.join(words[split:])


def _balanced_sentences(groups, prefix):
    """Avoid a nearly full block followed by a one-word sentence ending."""
    result, pending = [], []
    for i, group in enumerate(groups):
        pending.append(group)
        if i+1 == len(groups) or re.search(r'[.!?。！？][\"\'”’」』)]*$', group[-1][-1]):
            words = [w for g in pending for line in g for w in line]
            texts = [_two_lines(part, prefix) for part in _partition(words, len(pending))]
            if any(width(line) > LINE_WIDTH for text in texts for line in (prefix+text).split('\n')):
                texts = [_two_lines([w for line in g for w in line], prefix) for g in pending]
            result.extend(texts)
            pending = []
    return result


def _durations(weights, total):
    """Proportional timing with feasible bounds; no word alignment is claimed."""
    count = len(weights)
    low = MIN_MS if total >= count * MIN_MS else 1
    high = MAX_MS if total <= count * MAX_MS else total
    result, pending, left = [float(low)] * count, set(range(count)), float(total-count*low)
    while pending:
        weight = sum(weights[i] for i in pending)
        values = {i: left * weights[i] / weight for i in pending}
        # Reserve readable minima first, then distribute the remaining time.
        outlier = next((i for i in sorted(pending) if values[i] > high-low), None)
        if outlier is None:
            for i in pending:
                result[i] += values[i]
            break
        result[outlier] = high
        left -= high-low
        pending.remove(outlier)
    # Round cumulative boundaries instead of independently rounding each duration.
    ends, elapsed = [], 0.
    for value in result:
        elapsed += value
        ends.append(round(elapsed))
    ends[-1] = total
    return ends


def generated_layout(cues, duration, fallback_units=()):
    """Keep source units untouched; every output cue identifies its source unit."""
    cues = validate_cues(cues, duration)
    display, units, issues = [], [], []
    fallback_units = set(fallback_units)
    for index, cue in enumerate(cues):
        words = cue['text'].split()
        prefix = FALLBACK if index in fallback_units else ''
        groups = _lines(words, prefix)
        start, end = round(cue['start']*1000), round(cue['end']*1000)
        span = end-start
        desired = max(len(groups), math.ceil(span/MAX_MS))
        budget = MAX_CUES-len(display)-(len(cues)-index-1)
        count = min(desired, len(words), max(1, span//MIN_MS), budget)
        if count == len(groups):
            texts = _balanced_sentences(groups, prefix)
        else:
            texts = [_two_lines(part, prefix) for part in _partition(words, count)]
        weights = [max(.5, width(prefix + t.replace('\n', ' '))) for t in texts]
        offsets = _durations(weights, span)
        previous = 0
        for text, offset, weight in zip(texts, offsets, weights):
            shown = {'start':(start+previous)/1000, 'end':(start+offset)/1000, 'text':text}
            codes = []
            if any(width(line) > LINE_WIDTH for line in (prefix+text).split('\n')):
                codes.append('line_length')
            if offset-previous < MIN_MS:
                codes.append('short_duration')
            if offset-previous > MAX_MS:
                codes.append('long_duration')
            if weight*1000/(offset-previous) > MAX_CPS:
                codes.append('reading_speed')
            if count < desired:
                codes.append('layout_limited')
            if codes:
                issues.append({'cue':len(display), 'codes':codes})
            display.append(shown)
            units.append(index)
            previous = offset
    # Source units may overlap. Sort their children together, retaining provenance
    # and warning indices, rather than making a valid transcript unpublishable.
    order = sorted(range(len(display)), key=lambda i: display[i]['start'])
    original_codes = {issue['cue']:issue['codes'] for issue in issues}
    issues, latest_end = [], 0
    for index, old in enumerate(order):
        codes = original_codes.get(old, []).copy()
        shown = display[old]
        start, end = round(shown['start']*1000), round(shown['end']*1000)
        limit = (round(display[order[index+1]]['start']*1000) if index+1 < len(order)
                 else math.floor(duration*1000))
        # Hold only an isolated short cue with room for the full reading minimum.
        # Starts/text and canonical source intervals stay unchanged. Do not borrow
        # another cue's time or extend a cue inside an existing overlapping turn.
        if end-start < MIN_MS and start >= latest_end and start+MIN_MS <= limit:
            shown['end'] = (start+MIN_MS)/1000
            codes = [code for code in codes if code != 'short_duration']
            prefix = FALLBACK if units[old] in fallback_units else ''
            weight = max(.5, width(prefix + shown['text'].replace('\n', ' ')))
            if weight*1000/MIN_MS <= MAX_CPS:
                codes = [code for code in codes if code != 'reading_speed']
        if start < latest_end:
            codes.append('source_overlap')
        if codes:
            issues.append({'cue':index, 'codes':codes})
        latest_end = max(latest_end, round(shown['end']*1000))
    display, units = [display[i] for i in order], [units[i] for i in order]
    return {'profile':PROFILE, 'cues':validate_cues(display, duration), 'units':units, 'issues':issues}
