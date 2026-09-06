# Korean subtitle preparation

This is an incremental implementation, **not a real-model quality sign-off**.
Original watching does not depend on subtitle jobs. Video download, generation and
NAS remain excluded. Public model-weight setup below is separate from video downloading.

## Watching with existing subtitles

Open a video → **자막 파일 열기** → choose its Korean SRT (UTF-8 or CP949/EUC-KR, ≤2 MiB).
The app validates ordered timestamps against the video duration, stores a new version,
and serves escaped plain-text WebVTT to the native player. Previous versions remain
selectable. Common SRT styling is removed for display; literal angle-bracket text and the
original uploaded SRT bytes are preserved. Decoding is strict UTF-8 first, then CP949
(including EUC-KR), with no replacement characters. SMI/SAMI, ASS/SSA, embedded subtitle extraction and automatic
language verification are not implemented. Choose **자막 끄기** to hide captions.
Source SRT files and source videos are never written. Imported text is treated as
Korean because the user selected it for the Korean track; the app does not certify it.

Open **자막에서 장면 찾기** and enter a word or phrase in the selected subtitle.
Results show matching text and timestamps; choose one to seek and play. The existing
completed-seek handler saves the watch position. Search is a literal, Unicode-normalized
substring match, not visual/semantic scene analysis. It uses only this player's loaded
track in browser memory; no query API, saved search history, or global indexing.
Empty queries show no transcript; at most 50 matches are displayed. Native captions
Off and app track/item changes invalidate old results. Closing clears the query.

## Optional local models — CPU verification, Windows runtime gate

These adapters are a reversible baseline, not a model-selection verdict:
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) with
[large-v3](https://huggingface.co/Systran/faster-whisper-large-v3), followed by
[MADLAD-400-3B-MT](https://huggingface.co/docs/transformers/en/model_doc/madlad-400).
ASR source text/timing and Korean translations are stored separately. MADLAD uses
its `<2ko>` target prefix. Adjacent fragments join through sentence punctuation, capped
at 12 seconds, 400 characters and a 0.8-second gap; existing longer cues remain intact.
One translated sentence retains the combined original interval. This does not invent
word alignment or claim exact within-sentence timing. The untouched ASR cues remain stored.
Pure Hangul text passes through per unit; mixed-language units still translate.
MADLAD runs batches of two with beam four, CUDA bfloat16 or CPU float32. Unsupported
CUDA bfloat16 is diagnosed rather than silently using float16. GPU models run
sequentially; CUDA bfloat16 execution and 12 GB feasibility are still unmeasured.

The app does **not** download models, call hosted inference, accept license prompts,
load remote Python code or fetch missing tokenizer files. Prepare public model files
separately after checking their model cards and applicable terms; any explicit license
acceptance remains an owner action. Media and transcripts are never sent in setup.

**Windows inference is currently blocked before model import or job creation.**
The official ONNX Runtime wheel can emit an initialization trace before its Python
disable API is callable. `ORT_DISABLE_TELEMETRY=1` protects non-Windows initialization;
it does not establish the same guarantee for Windows ETW. A verified telemetry-free
Windows build is required before removing this gate. There is no override switch.
Original viewing and supplied subtitles remain available. This is an unfinished
October requirement, not removal of Windows ASR from scope.
[ONNX Runtime privacy controls](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md).

Linux CPU setup used Python 3.12.13 and the official CPU PyTorch wheel. Prepare at
least 15 GB for these weights plus runtime/cache and media working space. Public model
revisions used for the check are fixed below; this does not certify future revisions.
Set `MEDIA_CLARITY_DATA` to the same external directory passed to the app's `--data-dir`.

```sh
.venv/bin/python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements-models.txt
.venv/bin/hf download Systran/faster-whisper-large-v3 --revision edaa852ec7e145841d8ffdb056a99866b5f0a478 --local-dir "$MEDIA_CLARITY_DATA/models/asr" --include "*.json" "model.bin"
.venv/bin/hf download google/madlad400-3b-mt --revision fa184c675da0b5c9e1c8694fccd4e12e2d422094 --local-dir "$MEDIA_CLARITY_DATA/models/translation" --include "*.json" "*.safetensors" "*.model"
```

Models stay outside Git. CPU is the non-Windows default; `models/settings.json` accepts
`{"device":"cpu"}` or `{"device":"cuda"}` with no silent device fallback. A device
setting does not override the Windows privacy gate. The worker forces Hugging Face
offline/telemetry settings and ORT's pre-initialization flag, then calls ORT's disable
API before ASR. These are dependency controls, not an OS network sandbox. Linux package
resolution and real ASR ran successfully; target Windows/CUDA/12 GB fit remains open.
The [resolved Linux CPU environment](model-runtime-linux-cpu.txt) records that run;
it is not a Windows/CUDA lockfile. `pip check` reported no broken requirements.

The initial real-ASR probe was blocked by automatic approval review because ORT
attempted incidental Microsoft telemetry. The corrected adapter completed an
[11-second public speech sample](https://github.com/ggml-org/whisper.cpp/blob/master/samples/jfk.wav)
in 23.16 s on an AMD EPYC CPU environment (9 vCPUs, about 21 GiB RAM, no GPU).
Repeating that audio three times in a synthetic MP4 produced three ASR cues in
79.79 s. Repetition is only a recovery fixture, not varied speech/quality evidence.
Native network tracing was unavailable (`ptrace: Operation not permitted`).

At implementation `f2a3ba3`, the production CLI/HTTP pipeline completed that 33 s
fixture with three Korean cues in **133.10 s including pause and server restarts**.
After two saved translations (104.19 s), pause stopped the worker. Forced server restart
preserved the transcript hash, the exact saved batch bytes and a 5.25 s watch position.
Attempt two translated only the remaining unit. The regenerated VTT and the previous
ready version survived another forced restart byte-for-byte; Range bytes matched,
source hash stayed unchanged and server logs were zero bytes. Source and Korean text
were inspected; these long sentences still need browser readability/human evaluation.
This is real CPU model evidence, not actual browser or Windows/RTX evidence. The older
183.93 s run used one-cue processing; these small runs are not a speedup benchmark or
a two-hour movie runtime estimate.

Real MADLAD CPU float32 also translated two author-written fragment pairs. Japanese
`駅に着いたら、` + `私に電話してください。` translated together as
“역에 도착하면 전화해주세요”; separate fragments lost that conditional connection.
The English joined sentence retained the complete meaning but remained literal in
style. This checks actual text output, not Japanese ASR or general translation quality.
Model identity took 71.52 ms with the installed full weights; it no longer reads weight
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

- An OS worker lock survives server death and native inference stalls. A new server
  waits for the old worker to exit before recovery or another inference; original
  watching stays available. Attempts also condition checkpoint/publication writes
  on their claimed generation. Processing continues when the player closes.
- **일시정지** stops the child; **처리 재개** retries with durable completed results.
- An interrupted running job becomes paused on server startup. A completed transcript
  is reused; translation resumes after the last committed batch. New completed units
  append atomically every 20 units or after a batch completes at least five seconds
  after the last save. No growing prefix is rewritten. A hard stop repeats at most
  20 units; the five-second threshold does not interrupt an in-flight generation.
  Completed pending outputs also save on a caught runtime error. Interruption during
  ASR reruns that ASR stage; partial ASR and within-cue translation are not checkpoints.
- Original byte identity, model paths/file metadata (device, inode, size, modification/
  change time), execution device, adapter settings and dependency versions bind reusable
  results. This is a change fingerprint, not a fresh model byte-integrity certificate.
  Changed model/config refuses reuse; restore the old
  setup to resume, or choose **처음부터 다시 만들기** for a new job with current
  settings. This preserves previous jobs, checkpoints and caption versions.
  The new sentence/bfloat16 pipeline invalidates unfinished jobs from the old adapter;
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
- Actual mixed-language recognition, omission/hallucination/translation/timing quality,
  long-video runtime, Windows/CUDA installation, GPU memory and browser decoding/caption
  display need real samples and target tests. Synthetic results do not establish these.

The next required evidence is real browser caption playback/seek/resume and a verified
telemetry-free Windows runtime, then target RTX, Japanese/mixed speech and long videos.
