# Korean subtitle preparation

This is an incremental implementation, **not a real-model quality sign-off**.
Original watching does not depend on subtitle jobs. Video download, generation and
NAS remain excluded. Public model-weight setup below is separate from video downloading.

## Watching with existing subtitles

Open a video → **자막 파일 열기** → choose its Korean SRT (UTF-8, ≤2 MiB).
The app validates ordered timestamps against the video duration, stores a new version,
and serves escaped plain-text WebVTT to the native player. Previous versions remain
selectable. Common SRT styling is removed for display; literal angle-bracket text and the
original uploaded SRT bytes are preserved. ASS/SSA, embedded subtitle extraction and automatic
language verification are not implemented. Choose **자막 끄기** to hide captions.
Source SRT files and source videos are never written. Imported text is treated as
Korean because the user selected it for the Korean track; the app does not certify it.

## Optional local models — unverified setup candidate

These adapters are a reversible baseline, not a model-selection verdict:
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) with
[large-v3](https://huggingface.co/Systran/faster-whisper-large-v3), followed by
[MADLAD-400-3B-MT](https://huggingface.co/docs/transformers/en/model_doc/madlad-400).
ASR source text/timing and Korean translations are stored separately. MADLAD uses
its `<2ko>` target prefix. GPU models run sequentially; 12 GB feasibility is unmeasured.

The app does **not** download models, call hosted inference, accept license prompts,
load remote Python code or fetch missing tokenizer files. Prepare public model files
separately after checking their model cards and applicable terms; any explicit license
acceptance remains an owner action. Media and transcripts are never sent in setup.

With the existing Python 3.12 environment, choose the appropriate official
[PyTorch wheel](https://pytorch.org/get-started/previous-versions/) first. Example
Windows candidate (CUDA 12.6); CUDA/cuDNN requirements for CTranslate2 must also be
satisfied using the [faster-whisper installation notes](https://github.com/SYSTRAN/faster-whisper#requirements):

```powershell
.\.venv\Scripts\python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python -m pip install -r requirements-models.txt
.\.venv\Scripts\hf download Systran/faster-whisper-large-v3 --local-dir "$env:LOCALAPPDATA\MediaClarity\models\asr" --include "*.json" "model.bin"
.\.venv\Scripts\hf download google/madlad400-3b-mt --local-dir "$env:LOCALAPPDATA\MediaClarity\models\translation" --include "*.json" "*.safetensors" "*.model"
```

Use `<your --data-dir>/models` if you changed the app data directory. Models are
outside Git. For CPU, use the official CPU torch index and put `{"device":"cpu"}` in
`models/settings.json`. Default device is CUDA on Windows, CPU elsewhere; there is
no silent GPU→CPU fallback. Dependencies above are candidate direct pins, not an
executed/resolved lockfile. CPU transcription/translation can be slow. Runtime and
weights could not be acquired in the current network-restricted environment.

Once prepared, open a video → **한국어 자막 만들기**. Existing supplied/ready subtitles
prevent redundant generation. Missing weights/runtime show a local setup diagnostic.
Progress shows the processing stage and saved translation cue count.

## Recovery and limits

- An OS worker lock survives server death and native inference stalls. A new server
  waits for the old worker to exit before recovery or another inference; original
  watching stays available. Attempts also condition checkpoint/publication writes
  on their claimed generation. Processing continues when the player closes.
- **일시정지** stops the child; **처리 재개** retries with durable completed results.
- An interrupted running job becomes paused on server startup. A completed transcript
  is reused; translation resumes after the last committed cue. Interruption during
  ASR reruns that ASR stage; partial ASR and within-cue translation are not checkpoints.
- Original byte identity, model file contents, device, adapter settings and dependency
  versions bind reusable results. Changed model/config refuses reuse; restore the old
  setup to resume, or choose **처음부터 다시 만들기** for a new job with current
  settings. This preserves previous jobs, checkpoints and caption versions.
  Original/caption tampering fails closed.
- Source/caption versions remain available after failure. A job publishes its full
  Korean track only after successful validation; it never overwrites an imported SRT.
- Attempt input copies live in app-owned `processing/`. Normal exits remove only
  their own disposable input copy; crash leftovers are retained. Translation-only resume needs no extra media copy. Back up the
  complete data directory with the server stopped.
- No silent input truncation. An overlong cue or unfinished translation fails with a
  diagnostic. Empty ASR is reported as no speech, not a fabricated ready subtitle.
- Actual mixed-language recognition, omission/hallucination/translation/timing quality,
  long-video runtime, Windows/CUDA installation, GPU memory and browser decoding/caption
  display need real samples and target tests. Synthetic results do not establish these.

The next required evidence is a permitted, non-private speech sample through actual
local ASR → Korean translation → browser caption playback, then target Windows/RTX.
