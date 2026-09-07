# Korean subtitle preparation

This is an incremental implementation, **not a real-model quality sign-off**.
Original watching does not depend on subtitle jobs. Video download, generation and
NAS remain excluded. Public model-weight setup below is separate from video downloading.

## Watching with existing subtitles

Open a video → **자막 파일 열기** → choose its Korean SRT (UTF-8 or CP949/EUC-KR, ≤2 MiB).
The app sorts cues by time, skips empty/outside cues and clips valid cues at the video
end. One-digit hours and trailing positioning settings are accepted; positioning is
ignored. Adjustment counts appear for the selected version. Invalid timing, controls,
oversized text/files or excessive cue counts still fail; no usable cues is diagnosed.
It stores a new version and serves escaped plain-text WebVTT. Previous versions remain
selectable. Common SRT styling is removed for display; literal angle-bracket text and the
original uploaded SRT bytes are preserved. Decoding is strict UTF-8 first, then CP949
(including EUC-KR), with no replacement characters. SMI/SAMI, ASS/SSA, embedded subtitle extraction and automatic
language verification are not implemented. Choose **자막 끄기** to hide captions.
Source SRT files and source videos are never written. Imported text is treated as
Korean because the user selected it for the Korean track; the app does not certify it.

Generated versions with a saved transcript offer **한국어 · 자동 번역** and
**원문 · 자동 전사** in the same selector. Korean remains the initial choice; switching
preserves playback position and uses the selected version's job, source hash and audio.
The read-only transcript response verifies its hash and cue schema, escapes WebVTT,
and retains stored ASR wording/timing without Korean layout or new model calls.
Corrupt or mismatched transcripts are refused; existing Korean captions remain usable.
ASR can be wrong too. Imported SRT and legacy versions without a transcript retain
their existing behavior. Search follows whichever caption variant is selected.

Open **자막에서 장면 찾기** and enter a word or phrase in the selected subtitle.
Results show matching text and timestamps; choose one to seek and play. The existing
completed-seek handler saves the watch position. Search is a literal, Unicode-normalized
substring match, not visual/semantic scene analysis. It uses only this player's loaded
track in browser memory; no query API, saved search history, or global indexing.
Empty queries show no transcript; at most 50 matches are displayed. Native captions
Off and app track/item changes invalidate old results. Closing clears the query.

## Optional local models — CPU verified, target Windows pending

### Translating a saved transcript again

Select a generated subtitle version (Korean or its automatic transcript), then choose
**저장된 원문으로 다시 번역**. This creates a new Korean version from that exact saved
transcript and audio selection. It does not repeat audio decoding, VAD or ASR. Existing
versions remain available during processing; select the new version when it is ready.
The original transcription can still contain recognition errors, and running the same
translator again does not promise better wording. Use **새 자막 만들기** when fresh speech
recognition is needed instead.

Retranslation needs only the local translation weights/runtime. The standard environment
check still checks full ASR + translation setup. The new job freezes the selected source
and translation configuration before queueing. Pause/resume retains completed translation
units; changed configuration requires **번역 처음부터 다시** with the same saved source.
The original job, transcript serialization, original media and previous subtitle versions
remain preserved. Imported SRT and subtitles without a verified saved transcript do not
offer this action.

`POST /api/library/{item_id}/subtitles/{track_id}/retranslate` uses the existing session
token/same-origin boundary and returns a job ID. The source version determines audio;
there is no separate client-supplied audio override. The schema's nullable source reference
does not change existing jobs' configuration identity or normal ASR resume behavior.

### Model setup

These adapters are a reversible baseline, not a model-selection verdict:
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) with
[large-v3](https://huggingface.co/Systran/faster-whisper-large-v3), followed by
[MADLAD-400-3B-MT](https://huggingface.co/docs/transformers/en/model_doc/madlad-400).
ASR source text/timing and Korean translations are stored separately. MADLAD uses
its `<2ko>` target prefix. Adjacent fragments join through sentence punctuation, capped
at 12 seconds, 400 characters and a 0.8-second gap; existing longer cues remain intact.
One translated sentence retains the combined original interval in storage. New tracks
also store a separate two-line display presentation, with sequential timing bounded
by that interval. Existing ready tracks are never reflowed during reads. This does not
claim word alignment or exact within-sentence timing. Untouched ASR cues and translation
checkpoints remain stored. [Readability rules, warnings and evidence](subtitle-readability.md).
Hangul-only text, including explicit numeric units such as `15m`, passes through per
unit unchanged; other foreign letters still require translation. Generated translation
entities decode once before validation and escaped WebVTT output. Source/fallback text
does not take that normalization path.
MADLAD runs batches of two with beam four, CUDA bfloat16 or CPU float32. Unsupported
CUDA bfloat16 is diagnosed rather than silently using float16. GPU models run
sequentially; CUDA bfloat16 execution and 12 GB feasibility are still unmeasured.
The native SentencePiece tokenizer handles both source encoding and output decoding;
the pinned model's fast tokenizer loses rare input characters and exposes generated
byte tokens instead of some Hangul. Setup requires `spiece.model` and the explicit
`protobuf` dependency in `requirements-models.txt`. The pipeline identity changes,
so an older partial translation requires a new job; existing ready tracks remain saved.
This repairs character handling, without claiming better translation meaning.

After setup, check the actual tokenizer without loading model weights:

```sh
.venv/bin/python scripts/check_translation_tokenizer.py --model-dir "$MEDIA_CLARITY_DATA/models/translation"
```

The app does **not** download models, call hosted inference, accept license prompts,
load remote Python code or fetch missing tokenizer files. Prepare public model files
separately after checking their model cards and applicable terms; any explicit license
acceptance remains an owner action. Media and transcripts are never sent in setup.

Voice activity detection uses the official **Silero v6 TorchScript** model bundled in
`silero-vad==6.0.0`. It runs on CPU with the previous speech threshold, minimum speech,
silence and padding settings. The original waveform and source-time speech clips go
to faster-whisper; silent gaps retain their original positions. An all-silent input
stops as no speech before loading Whisper. Speech detection remains enabled.
[Silero local JIT support](https://github.com/snakers4/silero-vad/tree/v6.0).

Before dependency imports, the app refuses an already-loaded ONNX Runtime and blocks
future `onnxruntime` imports in that process. No ORT initialization or disable API is
used. ORT remains installed to satisfy upstream package metadata, but is not executed.
The unconditional Windows veto is removed; **Windows/CUDA/RTX operation is still
unverified**. No telemetry permission or private-data egress is enabled. The earlier
initialization issue is described by [ORT privacy controls](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md).

Linux CPU setup used Python 3.12.13 and matching official CPU Torch/TorchAudio wheels. Prepare at
least 15 GB for these weights plus runtime/cache and media working space. Public model
revisions used for the check are fixed below; this does not certify future revisions.
Set `MEDIA_CLARITY_DATA` to the same external directory passed to the app's `--data-dir`.

```sh
.venv/bin/python -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements-models.txt
.venv/bin/python -m pip check
.venv/bin/hf download Systran/faster-whisper-large-v3 --revision edaa852ec7e145841d8ffdb056a99866b5f0a478 --local-dir "$MEDIA_CLARITY_DATA/models/asr" --include "*.json" "model.bin"
.venv/bin/hf download google/madlad400-3b-mt --revision fa184c675da0b5c9e1c8694fccd4e12e2d422094 --local-dir "$MEDIA_CLARITY_DATA/models/translation" --include "*.json" "*.safetensors" "*.model"
```

On Windows, after the base app setup in README, the target CUDA preparation is:

```powershell
$env:MEDIA_CLARITY_DATA = "$env:LOCALAPPDATA\MediaClarity"
.\.venv\Scripts\python -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python -m pip install -r requirements-models.txt
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\hf download Systran/faster-whisper-large-v3 --revision edaa852ec7e145841d8ffdb056a99866b5f0a478 --local-dir "$env:MEDIA_CLARITY_DATA\models\asr" --include "*.json" "model.bin"
.\.venv\Scripts\hf download google/madlad400-3b-mt --revision fa184c675da0b5c9e1c8694fccd4e12e2d422094 --local-dir "$env:MEDIA_CLARITY_DATA\models\translation" --include "*.json" "*.safetensors" "*.model"
.\.venv\Scripts\python -m media_clarity --data-dir "$env:MEDIA_CLARITY_DATA"
```

Install Torch and TorchAudio together from the same CPU/CUDA index; mixing CPU Torch
with a CUDA TorchAudio wheel can fail during Silero import. These commands follow
[PyTorch's 2.8 wheel matrix](https://pytorch.org/get-started/previous-versions/#v280).
The Windows commands have not run here. A compatible NVIDIA driver and CTranslate2's
[CUDA 12 cuBLAS/cuDNN 9 libraries](https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1#gpu)
must be available to the worker; wheel installation alone does not certify that setup
or the model's 12 GB fit. Any explicit installer license acceptance remains yours.

Models stay outside Git. CPU is the non-Windows default, CUDA is the Windows default;
`models/settings.json` accepts `{"device":"cpu"}` or `{"device":"cuda"}` with no silent
device fallback. The worker retains Hugging Face offline/telemetry settings and blocks
ORT imports. These are dependency controls, not an OS network sandbox. Linux package
resolution and real ASR ran successfully; target Windows/CUDA/12 GB fit remains open.
The [resolved Linux CPU environment](model-runtime-linux-cpu.txt) records that run;
it is not a Windows/CUDA lockfile. `pip check` reported no broken requirements.

## Runtime preflight

Open **설정 → 자막 실행 환경 → 실행 환경 확인** from the library. `/api/session` reports the
selected device and whether it came from the default or explicit settings, without
importing the heavy runtimes. The button runs an isolated check; it never loads large
ASR/translation weights or reads a video. It does not change devices automatically.
To choose CPU deliberately, put `{"device":"cpu"}` in the existing data directory's
`models/settings.json`; remove that setting to restore the platform default. Device
and runtime package identities still bind resumable results; changing them can require
a fresh job. Existing ready subtitles remain available.

With the app stopped, the same check is available in PowerShell:

```powershell
.\.venv\Scripts\python -m media_clarity doctor --models
```

Use the same `--data-dir` as the app when overriding its location. Basic `doctor`
remains usable without optional models; `--models` returns exit 0 for a passed basic
model check and exit 1 for blocked preparation. Both emit fixed, path-free JSON.

| Diagnostic | Action |
| --- | --- |
| `local_models_missing` / `model_runtime_missing` | Finish the local file/package setup above. |
| `model_settings_invalid` | Use exactly one `device` field with `cpu` or `cuda`. |
| `model_cuda_unavailable` | Check the CUDA PyTorch wheel and NVIDIA driver; CPU wheels cannot run CUDA. |
| `model_bf16_unavailable` | Native bfloat16 is required on the selected GPU; do not substitute float16. |
| `model_asr_cuda_unavailable` / `model_asr_runtime_unavailable` | Check CTranslate2's CUDA support and native libraries. |
| `model_asr_precision_unavailable` | The selected ASR `int8`/`int8_float16` mode is unsupported. |
| `model_audio_runtime_unavailable` | Reinstall matching Torch/TorchAudio versions from the same CPU/CUDA index. |
| `model_runtime_incompatible` / `model_torch_unavailable` | Check the documented package/runtime installation. |
| `model_check_timeout` / `model_check_failed` | Retry after checking other work or restarting the app; raw native error text is deliberately not exposed. |

The worker repeats checks before ASR, including PyTorch CUDA availability, native
bfloat16 (`including_emulation=False`) and CTranslate2
[device presence](https://opennmt.net/CTranslate2/python/ctranslate2.get_cuda_device_count.html)/
[supported compute types](https://opennmt.net/CTranslate2/python/ctranslate2.get_supported_compute_types.html).
Runtime imports restore the prior Torch thread count after Silero initialization.
`ready` describes these basic checks, not successful full model inference, dynamic
cuDNN loading, 12 GB fit, processing speed or output quality. Only a real Windows/RTX
end-to-end run can establish those. GPU capability failures are tested with doubles
here; actual Windows drivers and CUDA are unavailable.

The UI check waits separately from playback, refuses active/orphan inference and
serializes with the existing job supervisor. Its child owns the worker lease, watches
the parent's pipe and is killed/reaped after a 60-second timeout. Native stdout/stderr
are suppressed; only bounded validated status JSON returns. Heavy runtime imports
stay out of the server. Dependency offline/ORT controls remain; this is not an OS
network sandbox. A buffered stdin watcher was observed aborting at normal Python
shutdown; the diagnostic and existing subtitle worker now use an unbuffered OS read.

At local `bc4a596`, actual CPU `doctor --models` passed in 1.947 s. An explicit CUDA
configuration with the real CPU wheel returned `model_cuda_unavailable` in 1.285 s,
without switching to CPU (placeholder file layout for this environment-only failure
probe, no weight inference). Both emitted zero stderr bytes. The same installed real
models regenerated the existing Japanese FLEURS sample in 40.91 s, with unchanged
ASR/translation/VTT, exact Range/source checks and zero server logs. This repeats short
speech, not a new quality corpus or throughput benchmark.

At final local `e2bcd10`, the production HTTP check passed in 1.626 s; an in-process
observer confirmed the server had no Torch/CTranslate2/Transformers/Silero modules and
no loaded ORT after the check. Logs stayed empty. Actual Chromium 149 at `bc4a596`
showed the selected CPU, checked preparation, kept library requests available and
repeated Korean caption playback/seek/Off/On/4.25 s resume. All 14 previous VTT tracks
remained byte-identical after the real run, browser and store restart. This is Linux
headless evidence; the exit-only remediation does not change the browser or pipeline.

Verification: full Python 85 passed at `bc4a596` (14.108 s); final focused 11 diagnostic
tests passed at `e2bcd10` (1.063 s). Tests include actual timeout kill/reap, noisy native
output suppression, parent EOF, normal worker exit, token checks and active/orphan
exclusion. Fresh review found a lease release before native teardown; fixed by holding
it through controlled process exit. Rereview's native teardown/output-stall reproductions
passed with no remaining actionable findings. Earlier failed probes exposed the buffered
stdin shutdown abort; the first browser-server import observer was interrupted by normal
server signal handling and was replaced by observation while the server was alive.

## Earlier execution evidence

The initial real-ASR probe was blocked by automatic approval review because ORT
attempted incidental Microsoft telemetry. The corrected adapter completed an
[11-second public speech sample](https://github.com/ggml-org/whisper.cpp/blob/master/samples/jfk.wav)
in 23.16 s on an AMD EPYC CPU environment (9 vCPUs, about 21 GiB RAM, no GPU).
Repeating that audio three times in a synthetic MP4 produced three ASR cues in
79.79 s. Repetition is only a recovery fixture, not varied speech/quality evidence.
Native network tracing was unavailable (`ptrace: Operation not permitted`).

At implementation `67f5e8e`, actual CPU TorchScript VAD on a 33-second public
speech/silence fixture produced exactly the previous Silero v6 ONNX sample boundaries:
3.920–14.896 and 19.120–29.872 seconds. Five seconds of silence produced no clips.
First JIT VAD call took 0.555 s; the four-thread Torch setting was restored. In that
standalone process ORT was absent from Python modules and native mappings, and a
Python socket-connect audit hook recorded zero attempts. This is not native packet tracing.

The production CLI/HTTP pipeline then completed a **48-second fixture** (three public
11-second speech repetitions separated by four-second gaps) in **95.93 s**, including
pause and server restarts. Three Korean cues retained source intervals 3.920–14.380,
19.120–29.380 and 34.160–44.360. ASR retained the repeated English sentence and the
Korean translation stayed consistent. After two saved units at 68.53 s, pause stopped
processing. Forced server restart preserved transcript hash, exact batch bytes and
5.25 s watch position; attempt two processed only the remaining unit. Ready VTT survived
another restart byte-for-byte, Range bytes matched, source hash stayed unchanged,
and server logs were zero bytes. Text/timing were inspected; actual browser readability
and human quality remain open. Prior 33-second runs used different silence/input handling
and are not comparable speed benchmarks or movie-runtime estimates.

An initial observer probe stopped because the child PID namespace did not match mounted
procfs. Its unfinished job was preserved and restarted. The successful HTTP run does not
claim child native mapping observation. The standalone VAD process above supplies that
limited observation; full native tracing and target Windows evidence remain unavailable.

Real MADLAD CPU float32 also translated two author-written fragment pairs. Japanese
`駅に着いたら、` + `私に電話してください。` translated together as
“역에 도착하면 전화해주세요”; separate fragments lost that conditional connection.
The English joined sentence retained the complete meaning but remained literal in
style. This checks actual text output, not Japanese ASR or general translation quality.
At the prior `f2a3ba3` checkpoint, model identity took 71.52 ms with the installed full weights; it no longer reads weight
bytes on each job. Whole-file download hashes below were verified once during setup.

Synthetic bookkeeping measurements on the same Linux machine (no model computation,
real SQLite FULL commits; 20 units/batch, import excluded):

| Units | Seconds | Appended batches | Stored payload characters |
| --- | --- | --- | --- |
| 250 | 0.014 | 13 | 12,744 |
| 500 | 0.021 | 25 | 25,465 |
| 1,000 | 0.038 | 50 | 50,930 |
| 2,000 | 0.091 | 100 | 101,860 |
| 4,000 | 0.148 | 200 | 203,720 |

This demonstrates bounded appended storage; it does not measure Windows fsync or
real speech timing. The initial benchmark fixture used sub-millisecond intervals
and correctly failed timestamp validation; these measurements use valid intervals.

Recorded SHA-256 identities:

| Public file | SHA-256 |
| --- | --- |
| Speech WAV | `59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e` |
| large-v3 model.bin | `69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1` |
| MADLAD model.safetensors | `66ff5f8fcaf92291da486fdfbd4d5233cec90e1359348a56e3172c978b3a76d4` |

The MADLAD digest was compared with its pinned Hugging Face LFS metadata. Model
cards label large-v3 MIT and MADLAD Apache-2.0; neither download required a gated
license acceptance. Weights, source media and generated captions stay out of Git.

Once prepared, open a video → **한국어 자막 만들기**. When a supplied/ready version
exists, **새 자막 만들기** explicitly creates another version; existing versions stay
selectable during processing. Only one active job per video is allowed. Missing
weights/runtime show a local diagnostic. Progress shows saved translation units and
the number left as source text. Such segments show **[원문]** in the actual caption.

## Recovery and limits

- Playback audio is selectable; new jobs freeze that original audio ordinal. Switching
  playback does not change a running/paused job or its restart. Caption versions show
  their audio; another voice's track is not auto-selected. New audio decode preserves
  start offsets and gaps. Saved pre-upgrade transcripts can finish translation unchanged;
  an older interrupted ASR without a transcript may require **처음부터 다시 만들기**.
  [Audio selection, migration and real playback evidence](compatible-renditions.md#audio-selection-follow-up).
- An OS worker lock survives server death and native inference stalls. A new server
  waits for the old worker to exit before recovery or another inference; original
  watching stays available. Attempts also condition checkpoint/publication writes
  on their claimed generation. Processing continues when the player closes.
- **일시정지** stops the child; **처리 재개** retries with durable completed results.
- An interrupted running job becomes paused on server startup. A completed transcript
  is reused. New ASR jobs also save each completed Silero speech span atomically,
  with its source interval, cues and hash; resume checks the same VAD plan and skips
  saved inference. Silence boundaries avoid hard cuts inside speech. The last 200
  plain-text tokens restore prior context; fresh predicted timestamps are intersected
  with the input span before strict storage validation. The UI shows saved span count.
  Full audio decode/VAD still repeat, and uninterrupted speech has **no fixed maximum
  replay interval**. This is partial ASR recovery, not bounded-memory streaming or word
  alignment. Existing complete transcripts retain their old translation identity.
  [Actual CPU interruption comparison](quality-check.md#speech-span-checkpoints--2026-09-07).
- Translation resumes after the last committed batch. New completed units
  append atomically every 20 units or after a batch completes at least five seconds
  after the last save. No growing prefix is rewritten. A hard stop repeats at most
  20 units; the five-second threshold does not interrupt an in-flight generation.
  Completed pending outputs also save on a caught runtime error. Within-span ASR and
  within-unit translation are not checkpoints.
- Original byte identity, model paths/file metadata (device, inode, size, modification/
  change time), execution device, adapter settings and dependency versions bind reusable
  results. This is a change fingerprint, not a fresh model byte-integrity certificate.
  Changed model/config refuses reuse; restore the old
  setup to resume, or choose **처음부터 다시 만들기** for a new job with current
  settings. This preserves previous jobs, checkpoints and caption versions.
  Pipeline v5 (numeric Korean units and generated plain-text handling) invalidates
  unfinished jobs from previous adapters;
  restart creates a new job without deleting the old results. Existing ready versions
  and legacy checkpoint storage remain readable. Original/caption tampering fails closed.
- Source/caption versions remain available after failure. A job publishes its full
  track only after validation; it never overwrites an imported SRT.
- FFmpeg reads the managed original directly under the existing protocol/container
  restrictions. Verify before/after decoding and before publication; no extra full
  video is copied into `processing/`. Old crash leftovers are not automatically removed.
  Back up the complete data directory with the server stopped.
- No silent input truncation. Overlong input, empty or unfinished translation retains
  that unit's source text with a saved warning and visible **[원문]**. Other units
  continue. Runtime/memory/storage errors stop with recoverable completed results.
  Empty ASR is reported as no speech, not a fabricated ready subtitle.
- The [actual multilingual speech check](speech-quality.md) covers short public
  Japanese/English/Korean recordings and concatenated language changes. It exposed
  remaining recognition/translation errors; natural mixed speech, long-video runtime,
  Windows/CUDA, GPU memory and human quality remain unverified. Short Linux Chromium
  decoding/caption/seek/resume evidence is recorded in [readability](subtitle-readability.md).

The next required target evidence is Windows/RTX installation and real browser caption
playback/seek/resume. Broaden speech quality checks to natural language changes and long
videos; the limited CPU corpus does not establish readiness for everyday watching.
