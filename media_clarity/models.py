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

PIPELINE = 'korean-subtitles-v3:sentence-12s-400ch-gap0.8:madlad-ko-bf16-beam4-512-batch2:stat-identity'
PACKAGES = ('faster-whisper','ctranslate2','transformers','torch','sentencepiece','tokenizers','numpy','onnxruntime','av')


def require_private_runtime():
    # Official Windows ORT wheels may emit ETW initialization before the disable
    # API is callable. Keep inference closed until a telemetry-free build is verified.
    if sys.platform == 'win32':
        raise MediaError('model_privacy_setup_required', 503)


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
    if check_packages and any(importlib.util.find_spec(n) is None for n in ('faster_whisper','transformers','torch','sentencepiece')):
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
        # ORT's initialization can send telemetry before its Python API is callable.
        # Disable that path before import, then also disable platform trace events.
        os.environ['ORT_DISABLE_TELEMETRY'] = '1'
        import onnxruntime
        onnxruntime.disable_telemetry_events()
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
        model = WhisperModel(str(self.paths['asr']), device=self.device,
                             compute_type='int8_float16' if self.device == 'cuda' else 'int8',
                             local_files_only=True)
        try:
            segments, _ = model.transcribe(audio, beam_size=5, vad_filter=True,
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
