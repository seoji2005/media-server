# Current work

Milestone: `fix/bounded-subtitle-status`, based on live Server main
`42c435842b70918d1f29924f74f023c7736576ca` (PR38 merged). Restored local base
`9ad3e25ca50cce5b48189d4e14ed798e7b81daaf` has the identical complete tree
`d958a3ecdf5106bfcb77503467c6118c5096ebc3`; publish using actual remote ancestry.
Fetch main stays `0d6aa28a4a0c6944c053e3d63e150908b44b9175`. No open PR in either
repository at start. Owner implementation, bounded verification, independent review
and passing development merge approvals continue; release is separate.

## Delivered and current change

Gemini3.8, foreign SRT/VTT import/retranslation, shared Qwen/scene installation pins,
exact Fetch-to-Server item entry, bounded preview/scene preparation and local display
labels/Unicode library search are merged. PR38 passed independent functional review,
Ubuntu/Windows CI34591293873 and actual desktop/mobile screenshot inspection.

Subtitle status and job commands had no browser response deadline. A delayed generation
button remained clickable; the new regression against base9ad3e25 sent2POSTs instead
of1. The corrected client serializes commands per item, with30s response/body limits
for commands, status reads and caption-setting writes. Status reads wait for already
pending caption/command requests, each independently bounded. No automatic command
retry, inference start, resume, server schema or worker/checkpoint change.

Ambiguous command responses stay blocked until an explicit successful status reread;
known missing-key/precondition rejection can be corrected directly. Pending/uncertain
state survives same-page item/audio switching. A reread is a server snapshot, not an
exactly-once command receipt; a delayed server request may still finish, and explicit
new actions retain the existing billing disclosure/server guards. Page reload is not
a durable operation journal.

Automatic monitoring stops on a failed read,5minutes without a higher saved count/time,
or10minutes/400reads per monitoring session. Limits are checked at completed status
reads; individual response waits remain bounded. Progress/stage changes cannot extend
the total budget. Explicit reread, a new command or player reopen starts a new session.
Manual pause remains available after monitoring stops. The server worker may continue;
no client timeout is presented as cancellation. Existing video/caption/Off/offset stay
usable through read failures. Initial-load and stalled caption-save recovery are covered.

## Verification and next action

- Linux CPU: all11DOM scripts pass. New status tests exercise delayed headers/body,
  duplicate commands, timeout/late acknowledgements, read-only confirmation/failure,
  first-read recovery, progress regression, elapsed/request caps, manual pause,
  caption-save timeout, pending reopen and audio/item isolation. HTTP/media mocked.
- The old-code duplicate-click regression exits1 (2POSTs); corrected tests exit0.
  Syntax, diff and documentation-link checks pass. No Python product code changed;
  avoid optional broad local repeats. Existing model-free CI supplies the full gate.
- Browser additions inject one503 status read while a real synthetic caption/video is
  loaded, then use the real server through the visible recovery button. They assert
  unchanged media/position/caption and zero job commands, and capture desktop/mobile
  failure screens. This is fault injection, not a natural network/model failure test.
- Freeze the source, obtain fresh independent recovery/privacy review, then inspect
  exact-HEAD Ubuntu24.04/Windows Server2025 CI and screenshots before development merge.
  CI jobs cap at10minutes; do not rerun unchanged failures without new evidence.

For GitHub PNGs, export the artifact as a file reference and use the official file
materialization service, then verify ZIP digest and inspect images. This worked without
credential/proxy/policy changes after prior direct download URLs returned403 twice.
Do not repeat those raw-URL requests or bypass browser/extension access restrictions.

## Blocked acceptance

Fresh natural long-speech Qwen→aligner→Gemini3.8 remains stopped. The preserved
`test/bounded-long-speech@f038f85` handoff records no Qwen weights and socksio install
network approval cancellation twice. No repeat installation/new model download here.
Two held public dialogue recordings706.24s/762.048s passed hash/time checks earlier;
some references informed translation comparisons, so they are not pristine holdouts.
No new ASR/alignment/Gemini calls. General approval alone does not prove limits changed.

Only once an allowed environment has the dependencies and pinned assets, run the fresh
speech product path with finite elapsed/no-progress/retry bounds and saved span/batch
reuse. Natural long-caption viewing, actual Chrome Fetch discovery/save/item playback,
Windows11/RTX4070SUPER installation/VRAM/playback and useful enhancement/subjective
search/recommendation quality remain open. No enhancement preset has been adopted.
Prior synthetic45-minute preview/restart checks are not natural long-speech evidence.

Terminate owned processes on bounds/repeated same-cause failures, preserve originals
and complete diagnostics, then stop that blocked task. Existing browser/CDP/profile/
proxy and model-inference CI workaround prohibitions remain.
