# Current work

- **Milestone:** Korean-subtitle viewing and resumable preparation — **in progress**.
  Original import/library/playback/resume is preserved. No October feature is dropped.
- **Branch:** `app/korean-subtitles-resume`, Draft PR #4, based on `harness/lean-work`
  at `d3c7607f65759e24b0ae5147d07b5e05c6f12dd6`. Latest app is on this progress branch,
  not main. PR #2 is merged into `harness/initial-workflow`; PRs #3 and #1 remain
  unmerged. Fetch live Git/PR coordinates on resume; final merge needs owner approval.
- **Implemented:** preserved SRT upload bytes and caption versions, escaped WebVTT,
  local ASR/translation adapters, transactional stage/cue checkpoints and pause/resume.
  Kernel worker/attempt guards prevent orphan overlap and stale writes. Selected-caption
  text search now seeks to matching timestamps; queries stay in browser memory. Native
  Off, delayed loads, version/item switches invalidate old results; closing clears queries.
- **Privacy correction:** actual ASR first triggered an incidental Microsoft telemetry
  connection, rejected by automatic approval review. Linux now forces ONNX Runtime's
  pre-initialization disable flag and disables trace events before ASR. Pin: ORT 1.29.0.
  Official Windows wheels have a pre-API ETW initialization gap, so Windows inference
  fails closed before imports/queueing until a telemetry-free runtime is verified.
  Supplied-caption/original viewing remains available. No owner approval for telemetry
  or private-data egress was requested or inferred from public-download authorization.
- **Verification:** Python 3.12.13/Linux app suite **38 tests passed**; all three
  `tests/ui/{player,subtitles,subtitle-search}.cjs` checks passed (mocked DOM/media/HTTP).
  Harness/diff checks passed. Prior real HTTP synthetic proof remains valid: two caption
  versions survive forced restart byte-identically, 5.25 s watch position restores,
  Range bytes are exact, source hash unchanged, and fixture payload absent from logs.
  Actual large-v3 CPU ASR: public 11 s speech in **23.16 s**, repeated 33 s fixture in
  **79.79 s**, producing three cues. These are real CPU/cloud model measurements,
  not RTX or broad language/quality results. Real CLI/HTTP pipeline completed three
  Korean cues in **183.93 s including pause and server restarts**: paused after cue one,
  preserved transcript/translation hashes and 5.25 s watch position across forced restart,
  resumed as attempt two without redoing saved cues. One ready VTT survived another
  forced restart byte-identically; source hash and Range bytes stayed exact, server log
  size was zero. Model text was inspected; browser readability/human quality is not signed off.
- **Independent review:** scene search passed at local `7f64767` after resolving native
  Off/loading/re-enable findings; privacy remediation passed at `f7e08d2` after the
  Windows gate. No unresolved BLOCKER/IMPORTANT in those scopes. Baseline persistence
  fixes retain their earlier independent review. Reviews are code/synthetic evidence.
- **Remaining gates:** browser captions/
  seeking/visual quality (`ERR_BLOCKED_BY_CLIENT` persists), Japanese/mixed language,
  long videos, Windows setup and target CUDA/12 GB RTX, human quality. Network tracing
  via strace was denied by the environment; dependency flags are not an OS sandbox.
  ASR interruption reruns ASR; translation resumes after saved cues. Crash input copies
  remain in app-owned `processing/`; ordinary exits clean only their disposable copy.
- **Next action:** obtain a telemetry-free Windows runtime and perform actual
  browser/RTX caption/seek/resume checks, then Japanese/mixed speech and long videos.
  The CPU processing checkpoint is complete; the viewing milestone remains open.
  Setup and exact limits: [subtitles](subtitles.md).
- **Operations:** old development/reviewer event tasks remain paused; the existing daily
  read-only progress check is enabled. One Work owns implementation. Public packages/
  model downloads are authorized; no private cloud inference or external payloads.
