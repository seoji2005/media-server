"""Local Qwen speech recognition and separate forced alignment, one window at a time."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

from .storage import MediaError, RESERVE, file_signature, no_symlink, run_media, safe_io
from .subtitles import MAX_CUES, validate_cues

LEGACY_PROFILE = 'qwen3-asr-1.7b-fa-0.6b-v1:all-audio-30s-quiet-cut:auto-language:phrase-boundaries'
PROFILE = 'qwen3-asr-1.7b-fa-0.6b-v2:all-audio-30s-quiet-cut:auto-language:aligned-phrase-handoff-20s'
PROFILES = (LEGACY_PROFILE, PROFILE)
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


def _aligned_evidence(evidence, clip):
    """Rebuild displayable source cues from the saved raw transcription/alignment."""
    if (type(evidence) is not dict or set(evidence) !=
            {'profile', 'language', 'text', 'audio_sha256', 'units', 'boundary'}
            or evidence['profile'] != LEGACY_PROFILE
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


def phrase_handoff(cues, clip, boundary):
    """Defer the unfinished suffix after an aligned phrase, never delete words.

    At least 20 seconds advance, at most 10 seconds are reconsidered. Only an
    internal punctuation boundary with non-overlapping phrase times is eligible.
    A quiet cut, final window or uncertain alignment keeps the existing envelope.
    """
    if boundary == 'forced':
        for i in range(len(cues)-2, -1, -1):
            left, right = cues[i:i+2]
            if (PHRASE_END.search(left['text']) and clip[0]+20 <= left['end']
                    <= right['start'] < clip[1]-.08):
                end = round((left['end']+right['start'])/2*SAMPLE_RATE)/SAMPLE_RATE
                return end, cues[:i+1]
    return clip[1], cues


def validate_evidence(evidence, clip):
    if type(evidence) is not dict or evidence.get('profile') != PROFILE:
        return _aligned_evidence(evidence, clip)
    if set(evidence) != {'profile','language','text','audio_sha256','units','boundary','recognition_end'}:
        raise MediaError('processing_checkpoint_invalid', 409)
    end = evidence['recognition_end']
    if (type(end) not in (int,float) or not math.isfinite(end)
            or not clip[0] < clip[1] <= end or end-clip[0] > 30+.5/SAMPLE_RATE):
        raise MediaError('processing_checkpoint_invalid', 409)
    raw = {k:v for k,v in evidence.items() if k != 'recognition_end'}
    raw['profile'] = LEGACY_PROFILE
    try:
        cues = _aligned_evidence(raw, [clip[0],end])
    except MediaError:
        if clip[1] != end:
            raise MediaError('processing_checkpoint_invalid', 409) from None
        raise
    committed_end, cues = phrase_handoff(cues, [clip[0],end], evidence['boundary'])
    if clip[1] != committed_end:
        raise MediaError('processing_checkpoint_invalid', 409)
    return cues


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


@contextmanager
def decoder_errors():
    """Drain error-level diagnostics without retaining private text or growing RAM/disk."""
    read_fd, write_fd = os.pipe()
    failed = [False]
    with os.fdopen(read_fd, 'rb') as reader, os.fdopen(write_fd, 'wb') as writer:
        def drain():
            try:
                while reader.read(4096):
                    failed[0] = True
            except OSError:
                failed[0] = True
        thread = threading.Thread(target=drain, daemon=True)
        thread.start()
        try:
            yield writer, failed
        finally:
            writer.close()
            thread.join()


@contextmanager
def decoded_audio(path, duration, audio_index):
    """Spool PCM beside the owned input; retain only one speech window in RAM.

    TemporaryFile is unlinked on POSIX and delete-on-close on Windows. The child
    inherits its open handle; neither a decoder path nor diagnostics are exposed.
    The PCM bytes/timeline match LocalModels.decode_audio for historical evidence.
    """
    if type(audio_index) is not int or not 0 <= audio_index < 128:
        raise MediaError('invalid_audio_track', 422)
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise MediaError('invalid_media', 422)
    from .models import require_private_runtime
    require_private_runtime()
    no_symlink(path)
    limit = math.ceil(duration * SAMPLE_RATE * 4) + 1048576
    try:
        if shutil.disk_usage(path.parent).free < limit + RESERVE:
            raise MediaError('insufficient_space', 507)
        with tempfile.TemporaryFile(dir=path.parent, prefix='qwen-audio-') as output:
            # FFmpeg may exceed -fs by one packet; anything above the historical
            # cap is rejected, never mistaken for a successfully decoded ending.
            args = ['ffmpeg','-v','error','-nostdin','-copyts','-start_at_zero',
                    '-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm',
                    '-i',str(path),'-map',f'0:a:{audio_index}','-vn','-sn','-dn',
                    '-ac','1','-ar','16000','-af','aresample=async=1:first_pts=0',
                    '-fs',str(limit+4),'-f','f32le','pipe:1']
            try:
                # Demuxers can report a truncated file at error level yet exit 0.
                # Reject that partial PCM before ASR/checkpoint publication. Do not
                # compare against video length: a valid audio track may end earlier.
                with decoder_errors() as (diagnostics, failed):
                    result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=output,
                        stderr=diagnostics, timeout=max(120,min(1800,math.ceil(duration/2))))
            except FileNotFoundError:
                raise MediaError('ffmpeg_unavailable', 503) from None
            except subprocess.TimeoutExpired:
                raise MediaError('media_timeout', 422) from None
            size = output.seek(0, os.SEEK_END)
            if result.returncode and shutil.disk_usage(path.parent).free < RESERVE:
                raise MediaError('insufficient_space', 507)
            if result.returncode or failed[0] or not size or size % 4 or size > limit:
                raise MediaError('invalid_media', 422)
            count = size // 4
            if count > math.ceil(duration * SAMPLE_RATE):
                count = math.floor(duration * SAMPLE_RATE)
            yield output, count
    except OSError as exc:
        raise safe_io(exc) from None


class SpeechTimings:
    """Opt-in, bounded aggregates. Never part of model identity or checkpoints."""
    def __init__(self):
        self.phases = {f'{kind}_{phase}': {'calls': 0, 'seconds': 0., 'failures': 0}
                      for kind in ('asr', 'align')
                      for phase in ('load', 'prepare', 'infer', 'decode', 'cleanup')}

    @contextmanager
    def measure(self, name, synchronize=None):
        row = self.phases[name]
        failed = True
        started = time.perf_counter()
        try:
            if synchronize:
                synchronize()
            started = time.perf_counter()
            yield
            if synchronize:
                synchronize()
            failed = False
        finally:
            row['calls'] += 1
            row['seconds'] += time.perf_counter() - started
            row['failures'] += int(failed)


def runtime_device(root):
    """Check configuration/native imports/device without requiring model weights."""
    from .models import device_configuration
    private_runtime()
    device = device_configuration(root)['device']
    try:
        import torch
        from transformers import AutoModelForMultimodalLM, AutoModelForTokenClassification, AutoProcessor
        if device == 'cuda' and not torch.cuda.is_available():
            raise MediaError('model_cuda_unavailable', 503)
    except ImportError:
        raise MediaError('model_runtime_incompatible', 503) from None
    return device


class QwenSpeech:
    asr_profile = PROFILE
    audio_timing = 'source-timestamps-v1'
    timings = None

    def __init__(self, root, profile=PROFILE, *, timings=None):
        if profile not in PROFILES:
            raise MediaError('processing_config_changed', 409)
        self.asr_profile = profile
        self.timings = timings
        private_runtime()
        self.paths = local_models(root, check_packages=True)
        self.device = runtime_device(root)

    def identity(self):
        digest = hashlib.sha256((self.asr_profile + ':' + self.device + ':float32-cpu-float16-cuda').encode())
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

    def _phase(self, name):
        if self.timings is None:
            return nullcontext()
        synchronize = None
        # Cleanup must run even if CUDA synchronization fails. Successful decode
        # already drained preceding work; cleanup adds no new model operations.
        # Failed execution timings are partial, not successful cost samples.
        if self.device == 'cuda' and not name.endswith('_cleanup') and sys.exc_info()[0] is None:
            import torch
            synchronize = torch.cuda.synchronize
        return self.timings.measure(name, synchronize)

    def recognize(self, audio):
        import torch
        from transformers import AutoModelForMultimodalLM, AutoProcessor
        dtype = torch.float16 if self.device == 'cuda' else torch.float32
        model = processor = inputs = output = generated = None
        try:
            with self._phase('asr_load'):
                processor = AutoProcessor.from_pretrained(str(self.paths['asr']), local_files_only=True, trust_remote_code=False)
                model = AutoModelForMultimodalLM.from_pretrained(str(self.paths['asr']), local_files_only=True,
                    trust_remote_code=False, use_safetensors=True, dtype=dtype, attn_implementation='sdpa').to(self.device).eval()
            with self._phase('asr_prepare'):
                inputs = processor.apply_transcription_request(audio=audio, language=None, prompt=None).to(self.device, dtype)
            with self._phase('asr_infer'), torch.inference_mode():
                output = model.generate(**inputs, do_sample=False, max_new_tokens=1024)
            with self._phase('asr_decode'):
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
            with self._phase('asr_cleanup'):
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
            with self._phase('align_load'):
                processor = AutoProcessor.from_pretrained(str(self.paths['aligner']), local_files_only=True, trust_remote_code=False)
                model = AutoModelForTokenClassification.from_pretrained(str(self.paths['aligner']), local_files_only=True,
                    trust_remote_code=False, use_safetensors=True, dtype=dtype, attn_implementation='sdpa').to(self.device).eval()
            with self._phase('align_prepare'):
                inputs, words = processor.prepare_forced_aligner_inputs(audio=audio, transcript=text,
                    language=language, sampling_rate=SAMPLE_RATE)
                inputs = inputs.to(self.device, dtype)
            with self._phase('align_infer'), torch.inference_mode():
                output = model(**inputs)
            with self._phase('align_decode'):
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
            with self._phase('align_cleanup'):
                model = processor = inputs = output = None
                self.close()

    def transcribe_parts(self, path, duration, audio_index, saved):
        with decoded_audio(path, duration, audio_index) as (stream, count):
            yield from self._transcribe_audio(stream, count, saved)

    def _transcribe_audio(self, stream, count, saved):
        import numpy as np
        first, index = 0, 0
        while first < count:
            # One lookahead sample distinguishes a full final window from a
            # forced/quiet cut. The historical segmentation sees the same bytes.
            read_count = min(30 * SAMPLE_RATE + 1, count - first)
            stream.seek(first * 4)
            raw = stream.read(read_count * 4)
            if len(raw) != read_count * 4:
                raise MediaError('invalid_media', 422)
            audio = np.frombuffer(raw, dtype='<f4')
            _, relative_end, boundary = next(windows(audio))
            last = first + relative_end
            clip = [first/SAMPLE_RATE, last/SAMPLE_RATE]
            samples = audio[:relative_end].copy()
            digest = hashlib.sha256(samples.tobytes()).hexdigest()
            if index < len(saved):
                part = saved[index]
                evidence = part.get('evidence', {})
                recognition_end = evidence.get('recognition_end', part['clip'][1])
                if (part['clip'][0] != clip[0] or recognition_end != clip[1]
                        or evidence.get('profile') != self.asr_profile
                        or evidence.get('audio_sha256') != digest or evidence['boundary'] != boundary):
                    raise MediaError('processing_checkpoint_invalid', 409)
                cues, error = evidence_result(evidence, part['clip'])
                if cues != part['cues'] or error != part['error']:
                    raise MediaError('processing_checkpoint_invalid', 409)
                first = round(part['clip'][1]*SAMPLE_RATE); index += 1
                continue
            text, language = self.recognize(samples)
            units = self.align(samples, text, language) if text.strip() and language in LANGUAGES else []
            evidence = {'profile':LEGACY_PROFILE, 'language':language, 'text':text, 'audio_sha256':digest,
                        'units':units, 'boundary':boundary}
            cues, error = evidence_result(evidence, clip)
            if self.asr_profile == PROFILE:
                evidence.update(profile=PROFILE, recognition_end=clip[1])
                if not error:
                    clip[1], cues = phrase_handoff(cues, clip, boundary)
            yield {'clip':clip, 'cues':cues, 'evidence':evidence, 'error':error}
            first = round(clip[1]*SAMPLE_RATE); index += 1
        if index < len(saved):
            raise MediaError('processing_checkpoint_invalid', 409)

    def close(self):
        gc.collect()
        import torch
        if self.device == 'cuda':
            torch.cuda.empty_cache()
