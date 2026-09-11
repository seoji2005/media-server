# Current subtitle path · September 11, 2026

The owner selected **Qwen3-ASR-1.7B → Qwen3-ForcedAligner-0.6B → Gemini
3.8 Flash** for new jobs. The v5 prompt/context, strict IDs and low thinking match
the selected comparison configuration. Existing Lite v5 and earlier jobs keep their
original model and configuration; a restart does not upgrade them. This is the product choice, not a claim that Qwen won an independent
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
Optional scene search uses `requirements-scene.txt` in this same environment.
Its Torch/Transformers/Pillow pins match Qwen; do not install the legacy
`requirements-models.txt` over it. See [scene setup](scene-search.md).

If HTTPX fails while constructing its client with a missing `socksio` error, and
this environment already supplies an approved HTTP/HTTPS proxy in `https_proxy`
or `HTTPS_PROXY`, the explicit setup-only option is:

```powershell
.\.venv\Scripts\python scripts/prepare_qwen_models.py --use-system-https-proxy
```

Lowercase `https_proxy` takes precedence when nonempty. This selects that existing
HTTPS route without initializing an unrelated SOCKS `ALL_PROXY`; it does not set
or change any environment variable, proxy address, model revision, dependency or
application runtime. No direct, alternate proxy or mirror fallback is introduced.
The default command remains unchanged. Custom libraries still need `--data-dir`.
TLS verification and certificate environment settings stay enabled (`trust_env=True`),
and the installed Hugging Face request hook retains its offline guard. Missing client
factory/hook APIs stop setup with an environment error; do not upgrade blindly.
Initialization is checked with HTTPX 0.28.1 / huggingface_hub 1.31.0 without sockets;
that is not authentication, download or internet-connectivity evidence.

This does not fix `network approval was cancelled before a decision was returned`.
The cause of that separate execution-tool error is unverified; existing user consent
is not proof that the execution service can complete a request. A local client fix,
cache rescan or new conversation alone is not grounds to repeat a blocked request.
When execution access is demonstrably restored, supervise setup with finite total
time, asset-progress and retry limits. Client defaults (10 s connect / 30 s other
I/O) are not a whole-download deadline; Hugging Face can supply per-request timeouts
and retries. Preserve partial assets/checkpoints and terminate owned processes if
limits or the repeated approval-cancellation condition are reached.

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
  Decoded PCM lives in an automatically removed temporary file beside the owned
  input; only up to 30 seconds plus one lookahead sample are read into RAM.
  Allow about 440 MiB of temporary disk space for two hours, plus the existing
  32 MiB reserve. Low disk space, timeout, malformed output or exceeding the
  output cap stops the job without publishing a partial transcript. Normal close,
  failure and worker exit release the temporary file. Resume still decodes the
  complete audio and verifies saved recognition hashes; this is a memory bound,
  not a persistent PCM cache or a claim of faster inference. Historical v1/v2
  profiles, sample bytes, time origins and evidence identities remain unchanged.
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
- New Gemini `faithful-context-v5-flash38` requests (and preserved Lite v5 jobs) add the preceding two saved source/Korean
  pairs (each text capped at 400 characters) as context, never additional targets.
  The context is rebuilt from this job's verified checkpoints after interruption;
  it does not read another track's translations or user corrections. The prompt
  preserves supported register/terminology and leaves unfinished phrases open
  instead of borrowing and repeating the next target's continuation. It does not
  delete source repetitions or change ASR text/times. This is translation guidance,
  not proof that an uncertain speech boundary has been repaired.
- The v5 prompt also preserves culture-specific named holidays, places and customs
  using their Korean names or faithful transliteration. It prohibits substituting
  a Korean cultural analogue or inventing shared nationality/ownership. This is
  guidance, not an automatic named-entity quality guarantee.
- Gemini v3/v4/v5 requests constrain array length and ID enum to
  exactly the target set. The strict response validator still rejects extra,
  reordered, missing and duplicate IDs. No trimming, repair or automatic retry.
  [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output).

Schema v9 leaves old jobs' speech profile NULL, retaining their legacy Whisper
identity. Historical Gemini v1/v2/v3/v4 prompts and request/response schemas remain byte-for-byte
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

## Measure local speech cost

After installing the existing runtime and models, an explicit offline probe can
measure the actual speech path without translation or library jobs:

```powershell
.\.venv\Scripts\python scripts/probe_qwen_speech.py --input SAMPLE.mp4 --duration 35 --data-dir MODEL_DATA_DIR --output NEW_OUTPUT_DIR --threads 4
```

Use the source duration in seconds and `--audio-index` for a nondefault audio track.
The output directory must be new and outside the checkout. After each new span,
`checkpoint.json` atomically publishes its raw dialogue/evidence and bound summary.
Treat this file as private. A killed process leaves the previous complete snapshot
or the new one; an unfinished temporary file is never used for recovery. This does
not protect against removal of the entire workspace or establish power-loss/disk
durability. Copy the single checkpoint to durable storage during expensive trials.
When the process finishes normally or handles an error, `parts.json` and
`summary.json` are also exported for inspection. The latter contains only hashes,
runtime identity, package versions, counts and timings. New recovery always reads
the single checkpoint; incomplete, stale or missing final exports cannot replace it.
The probe does not download models and blocks Python network access. Use the
explicit setup command first. No Gemini, database, player or saved-track change.

Each ASR and alignment call measures load (processor and weights through device
transfer), input preparation, inference, result decoding/validation, and cleanup
(reference release and existing garbage collection/cache cleanup). Normal app jobs
leave timing disabled, with no clock calls or added CUDA synchronization. The probe
synchronizes CUDA at model-work boundaries; cleanup adds no synchronization that
could prevent reference release or mask the original failure. Failed phases are
partial observations. The speech total also includes PCM decoding, segmentation and evidence
validation, excluding checkpoint verification and publication. `checkpoint_seconds`
in the final summary reports that separate cost; a live checkpoint counts preceding
publications, excluding its own write. Setup/import/identity time is separate. These timings include observer
overhead and filesystem cache state; they are not a cold-start or target-device claim.

`--resume-from PREVIOUS_OUTPUT_DIR` verifies the checkpoint's input hash, runtime
identity, profile, duration, audio selection and canonical parts hash before using
the production span validator. Saved spans and new spans are counted separately;
a complete saved input should make zero ASR/alignment calls. `--reuse-spans N` selects
a bounded prefix only after verification; it never modifies the prior evidence.
Old probe directories with no `checkpoint.json` can still use the final summary and
parts, with the same strict verification. A present but invalid checkpoint is never
bypassed by those exports. Original input and model identity are checked before
each checkpoint and again after processing. A rejected production checkpoint is
not republished as resumable. An error or
unresolved span leaves `complete: false`; it is not a successful performance sample.
Do not commit raw outputs or infer broad quality/speed from a single short clip.

## Verification boundaries

Regression tests exercise the prefix split, zero-time preservation, strict Gemini
schema, completed-window recovery, old-profile migration, provided-caption retry,
foreign-caption translation and bounded opt-in library reads. Actual model execution,
browser results and remaining target gates are recorded in [current](current.md).
Fixtures establish contracts and recovery, not natural-language quality.
