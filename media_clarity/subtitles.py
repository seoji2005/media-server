"""Bounded, plain-text timed subtitles. No active markup or file references."""
from __future__ import annotations

import html
import math
import re
from .storage import MediaError

MAX_SUBTITLE_BYTES = 2 * 1024 * 1024
MAX_CUES = 20000


def validate_cues(cues, duration):
    if not isinstance(cues, list) or len(cues) > MAX_CUES:
        raise MediaError('invalid_subtitles', 422)
    result, previous = [], -1
    for cue in cues:
        if type(cue) is not dict or set(cue) != {'start', 'end', 'text'}:
            raise MediaError('invalid_subtitles', 422)
        start, end, text = cue['start'], cue['end'], cue['text']
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, end)):
            raise MediaError('invalid_subtitles', 422)
        if not 0 <= start < end <= duration + .05 or start < previous:
            raise MediaError('invalid_subtitles', 422)
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise MediaError('invalid_subtitles', 422)
        text = text.strip()
        if any(ord(c) < 32 and c not in '\n\t' for c in text) or '\x7f' in text:
            raise MediaError('invalid_subtitles', 422)
        result.append({'start': round(start, 3), 'end': round(min(end, duration), 3), 'text': text})
        if result[-1]['start'] >= result[-1]['end']:
            raise MediaError('invalid_subtitles', 422)
        previous = start
    return result


def parse_srt(data, duration):
    if not data or len(data) > MAX_SUBTITLE_BYTES:
        raise MediaError('invalid_subtitles', 422)
    try:
        text = data.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').strip()
    except UnicodeError:
        raise MediaError('subtitle_utf8_required', 422) from None
    cues = []
    def seconds(value):
        h, m, s, ms = map(int, re.split('[:,.]', value))
        if m >= 60 or s >= 60:
            raise MediaError('invalid_subtitles', 422)
        return h * 3600 + m * 60 + s + ms / 1000
    for block in re.split(r'\n[ \t]*\n', text):
        lines = block.split('\n')
        if lines and lines[0].strip().isdigit():
            lines.pop(0)
        if len(lines) < 2:
            raise MediaError('invalid_subtitles', 422)
        match = re.fullmatch(r'(\d{2,3}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+(\d{2,3}:\d{2}:\d{2}[,.]\d{3})', lines[0].strip())
        if not match:
            raise MediaError('invalid_subtitles', 422)
        # Drop common SRT styling, keeping only literal visible text.
        body = html.unescape(re.sub(r'</?(?:b|i|u|s|font)(?:\s+[^>]*)?>', '', '\n'.join(lines[1:]), flags=re.I))
        cues.append({'start': seconds(match[1]), 'end': seconds(match[2]), 'text': body})
    return validate_cues(cues, duration)


def timestamp(seconds, separator='.'):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}{separator}{ms % 1000:03}'


def webvtt(cues):
    # Encode all markup, including model/user-provided cue settings and tags.
    return 'WEBVTT\n\n' + '\n\n'.join(
        f"{timestamp(c['start'])} --> {timestamp(c['end'])}\n{html.escape(c['text'], quote=False)}"
        for c in cues) + '\n'
