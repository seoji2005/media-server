"""Local Qwen speech recognition and separate forced alignment, one window at a time."""
from __future__ import annotations

import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import unicodedata

from .storage import MediaError, file_signature, no_symlink, run_media
from .subtitles import MAX_CUES, validate_cues

PROFILE = 'qwen3-asr-1.7b-fa-0.6b-v1:all-audio-30s-quiet-cut:auto-language:phrase-boundaries'
ASR_REPO = 'Qwen/Qwen3-ASR-1.7B-hf'
ASR_REVISION = 'bcd2b5b7f32b480ab5790554cfa8347f246a14f3'
ALIGNER_REPO = 'Qwen/Qwen3-ForcedAligner-0.6B-hf'
ALIGNER_REVISION = 'c07281df297b9905d24a508279258cccf987a064'
PACKAGES = ('torch', 'transformers', 'numpy', 'librosa', 'nagisa', 'soynlp', 'tokenizers')
LANGUAGES = {'Chinese', 'English', 'Cantonese', 'French', 'German', 'Italian',
             'Japanese', 'Korean', 'Portuguese', 'Russian', 'Spanish'}
SAMPLE_RATE = 16000
PHRASE_END = re.compile(r'[、,。！？!?;；.]["\'”’」』)]*\s*$')


def private_runtime():
    for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY',
                 'DO_NOT_TRACK', 'ORT_DISABLE_TELEMETRY'):
        os.environ[name] = '1'
    from .models import require_private_runtime
    require_private_runtime()


def local_models(root, check_packages=False):
    paths = {kind: root / 'models' / ('qwen-' + kind) for kind in ('asr', 'aligner')}
    settings = root / 'models' / 'qwen-paths.json'
    no_symlink(settings)
    if settings.exists():
        try:
            if settings.stat().st_size > 8192:
                raise ValueError()
            values = json.loads(settings.read_text(encoding='utf-8'))
            if type(values) is not dict or set(values) != {'asr', 'aligner'}:
                raise ValueError()
            for kind, value in values.items():
                if not isinstance(value, str) or not Path(value).is_absolute():
                    raise ValueError()
                paths[kind] = Path(value)
        except (ValueError, TypeError):
            raise MediaError('model_settings_invalid', 422) from None
    for kind, path in paths.items():
        no_symlink(path)
        for name in ('config.json', 'tokenizer.json', 'tokenizer_config.json',
                     'processor_config.json', 'model.safetensors'):
            target = model_file(path, path / name)
            if not target.is_file():
                raise MediaError('local_models_missing', 503)
        try:
            config = json.loads((path / 'config.json').read_text(encoding='utf-8'))
            architecture = 'Qwen3ASRForConditionalGeneration' if kind == 'asr' else 'Qwen3ASRForTokenClassification'
            if (config['architectures'] != [architecture] or config['model_type'] != 'qwen3_asr'
                    or config['text_config']['hidden_size'] != (2048 if kind == 'asr' else 1024)):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise MediaError('model_runtime_incompatible', 503) from None
    if check_packages:
        private_runtime()
        try:
            if any(importlib.util.find_spec(name) is None for name in
                   ('torch', 'transformers', 'numpy', 'librosa', 'nagisa')):
                raise ValueError()
            version = tuple(int(v) for v in importlib.metadata.version('transformers').split('.')[:2])
            if version < (5, 13):
                raise ValueError()
        except (ImportError, ValueError, importlib.metadata.PackageNotFoundError):
            raise MediaError('model_runtime_missing', 503) from None
    return paths


def model_file(root, path):
    # An explicitly configured, pinned HF cache uses links into its own blobs.
    # Other symlinks, paths and remote model code remain forbidden.
    if path.is_symlink():
        if root.name not in (ASR_REVISION, ALIGNER_REVISION) or root.parent.name != 'snapshots':
            raise MediaError('unsafe_storage', 503)
        target = path.resolve(strict=True)
        if target.parent != root.parent.parent / 'blobs':
            raise MediaError('unsafe_storage', 503)
        no_symlink(target)
        return target
    no_symlink(path)
    return path


def normalized(text, language):
    # Match the native aligner's letter/number/apostrophe filter. Filter before
    # compatibility normalization so symbols such as trademark signs cannot
    # become extra letters. This comparison never changes the saved source text.
    # Japanese nagisa normalizes before the native filter; other languages do not.
    if language == 'Japanese':
        text = unicodedata.normalize('NFKC', text).replace('İ', 'I')
    kept = ''.join(c for c in text if c == "'" or unicodedata.category(c)[0] in 'LN')
    return unicodedata.normalize('NFKC', kept).casefold()


def source_slices(text, units, language):
    """Map every aligned word to exact source characters, retaining punctuation/spaces."""
    chars, offsets = [], []
    for i, char in enumerate(text):
        value = normalized(char, language)
        chars.extend(value); offsets.extend([i] * len(value))
    joined = ''.join(chars)
    expected = normalized(text, language)
    if joined != expected:
        # Whole-string NFKC can compose adjacent kana/Jamo. Rebuild only this
        # uncommon mapping from bounded prefixes, retaining the first source offset.
        joined, offsets = '', []
        for i in range(len(text)):
            current = normalized(text[:i+1], language)
            common = 0
            while common < min(len(joined), len(current)) and joined[common] == current[common]:
                common += 1
            start = offsets[common] if common < len(offsets) else i
            offsets[common:] = [start] * (len(current) - common)
            joined = current
    cursor, starts = 0, []
    for unit in units:
        word = normalized(unit['text'], language)
        if not word or not joined.startswith(word, cursor):
            raise MediaError('alignment_text_mismatch', 422)
        starts.append(offsets[cursor]); cursor += len(word)
    if cursor != len(joined) or (text.strip() and not starts):
        raise MediaError('alignment_text_mismatch', 422)
    if not starts:
        return []
    starts[0] = 0
    return [text[first:last] for first, last in zip(starts, starts[1:] + [len(text)])]


def aligned_cues(text, units, clip, language):
    """Punctuation chooses phrase boundaries; a subword time gap never splits a word."""
    pieces = source_slices(text, units, language)
    groups, pending = [], []
    for index, (piece, unit) in enumerate(zip(pieces, units)):
        pending.append((piece, unit))
        decimal = (index + 1 < len(pieces) and re.search(r'\d\.$', piece.rstrip())
                   and pieces[index+1][:1].isdigit())
        if PHRASE_END.search(piece) and not decimal:
            groups.append(pending); pending = []
    if pending:
        groups.append(pending)
    # A zero-length phrase can share a contiguous neighbor's real time envelope.
    # Never omit its text or assign a fabricated standalone duration.
    i = 0
    while i < len(groups):
        group = groups[i]
        start = min(clip[1]-clip[0], min(u['start'] for _, u in group))
        end = min(clip[1]-clip[0], max(u['end'] for _, u in group))
        if round(start, 3) >= round(end, 3):
            if i + 1 < len(groups) and min(u['start'] for _, u in groups[i+1]) - end <= .8:
                groups[i+1] = group + groups[i+1]; groups.pop(i); continue
            if i and start - max(u['end'] for _, u in groups[i-1]) <= .8:
                groups[i-1].extend(group); groups.pop(i); continue
            raise MediaError('alignment_unresolved', 422)
        i += 1
    cues = [{'start':min(clip[1],clip[0]+min(u['start'] for _, u in g)),
             'end':min(clip[1],clip[0]+max(u['end'] for _, u in g)),
             'text':''.join(s for s, _ in g).strip()} for g in groups]
    return validate_cues(cues, clip[1])


def validate_evidence(evidence, clip):
    """Rebuild displayable source cues from the saved raw transcription/alignment."""
    if (type(evidence) is not dict or set(evidence) !=
            {'profile', 'language', 'text', 'audio_sha256', 'units', 'boundary'}
            or evidence['profile'] != PROFILE
            or not isinstance(evidence['audio_sha256'], str)
            or not re.fullmatch('[0-9a-f]{64}', evidence['audio_sha256'])
            or evidence['boundary'] not in ('end', 'quiet', 'forced')
            or not isinstance(evidence['text'], str) or len(evidence['text']) > 4000
            or type(evidence['units']) is not list or len(evidence['units']) > 4000):
        raise MediaError('processing_checkpoint_invalid', 409)
    text, units = evidence['text'], evidence['units']
    if not text.strip():
        if units or evidence['language'] not in ('', None, *LANGUAGES):
            raise MediaError('processing_checkpoint_invalid', 409)
        return []
    if evidence['language'] not in LANGUAGES:
        raise MediaError('alignment_language_unsupported', 422)
    previous = 0.
    for unit in units:
        if (type(unit) is not dict or set(unit) != {'text', 'start', 'end', 'raw_start', 'raw_end'}
                or not isinstance(unit['text'], str) or not unit['text'].strip()
                or len(unit['text']) > 4000
                or any(type(unit[k]) not in (int, float) or not math.isfinite(unit[k])
                       for k in ('start', 'end', 'raw_start', 'raw_end'))
                # The model has an 80 ms timestamp grid. Bound its final tick to
                # the actual audio only; preserve official/raw values as evidence.
                or not 0 <= unit['start'] <= unit['end'] <= clip[1] - clip[0] + .080001
                or unit['start'] < previous):
            raise MediaError('alignment_unresolved', 422)
        previous = unit['start']
    return aligned_cues(text, units, clip, evidence['language'])


def windows(audio):
    """Cover every sample exactly once, choosing a quiet cut in the last ten seconds."""
    import numpy as np
    first = 0
    while first < len(audio):
        last = min(first + 30 * SAMPLE_RATE, len(audio)); boundary = 'end'
        if last < len(audio):
            # 300 ms sustained low energy: segmentation only, never speech rejection.
            begin = first + 20 * SAMPLE_RATE
            frames = audio[begin:last].reshape(-1, 160)
            energy = np.mean(frames.astype(np.float64) ** 2, axis=1)
            quiet = np.convolve((energy <= 1.e-5).astype(int), np.ones(30, dtype=int), 'valid')
            candidates = np.flatnonzero(quiet == 30)
            if len(candidates):
                last = begin + (int(candidates[-1]) + 15) * 160; boundary = 'quiet'
            else:
                boundary = 'forced'
        yield first, last, boundary
        first = last


def evidence_result(evidence, clip):
    try:
        return validate_evidence(evidence, clip), None
    except MediaError as exc:
        if exc.code not in ('alignment_unresolved', 'alignment_text_mismatch', 'alignment_language_unsupported'):
            raise
        return [], exc.code


class QwenSpeech:
    asr_profile = PROFILE
    audio_timing = 'source-timestamps-v1'

    def __init__(self, root):
        from .models import device_configuration
        private_runtime()
        self.paths = local_models(root, check_packages=True)
        self.device = device_configuration(root)['device']
        try:
            import torch
            from transformers import AutoModelForMultimodalLM, AutoModelForTokenClassification, AutoProcessor
            if self.device == 'cuda' and not torch.cuda.is_available():
                raise MediaError('model_cuda_unavailable', 503)
        except ImportError:
            raise MediaError('model_runtime_incompatible', 503) from None

    def identity(self):
        digest = hashlib.sha256((PROFILE + ':' + self.device + ':float32-cpu-float16-cuda').encode())
        digest.update(run_media(['ffmpeg', '-version'], 10, 16384))
        for package in PACKAGES:
            try:
                version = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                if package != 'soynlp':
                    raise
                version = 'not-installed'
            digest.update((package + ':' + version).encode())
        for kind, root in self.paths.items():
            digest.update((kind + ':' + str(root.absolute())).encode())
            for path in sorted(root.rglob('*')):
                target = model_file(root, path)
                if path.is_file():
                    with target.open('rb') as stream:
                        digest.update((path.relative_to(root).as_posix() + str(target) + repr(file_signature(stream))).encode())
        return digest.hexdigest()

    def recognize(self, audio):
        import torch
        from transformers import AutoModelForMultimodalLM, AutoProcessor
        dtype = torch.float16 if self.device == 'cuda' else torch.float32
        model = processor = inputs = output = generated = None
        try:
            processor = AutoProcessor.from_pretrained(str(self.paths['asr']), local_files_only=True, trust_remote_code=False)
            model = AutoModelForMultimodalLM.from_pretrained(str(self.paths['asr']), local_files_only=True,
                trust_remote_code=False, use_safetensors=True, dtype=dtype, attn_implementation='sdpa').to(self.device).eval()
            inputs = processor.apply_transcription_request(audio=audio, language=None, prompt=None).to(self.device, dtype)
            with torch.inference_mode():
                output = model.generate(**inputs, do_sample=False, max_new_tokens=1024)
            generated = output[:, inputs['input_ids'].shape[1]:]
            eos = model.config.eos_token_id
            eos = [eos] if isinstance(eos, int) else eos
            if not any(token in eos for token in generated[0].tolist()):
                raise MediaError('asr_truncated', 422)
            parsed = processor.decode(generated, return_format='parsed')[0]
            text, language = parsed['transcription'], parsed['language']
            if not isinstance(text, str) or len(text) > 4000:
                raise MediaError('asr_truncated', 422)
            return text, language
        finally:
            model = processor = inputs = output = generated = None
            self.close()

    def align(self, audio, text, language):
        if language == 'Korean' and importlib.util.find_spec('soynlp') is None:
            raise MediaError('model_runtime_missing', 503)
        import torch
        from transformers import AutoModelForTokenClassification, AutoProcessor
        dtype = torch.float16 if self.device == 'cuda' else torch.float32
        model = processor = inputs = output = None
        try:
            processor = AutoProcessor.from_pretrained(str(self.paths['aligner']), local_files_only=True, trust_remote_code=False)
            model = AutoModelForTokenClassification.from_pretrained(str(self.paths['aligner']), local_files_only=True,
                trust_remote_code=False, use_safetensors=True, dtype=dtype, attn_implementation='sdpa').to(self.device).eval()
            inputs, words = processor.prepare_forced_aligner_inputs(audio=audio, transcript=text,
                language=language, sampling_rate=SAMPLE_RATE)
            inputs = inputs.to(self.device, dtype)
            with torch.inference_mode():
                output = model(**inputs)
            classes = output.logits[0].argmax(-1)[inputs['input_ids'][0] == model.config.timestamp_token_id].cpu().tolist()
            official = processor.decode_forced_alignment(logits=output.logits, input_ids=inputs['input_ids'],
                word_lists=words, timestamp_token_id=model.config.timestamp_token_id)[0]
            if len(classes) != 2 * len(official):
                raise MediaError('alignment_unresolved', 422)
            tick = processor.timestamp_segment_time / 1000
            return [{'text':unit['text'], 'start':float(unit['start_time']), 'end':float(unit['end_time']),
                     'raw_start':classes[2*i]*tick, 'raw_end':classes[2*i+1]*tick}
                    for i, unit in enumerate(official)]
        finally:
            model = processor = inputs = output = None
            self.close()

    def transcribe_parts(self, path, duration, audio_index, saved):
        from .models import LocalModels
        audio = LocalModels.decode_audio(self, path, duration, audio_index)
        if len(audio) > math.ceil(duration * SAMPLE_RATE):
            # Container rounding may expose a few padded samples after the media end.
            audio = audio[:math.floor(duration * SAMPLE_RATE)]
        plan = list(windows(audio))
        if len(saved) > len(plan):
            raise MediaError('processing_checkpoint_invalid', 409)
        for index, (first, last, boundary) in enumerate(plan):
            clip = [first/SAMPLE_RATE, last/SAMPLE_RATE]
            samples = audio[first:last].copy()
            digest = hashlib.sha256(samples.tobytes()).hexdigest()
            if index < len(saved):
                part = saved[index]
                if (part['clip'] != clip or part.get('evidence', {}).get('audio_sha256') != digest
                        or part['evidence']['boundary'] != boundary):
                    raise MediaError('processing_checkpoint_invalid', 409)
                continue
            text, language = self.recognize(samples)
            units = self.align(samples, text, language) if text.strip() and language in LANGUAGES else []
            evidence = {'profile':PROFILE, 'language':language, 'text':text, 'audio_sha256':digest,
                        'units':units, 'boundary':boundary}
            cues, error = evidence_result(evidence, clip)
            yield {'clip':clip, 'cues':cues, 'evidence':evidence, 'error':error}

    def close(self):
        gc.collect()
        import torch
        if self.device == 'cuda':
            torch.cuda.empty_cache()
