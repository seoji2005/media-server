# Runtime installation and saved model restoration

Use Python 3.12 (64-bit x86) and install trusted FFmpeg/ffprobe on PATH first.
This helper supports Windows and Linux. It creates this checkout's selected venv at its
final path; it never moves a venv or upgrades an existing one. Other original
environments, media, DBs and corrections are not installation targets.

## Start with viewing

Windows PowerShell:

```powershell
.\install-media-clarity.cmd --viewing-only
.\.venv-viewing\Scripts\python -m media_clarity doctor
.\start-media-clarity.cmd
```

This prepares `.venv-viewing` using only the exact pins in `requirements.txt`.
Import, playback, supplied SRT/VTT selection, timing adjustment, sentence search
and viewing-state storage use the actual app and normal library. Torch,
Transformers, model weights, GPU, API keys and inference are not prerequisites.
Model/device settings are neither inspected nor changed. Device selection and
cache-restore arguments cannot be combined with `--viewing-only`.

The limit is 600 seconds total / 120 seconds of installation-byte idle, with zero
connection/resume retries. The final isolated check has a 30-second bound and
verifies Python 3.12/64-bit, this venv, exact runtime package versions and imports
FastAPI/uvicorn. It does not call the model diagnostic. Existing `.venv-viewing`
is checked without pip or bytecode writes; a partial environment stays intact.
The initial free-space prerequisite is 1 GiB; this is not a media storage allowance.

On Linux use `python3.12 scripts/install_runtime.py --viewing-only`, then
`.venv-viewing/bin/python -m media_clarity --open-browser`.
The Windows start command prefers `.venv` when its Python exists, otherwise
`.venv-viewing`. It never retries a failed full-runtime launch in the viewing venv.
Both use the same default library; pass the same `--data-dir` on install and launch
for a custom library. Stop the app before preparing either environment.

## Add subtitle generation

Run without `--viewing-only` to prepare the separate `.venv`. It preserves
`.venv-viewing` and the same media, captions, viewing position and preferences:

```powershell
.\install-media-clarity.cmd
```

The existing `models/settings.json` selects the device. With no setting, Windows
uses CUDA and Linux uses CPU. `--device cpu` or `--device cuda` can explicitly save
a first selection; conflicting existing settings stop unchanged. CUDA preparation
uses the official Torch 2.8.0 CUDA 12.6 wheel; CPU uses 2.8.0+cpu. A compatible
driver/GPU and actual inference remain separate. No silent CPU fallback occurs.

For the owner's original saved ASR/aligner bundles, combine installation, the
[pinned offline cache restore](qwen-subtitles.md#offline-cache-restore), and the
final setup check:

```powershell
.\install-media-clarity.cmd --asr-bundle 'D:\QwenCache\asr' --aligner-bundle 'D:\QwenCache\aligner' --parts-dir 'D:\QwenCache\parts'
```

Each bundle contains the original manifest and metadata directory. Omit
`--parts-dir` if each bundle contains its own ZIPs. Use the same `--data-dir` for
installation, restore and everyday launch when using a custom library. On Linux
run `python3.12 scripts/install_runtime.py` with the same arguments.

After success, use `start-media-clarity-gemini.cmd` for hidden session-key input,
or `start-media-clarity.cmd` for ordinary viewing. The installer does not read keys
or call Gemini. It strips Gemini/Google/Hugging Face credentials from its children.
Existing platform proxy/TLS settings are retained; pip indexes/config/targets are
isolated. No alternate mirror, route, source build or automatic model download is
attempted on failure.

Full-runtime installation is limited to 1800 seconds total and 120 seconds without changes in
the byte counts of installation files. Quiet native checks have their own 75-second
outer bound and the existing 60-second diagnostic. Optional restore plus final
diagnostic has a separate 1320-second total / 90-second byte-progress idle limit.
All subprocess descendants are contained in owned POSIX groups or Windows Jobs.
Completed check rows survive limits; `--json` reports fixed errors without raw pip
output, paths or keys. API connection, actual inference and viewing are unverified.

Downloads use only official PyTorch/PyPI indexes and binary wheels. The repository
requirements are validated and snapshotted before installation. Torch is constrained
to the selected build; the remaining requirements keep their repository pins/ranges.
After download, installation uses `--no-index` and only that run's wheel directory.
The actual pip install child also blocks Python socket events before imports,
including any attempted direct-URL dependency resolution.
`pip check`, repository package checks and the weight-free native probe must pass.
Both connection and download-resume retries are zero. Bundled pip25.0.1 has no
resume loop; other pip versions must expose `--resume-retries` or stop before traffic.
No implicit pip upgrade is performed.

On failure, `.setup-cache/install-*` retains completed wheels and temporary assets;
the selected `.venv` or `.venv-viewing` retains its current files. There is no automatic repair/resume of a partial
environment. A later invocation validates an existing environment without calling
pip; invalid/mismatched environments stop. Preserve them and use a fresh checkout
for a new installation. Validation disables bytecode writes in both its isolated
interpreter and the separate native probe, including cache-free existing environments.
Full-runtime reuse requires the selected exact Torch build; viewing reuse checks
only the exact base runtime pins.
The app/worker locks prevent setting/package work during active app/model jobs.
Restore reacquires its own locks and stops if another app starts during handoff.

Windows CI uses small offline wheels and command dispatch fixtures. Linux CPU
runtime evidence is recorded in the PR. Neither establishes Windows 11/RTX 4070
SUPER installation, 12 GB inference fit, long-form or human viewing acceptance.

Option references: [pip CLI](https://pip.pypa.io/en/stable/cli/pip/) and
[official Torch 2.8 installation variants](https://pytorch.org/get-started/previous-versions/).
