"""Bounded, plain-text timed subtitles. No active markup or file references."""
from __future__ import annotations

import html
import math
import re
from .storage import MediaError

MAX_SUBTITLE_BYTES = 2 * 1024 * 1024
MAX_CUES = 20000
NUMERIC_UNIT = re.compile(r'(?<=[0-9])\s*(?:mm|cm|km|m|kg|mg|g|mL|ml|L|ms|s|kHz|MHz|GHz|Hz|KB|MB|GB|TB|°C|°F)(?![A-Za-z])')


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
        text = data.decode('utf-8-sig')
    except UnicodeError:
        try:
            text = data.decode('cp949')  # Includes EUC-KR; never replace invalid bytes.
        except UnicodeError:
            raise MediaError('subtitle_encoding_unsupported', 422) from None
    text = text.replace('\r\n', '\n').replace('\r', '\n').strip()
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


def translation_units(cues):
    """Join adjacent fragments, preserving source timing rather than inventing alignment."""
    units = []
    for cue in cues:
        previous = units[-1] if units else None
        if (previous and not re.search(r'[.!?。！？][\"\'”’」』)]*$', previous['text'])
                and 0 <= cue['start'] - previous['end'] <= .8
                and cue['end'] - previous['start'] <= 12
                and len(previous['text']) + len(cue['text']) + 1 <= 400):
            previous['text'] += ' ' + cue['text']
            previous['end'] = cue['end']
        else:
            units.append(dict(cue))
    return units


def korean_text(text):
    """Conservative pass-through; never classify an entire mixed-language video as Korean."""
    # Whisper may write Korean measurements as "15m". Ignore only explicit numeric
    # units for classification; preserve the text and require all remaining letters
    # to be Hangul. Do not consume prefixes of foreign words such as "15minutes".
    letters = [c for c in NUMERIC_UNIT.sub('', text) if c.isalpha()]
    return bool(letters) and all('\uac00' <= c <= '\ud7a3' or '\u1100' <= c <= '\u11ff'
                                 or '\u3130' <= c <= '\u318f' for c in letters)


def timestamp(seconds, separator='.'):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}{separator}{ms % 1000:03}'


def webvtt(cues, fallback_indices=()):
    # Encode all markup, including model/user-provided cue settings and tags.
    return 'WEBVTT\n\n' + '\n\n'.join(
        f"{timestamp(c['start'])} --> {timestamp(c['end'])}\n{'[원문] ' if i in fallback_indices else ''}{html.escape(c['text'], quote=False)}"
        for i, c in enumerate(cues)) + '\n'
