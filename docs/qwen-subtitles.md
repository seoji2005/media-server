# Current subtitle path · September 9, 2026

The owner selected **Qwen3-ASR-1.7B → Qwen3-ForcedAligner-0.6B → Gemini
3.1 Flash-Lite**. This is the product choice, not a claim that Qwen won an independent
quality benchmark. Fresh HTTP jobs use this path even when the request body is empty.
The only accepted new translation provider is `gemini`. No automatic fallback.
Opening a video sends nothing; the labeled action still discloses text egress and cost.

## Install

Keep Python 3.12 and the normal `requirements.txt`. Install the appropriate official
PyTorch 2.8 CPU/CUDA wheel for the machine, then:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-qwen.txt
.\.venv\Scripts\python scripts/prepare_qwen_models.py
.\.venv\Scripts\python -m media_clarity doctor --models
$env:GEMINI_API_KEY = 'YOUR_KEY'
.\.venv\Scripts\python -m media_clarity
```

On Linux use `.venv/bin/python`. A custom library needs the same `--data-dir` on
setup, diagnostics and application commands. Models use `models/qwen-asr` and
`models/qwen-aligner`. `models/settings.json` still selects only `cpu` or `cuda`;
Windows defaults to CUDA, other systems to CPU. CUDA is float16, CPU float32.
Only one model is loaded at a time. No target 12 GB fit or Windows inference claim.

Gemini connects directly by default. If the runtime requires a trusted system HTTPS
proxy (including this Work environment), explicitly set `MEDIA_GEMINI_USE_SYSTEM_HTTPS=1`
before launching the server or resuming a job. This uses the platform's configured
HTTPS route; verify that you trust it with the API key and dialogue. It does not
change the official Google endpoint, TLS verification, redirect prohibition,
request/response validation or retry policy. Leave the option unset for direct
connections. The worker inherits it; no transcription or successful translation
batches need to be repeated just to change the network route.

Existing complete caches can be reused without copying several gigabytes: place an
explicit `{"asr":"ABSOLUTE_SNAPSHOT_DIRECTORY","aligner":"ABSOLUTE_SNAPSHOT_DIRECTORY"}`
in the private library's `models/qwen-paths.json`. Each model must have its correct
architecture/size. HF snapshot symlinks are accepted only for the pinned revisions
below and only into that model cache's own `blobs` directory. Other symlinks fail.
Runtime identity includes resolved assets, file signatures, dependencies and settings.
Never commit this file or private paths.

| Native Transformers model | Pinned revision |
| --- | --- |
| `Qwen/Qwen3-ASR-1.7B-hf` | `bcd2b5b7f32b480ab5790554cfa8347f246a14f3` |
| `Qwen/Qwen3-ForcedAligner-0.6B-hf` | `c07281df297b9905d24a508279258cccf987a064` |

Native support uses Transformers 5.16.1, local files, safetensors and
`trust_remote_code=False`. Japanese alignment needs nagisa; Korean alignment needs
soynlp. The latter is checked when Korean is detected, so an existing Japanese-only
runtime can still run. Speech language is automatically detected. The aligner supports
11 languages; unsupported detected speech is preserved and stops the job.
[Official ASR model](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf),
[official aligner](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B-hf).

## Text, timing and recovery

- Decode the selected original audio with existing restricted FFmpeg behavior.
  Cover every sample with committed, contiguous spans. Recognize at most 30 seconds
  per call. Prefer 300 ms of low
  energy in seconds 20–30 for a cut. Never discard quiet audio through VAD.
  A forced cut remains flagged; this heuristic does not prove perfect word seams.
- New Qwen v2 jobs can move a forced cut back to an internal punctuation boundary
  verified by the aligner, after at least 20 seconds of progress. The trailing
  audio is recognized again in the next window, with at most ten seconds of
  overlap in recognition work. Only the earlier complete phrases are committed;
  no repeated-word deletion or guessed source-text repair is applied. If there
  is no suitable late boundary, preserve the forced cut and its review indication.
  Quiet cuts and the final window keep their existing envelope.
- Each v2 checkpoint retains the whole recognition text, raw/official word times,
  full recognition-audio hash and recognition end, alongside the shorter committed
  span. Resume verifies the full recognized audio, including the deferred suffix,
  and restarts from the committed end. The committed cue subset is reconstructed
  from the evidence during validation. An interrupted suffix cannot disappear
  silently from a ready track: translation starts only after the speech stage ends.
- Recognize without context prompts, then separately align the recognized text.
  Persist complete windows with input-audio hash, exact source text/language, raw
  timestamps, official corrected timestamps and derived source phrases.
- Map aligned words back to exact source characters. Punctuation supplies phrase
  boundaries; an internal time gap cannot split `おめでとう` into `お / めでとう`.
  Do not invent source timings by dividing the whole window proportionally.
- The aligner's final 80 ms timestamp tick may be clipped to the actual audio end;
  larger overruns remain unresolved. Raw and official timestamps are retained, and
  the window receives a timing-review indication.
- A zero-length phrase may join an adjacent phrase's real time envelope. Otherwise
  retain its text/times in a failed checkpoint and publish no partial subtitle track.
  Repeated resume of unresolved evidence stops without Gemini calls. Restart creates
  a separate attempt/job and preserves the failed evidence and all older tracks.
- Translation uses the source phrases without inserting spaces between Japanese
  subwords. Korean display layout remains an explicit proportional display rule,
  not Korean word alignment. Long punctuation-free phrases can remain long and
  need reading/timing review; no general subtitle-quality completion claim.
- New Gemini `faithful-context-v4` requests add the preceding two saved source/Korean
  pairs (each text capped at 400 characters) as context, never additional targets.
  The context is rebuilt from this job's verified checkpoints after interruption;
  it does not read another track's translations or user corrections. The prompt
  preserves supported register/terminology and leaves unfinished phrases open
  instead of borrowing and repeating the next target's continuation. It does not
  delete source repetitions or change ASR text/times. This is translation guidance,
  not proof that an uncertain speech boundary has been repaired.
- Gemini v3/v4 requests constrain array length and ID enum to
  exactly the target set. The strict response validator still rejects extra,
  reordered, missing and duplicate IDs. No trimming, repair or automatic retry.
  [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output).

Schema v9 leaves old jobs' speech profile NULL, retaining their legacy Whisper
identity. Historical Gemini v1/v2/v3 prompts and request/response schemas remain byte-for-byte
recoverable. New UI defaults do not relabel those jobs. Restoring their original
runtime can still be necessary: the old optional `requirements-models.txt` pins
Transformers 4.57.1 and must not be installed on top of the new Qwen environment.
Old subtitle tracks remain watchable without either model runtime. Retranslation
needs only Gemini, and keeps the original source units and audio selection.
Historical Qwen v1 jobs also retain their original fixed-window identity, evidence
format and phrase grouping; resuming/restarting them does not apply v2 handoffs.
Create a new subtitle job to use the new segmentation policy.

Provided foreign captions accepted through the companion endpoint can also be
translated directly with Gemini. Their original text/times/bytes remain preserved;
neither ASR nor an aligner runs. Korean provided tracks already avoid needless ASR.

## Verification boundaries

Regression tests exercise the prefix split, zero-time preservation, strict Gemini
schema, completed-window recovery, old-profile migration, provided-caption retry,
foreign-caption translation and bounded opt-in library reads. Actual model execution,
browser results and remaining target gates are recorded in [current](current.md).
Fixtures establish contracts and recovery, not natural-language quality.
