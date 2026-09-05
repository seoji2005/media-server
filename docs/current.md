# Current work

- **Milestone:** Korean-subtitle viewing and resumable preparation — **in progress**.
  Source import/library/playback/resume is preserved. No October feature is dropped.
- **Branch:** `app/korean-subtitles-resume`, based on `harness/lean-work` at
  `d3c7607f65759e24b0ae5147d07b5e05c6f12dd6`. Latest app is on this progress branch,
  not main. PR #2 is merged into `harness/initial-workflow`; harness PR #3 and main
  integration PR #1 remain unmerged. Fetch live Git/PR coordinates on resume.
- **Implemented:** UTF-8 Korean SRT import, original uploaded bytes and caption
  version preservation, escaped WebVTT/native-player track selection; background
  local-only faster-whisper/MADLAD adapters; transactional ASR-stage/translation-cue
  checkpoints, pause/resume and non-destructive restart with changed settings.
  A kernel worker lock prevents overlapping inference after server death/native
  stalls. Claimed attempt checks prevent stale checkpoint/publication writes.
  Missing/changed provenance, media and subtitle corruption fail closed.
- **Verification:** Python 3.12.13/Linux with existing pinned app dependencies.
  At the repaired code checkpoint, `python -m unittest discover -s tests -q` passed
  **36 tests**; the final focused `-p test_subtitles.py` run passed **12 tests**,
  including one additional real FFmpeg audio-decode/ASR-interface test with a stub
  model. `node tests/ui/player.cjs` and `node tests/ui/subtitles.cjs` passed
  (**mocked DOM/media/HTTP**, not browser decoding). Harness and diff checks passed.
  Actual HTTP/process probe: two caption versions survive forced server restart
  byte-for-byte; **5.25 s** watch position restored, Range bytes exact, source hash
  unchanged and no fixture title/path/caption in logs. Evidence: **synthetic fixture**.
- **Independent review:** initial review found missing-config checkpoint reuse,
  old/new worker overlap during a native GIL stall, and lost literal angle text.
  All three resolved in limited rereview: 11 subtitle tests plus production CLI
  crash/restart with a synthetic backend. Native-stall survivor blocks replacement;
  after exit, resume reuses ASR/first translated cue and produces one track. Reviewer
  observed zero-byte server logs and no unresolved BLOCKER/IMPORTANT. This is code
  evidence, not model-quality or owner merge approval.
- **Actual blockers/limits:** inference packages/weights could not be acquired
  (network approval cancelled); real ASR/translation was **not executed**. Optional
  model pins/setup are unverified candidates. Browser connected but localhost app
  navigation returned `ERR_BLOCKED_BY_CLIENT`; no alternate route was attempted.
  Actual subtitles/seek/visual quality, mixed-language accuracy, long-video runtime,
  Windows/CUDA/12 GB RTX fit and human viewing quality remain unverified.
  ASR interruption reruns that stage; translation resumes by saved cue. Crash input
  copies remain in `processing/`; normal attempts remove their disposable copy.
- **Operations:** old development/reviewer event tasks were already paused; the
  read-only daily progress check remains enabled. This Work owns implementation.
  Commit/push/Draft PR are authorized; final merge/release needs owner approval.
- **Next action:** obtain permitted public model weights/runtime in an authorized
  environment and execute a non-private speech sample through real ASR → Korean
  translation → browser subtitles. Use [subtitle setup/recovery](subtitles.md).
  Then inspect Japanese/English/mixed accuracy and target Windows/RTX behavior.
