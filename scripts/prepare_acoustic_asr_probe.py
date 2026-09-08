"""Build a non-graphic acoustic pilot from explicitly supplied generated WAV clips.

No download/API calls. The SRT is the intended TTS script, not human-verified gold.
Run with the optional model runtime (numpy), never inside the app's private library.
"""
import argparse
import hashlib
import json
from pathlib import Path
import wave

import numpy as np

RATE = 24000


def timestamp(seconds):
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    secs, millis = divmod(millis, 1000)
    return f'{hours:02}:{minutes:02}:{secs:02},{millis:03}'


def prepare(source, output):
    generation = json.loads((source / 'generation.json').read_text(encoding='utf-8'))
    rows = generation['clips']
    if len(rows) != 6 or any(row['state'] != 'saved' for row in rows):
        raise ValueError('Six complete source clips are required')
    clips = []
    for row in rows:
        path = source / row['file']
        if path.resolve().parent != source.resolve():
            raise ValueError('Clip must be directly inside the supplied source folder')
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Source hash changed')
        with wave.open(str(path), 'rb') as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, RATE):
                raise ValueError('Expected mono PCM16 at 24 kHz')
            clips.append(np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(np.float64) / 32768)
    output.mkdir()  # Refuse accidental overwrite/rerun.
    rng = np.random.default_rng(20260908)
    blocks, cases, cues = [], [], []
    position = 0

    def add_case(name, placements, *, quiet=False):
        nonlocal position
        length = max((offset + len(clips[index]) for index, offset in placements), default=RATE * 12) + RATE
        block = np.zeros(length)
        case_cues = []
        for index, offset in placements:
            signal = clips[index].copy()
            if quiet:
                signal *= 10 ** (-18 / 20)
                # White noise RMS is 10 dB below this whole clip's RMS, including pauses.
                noise = rng.normal(size=len(signal))
                noise *= np.sqrt(np.mean(signal ** 2)) / (10 ** (10 / 20) * np.sqrt(np.mean(noise ** 2)))
                signal += noise
            block[offset:offset + len(signal)] += signal
            cue = {'id': name + '-' + rows[index]['id'], 'start': (position + offset) / RATE,
                   'end': (position + offset + len(signal)) / RATE, 'text': rows[index]['script']}
            cues.append(cue);case_cues.append(cue)
        if not placements:
            # Artificial non-speech control: silence, low noise bursts and clicks.
            # This is not a recording or simulation of sexual vocalizations/breathing.
            for start in (3, 6, 9):
                first = start * RATE
                block[first:first + RATE // 2] = rng.normal(0, 0.003, RATE // 2)
            block[2 * RATE:2 * RATE + 100] = 0.03
        peak = float(np.max(np.abs(block)))
        scale = min(1.0, 0.95 / peak) if peak else 1.0
        block *= scale
        cases.append({'name': name, 'start': position / RATE, 'end': (position + length) / RATE,
                      'cues': case_cues, 'peak_scale': scale})
        blocks.extend((block, np.zeros(RATE * 6)))
        position += length + RATE * 6

    placements, offset = [], RATE
    for index, clip in enumerate(clips):
        placements.append((index, offset));offset += len(clip) + round(0.65 * RATE)
    add_case('source', placements)
    add_case('quiet_noise', placements, quiet=True)
    pairs, offset = [], RATE
    for first in (0, 2, 4):
        pairs.extend(((first, offset), (first + 1, offset + RATE)))
        offset += max(len(clips[first]), RATE + len(clips[first + 1])) + RATE
    add_case('overlap', pairs)
    add_case('non_speech', [])
    samples = np.concatenate(blocks[:-1])
    path = output / 'acoustic-pilot.wav'
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(RATE)
        stream.writeframes(np.round(np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())
    cues.sort(key=lambda cue: (cue['start'], cue['end']))
    srt = '\n\n'.join(f"{i}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{c['text']}"
                       for i, c in enumerate(cues, 1)) + '\n'
    (output / 'intended-script.srt').write_text(srt, encoding='utf-8')
    manifest = {'schema': 1, 'sample_rate': RATE, 'audio_file': path.name,
        'audio_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'duration_seconds': len(samples) / RATE,
        'reference_status': 'intended TTS script; no independent listening/word-alignment sign-off',
        'limitations': 'Non-graphic synthetic pilot. No genuine adult-media acting or nonverbal vocalization recordings. Not a real-media quality ranking.',
        'quiet_noise': {'gain_db': -18, 'noise': 'white Gaussian', 'snr_db_clip_including_pauses': 10, 'seed': 20260908},
        'overlap': 'Two source clips per pair; second starts one second after first. Not natural conversational overlap.',
        'cases': cases, 'source_clips': [{k: row[k] for k in ('id', 'script', 'file', 'sha256', 'duration_seconds', 'style_requested')} for row in rows]}
    (output / 'reference.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'duration_seconds': manifest['duration_seconds'], 'cues': len(cues), 'sha256': manifest['audio_sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prepare(args.source, args.output)
