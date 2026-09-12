# Current work

Server main is `3fa3335ce14d1e2196228512952dc7587b76f05f` (PR43 merged).
Fetch main remains `0d6aa28a4a0c6944c053e3d63e150908b44b9175`; both had
no open PRs at the September 12 recovery check. Existing cost/allowed-egress and
independent-review plus passing-CI development-merge approvals persist. Release,
subjective quality and target-device acceptance remain separate.

## Current correction

PR43 contains subtitle compute/FFmpeg lifecycle cleanup, bounded stop and failed
job pause/resume fixes. Its fixed HEAD `a0af75e` passed independent review and
PR CI34660045994 on Ubuntu and Windows; the merged tree was identical.
The subsequent automatic main CI34660439190 failed: both OSes passed Python
(293 tests; Ubuntu 3 skips, Windows 2), but Ubuntu's preparation DOM fixture
observed a stale empty label and Windows's first browser phase hit its existing
75-second cap without an identifying stage. Do not erase that failure or relabel
it as a successful main check.

This slice only changes tests: wait for the actual details toggle instead of
manually duplicating its queued native event; bound that wait to five seconds.
Add fixed-label browser phase markers so a hard timeout identifies its last
stage without paths, dialogue, URLs or credentials. No production behavior,
assertion, browser deadline or automatic retry changes. The Windows root cause
is still unconfirmed; better diagnostics are not a playback fix.

Local syntax checks do not run jsdom or the real browser. Require independent
fixed-HEAD review and final Ubuntu/Windows product CI before development merge.
Observe CI for at most ten minutes/ten polls and do not rerun unchanged failures.
If a failure repeats, preserve its stage and stop instead of raising the cap.

## Actual product trial and recovery

The prior unchanged-main dialogue03 trial last confirmed 18 committed speech
spans through 501.39 of 762.048 seconds, at 889.45 seconds elapsed. Translation
had not started. After execution-service disconnection, completion and shutdown
were unconfirmed. Automatic workspace maintenance then removed the old checkout,
venvs, model working copies and trial DB/output directories. The recovered local
service responds and its current process list contains no old model/FFmpeg/pip
worker; that does not reconstruct what happened before the old environment ended.
No saved trial DB/checkpoint was found. Do not claim those 18 spans are reusable.

The saved original audio/annotation archive was recovered. dialogue03 WAV and
EAF SHA256 values match the prior record; duration is 762.048 seconds. Saved
pinned model archives remain available. Do not redownload several GB until the
runtime can use them. No original or completed saved artifact was deleted by
this task.

The fresh runtime lacks Torch, Transformers, FastAPI/Uvicorn and the speech
language packages. One bounded Torch package-index request (10-second I/O,
zero retries) returned `network approval was cancelled before a decision was
returned`; no retry, proxy change or alternate execution route followed. No
saved runtime/wheel bundle was found. Neither GEMINI_API_KEY nor GOOGLE_API_KEY
is configured in the new environment; never recover credentials from chat logs.
New ASR/alignment/Gemini calls: zero. Restoring package-download access and an
approved key configuration is required before the actual product trial.

## Next acceptance work

First recover the correct runtime and any genuine saved DB, then run the full
Qwen → ForcedAligner → Gemini 3.8 product job, preserving originals and publishing
small durable checkpoints during processing. If no DB exists, record a new run
rather than fabricating resume. Speech bounds: 45 minutes total / five minutes
without a committed span. Translation: ten minutes / two minutes without a saved
batch. Automatic retries: zero. Stop the owned process group at a bound.

Dialogue03 is new to a complete Qwen product run, but reference text was used in
translation comparisons; it is not a pristine holdout. Twelve minutes does not
establish the target 40–120-minute quality or Windows 11/RTX 4070 SUPER behavior.
Inspect omission, timing, Korean consistency/readability and actual playback.
Then finish real Fetch extension download → exact-video playback, useful video
enhancement, search/recommendation quality and target-device checks. Previous
Fetch HTTP/Native/FFmpeg integration 2/2 and synthetic CI playback are separate
from those still-open acceptance gates.
