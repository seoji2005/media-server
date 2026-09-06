"""Provisional faster-whisper/MADLAD adapters; installed local weights only."""
from __future__ import annotations
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

from .storage import MediaError, file_signature, no_symlink, run_media
from .subtitles import MAX_CUES

PIPELINE = 'korean-subtitles-v4:silero6-jit-0.5-2000ms-pad400ms:source-clips:sentence-12s-400ch-gap0.8:madlad-ko-bf16-beam4-512-batch2:stat-identity'
PACKAGES = ('faster-whisper','ctranslate2','transformers','torch','torchaudio','silero-vad','sentencepiece','tokenizers','numpy','av')


def require_private_runtime():
    # Keep ORT entirely out of this process, including its pre-API native telemetry.
    # VAD uses the official local TorchScript model on every platform instead.
    if sys.modules.get('onnxruntime') is not None:
        raise MediaError('model_privacy_setup_required', 503)
    sys.modules['onnxruntime'] = None  # Python refuses subsequent ORT imports.


def local_models(root, check_packages=False):
    if check_packages:
        require_private_runtime()
    base = root / 'models'
    no_symlink(base)
    paths = {'asr':base/'asr', 'translation':base/'translation'}
    required = {'asr':('model.bin','config.json','tokenizer.json'),
                'translation':('config.json','tokenizer_config.json')}
    for kind, names in required.items():
        for name in names:
            path = paths[kind] / name
            no_symlink(path)
            if not path.is_file():
                raise MediaError('local_models_missing', 503)
    if not any(paths['translation'].glob('*.safetensors')):
        raise MediaError('local_models_missing', 503)
    if check_packages:
        if any(importlib.util.find_spec(n) is None for n in ('faster_whisper','transformers','torch','torchaudio','silero_vad','sentencepiece')):
            raise MediaError('model_runtime_missing', 503)
        paths['vad'] = Path(importlib.metadata.distribution('silero-vad').locate_file('silero_vad/data'))
        no_symlink(paths['vad'] / 'silero_vad.jit')
        if not (paths['vad'] / 'silero_vad.jit').is_file():
            raise MediaError('model_runtime_missing', 503)
    return paths


class LocalModels:
    batch_size = 2
    checkpoint_size = 20
    def __init__(self, root):
        for name in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK','ORT_DISABLE_TELEMETRY'):
            os.environ[name] = '1'
        self.paths = local_models(root, check_packages=True)
        self.device = 'cuda' if os.name == 'nt' else 'cpu'
        settings = root / 'models' / 'settings.json'
        no_symlink(settings)
        if settings.exists():
            if settings.stat().st_size > 512:
                raise MediaError('model_settings_invalid', 422)
            try:
                value = json.loads(settings.read_text())
            except (ValueError, UnicodeError):
                raise MediaError('model_settings_invalid', 422) from None
            if type(value) is not dict or set(value) != {'device'} or value['device'] not in ('cpu','cuda'):
                raise MediaError('model_settings_invalid', 422)
            self.device = value['device']
        self.model = self.tokenizer = None

    def identity(self):
        digest = hashlib.sha256((PIPELINE+':'+self.device).encode())
        digest.update(run_media(['ffmpeg','-version'],10,16384))
        for package in PACKAGES:
            digest.update((package+':'+importlib.metadata.version(package)).encode())
        for kind, root in self.paths.items():
            digest.update(str(root.absolute()).encode())
            for path in sorted(root.rglob('*')):
                no_symlink(path)
                if not path.is_file():
                    continue
                digest.update((kind+'/'+path.relative_to(root).as_posix()+'\0').encode())
                with path.open('rb') as stream:
                    digest.update(repr(file_signature(stream)).encode())
        return digest.hexdigest()

    def transcribe(self, path, duration):
        require_private_runtime()
        import numpy as np
        from faster_whisper import WhisperModel
        # Decode with the same local protocol/container restrictions as import.
        # Pass samples to Whisper so its decoder cannot resolve media references.
        raw = run_media([
            'ffmpeg','-v','error','-nostdin','-protocol_whitelist','file,pipe',
            '-format_whitelist','mov,matroska,webm','-i',str(path),'-map','0:a:0',
            '-vn','-sn','-dn','-ac','1','-ar','16000','-f','f32le','pipe:1'],
            max(120,min(1800,math.ceil(duration / 2))), math.ceil(duration * 64000) + 1048576)
        if not raw or len(raw) % 4:
            raise MediaError('invalid_media', 422)
        audio = np.frombuffer(raw, dtype='<f4')
        clips = self.speech_clips(audio)
        if not clips:
            return []
        model = WhisperModel(str(self.paths['asr']), device=self.device,
                             compute_type='int8_float16' if self.device == 'cuda' else 'int8',
                             local_files_only=True)
        try:
            # Source-time clips retain silence offsets without ORT or an
            # application-level waveform/timestamp-remapping layer.
            segments, _ = model.transcribe(audio, beam_size=5, vad_filter=False, clip_timestamps=clips,
                                           task='transcribe', language=None, multilingual=True)
            cues = []
            for s in segments:  # Materialize lazy inference before checkpointing.
                if s.text.strip():
                    cues.append({'start':float(s.start), 'end':float(s.end), 'text':s.text.strip()})
                if len(cues) > MAX_CUES:
                    raise MediaError('subtitles_too_large', 422)
            return cues
        finally:
            # Never hold the ASR and translation GPU weights simultaneously.
            del model
            gc.collect()

    def speech_clips(self, audio):
        require_private_runtime()
        import torch
        threads = torch.get_num_threads()
        model = None
        try:
            from silero_vad import get_speech_timestamps
            # CPU VAD stays small; do not occupy the ASR/translation GPU.
            torch.set_num_threads(1)
            model = torch.jit.load(str(self.paths['vad'] / 'silero_vad.jit'), map_location='cpu').eval()
            chunks = get_speech_timestamps(torch.from_numpy(audio.copy()), model,
                sampling_rate=16000, threshold=.5, min_speech_duration_ms=0,
                min_silence_duration_ms=2000, speech_pad_ms=400, return_seconds=False)
            return [chunk[key] / 16000 for chunk in chunks for key in ('start','end')]
        finally:
            del model
            # Silero's import changes this globally; retain the caller's CPU
            # configuration for later ASR/translation, including on failure.
            torch.set_num_threads(threads)

    def translate(self, text):
        result = self.translate_many([text])[0]
        if isinstance(result, MediaError):
            raise result
        return result

    def translate_many(self, texts):
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        if not 1 <= len(texts) <= self.batch_size:
            raise ValueError('invalid translation batch')
        if self.model is None:
            if self.device == 'cuda' and not torch.cuda.is_bf16_supported():
                raise MediaError('model_bf16_unavailable', 503)
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.paths['translation']), local_files_only=True, trust_remote_code=False)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                str(self.paths['translation']), local_files_only=True, trust_remote_code=False,
                use_safetensors=True, torch_dtype=torch.bfloat16 if self.device == 'cuda' else torch.float32)
            self.model.to(self.device).eval()
        tokens = [self.tokenizer('<2ko> '+text, truncation=False) for text in texts]
        results = [MediaError('translation_input_too_long', 422) for _ in texts]
        usable = [i for i, value in enumerate(tokens) if len(value['input_ids']) <= 512]
        if not usable:
            return results
        inputs = self.tokenizer.pad([tokens[i] for i in usable], padding=True, return_tensors='pt')
        with torch.inference_mode():
            output = self.model.generate(**inputs.to(self.device), max_new_tokens=512, num_beams=4, do_sample=False)
        eos = self.model.config.eos_token_id
        for index, sequence in zip(usable, output):
            # Batched shorter outputs are padded after EOS.
            if eos not in sequence.tolist():
                results[index] = MediaError('translation_truncated', 422)
                continue
            result = self.tokenizer.decode(sequence, skip_special_tokens=True).strip()
            results[index] = result if result else MediaError('translation_empty', 422)
        return results

    def close(self):
        self.model = self.tokenizer = None
        gc.collect()
        import torch
        if self.device == 'cuda':
            torch.cuda.empty_cache()
