# Current work

- **Milestone:** simplify the harness; preserve the existing local import/play/resume app.
- **Branch:** `harness/lean-work`, based on
  `90b6d9c488e927d5f08e70d22ce8a323410d49f7`.
  [PR #2](https://github.com/seoji2005/media-server/pull/2) merged into
  `harness/initial-workflow`; [PR #1](https://github.com/seoji2005/media-server/pull/1)
  targets main. Fetch live coordinates on resume; main is not the latest app checkout.
- **Last verified product revision:** `90b6d9c488e927d5f08e70d22ce8a323410d49f7`;
  its 24 file blobs/tree were matched before cleanup. Application, dependencies and
  application regression files remain byte-identical in this change.
- **Verified behavior:** prior PR #2 records report import, original/copy integrity,
  library, HTTP ranges and 8.25-second resume after forced process restart; same-size
  mutations rejected cold/warm and cache reuse probed on a 128 MiB fixture.
  Evidence: **synthetic fixture**, not real-model quality. Those earlier process
  probes were not repeated for documentation cleanup. This cleanup ran
  `python scripts/harness.py run test`: **25 app tests passed** with pinned dependencies
  on Python 3.12.13/Linux. Harness/link and diff checks passed (**contract only**);
  a synthetic failing test retained its failure detail, skip count and exit 1 under
  quiet mode. Doctor found FFmpeg/ffprobe. No model or browser run was performed.
- **Open limits:** actual browser playback/seek/visual quality, Windows installation/
  locking/codecs, target RTX and human quality remain unverified. ASR/translation/
  enhancement/search/recommendations are not implemented. No token/cost saving measured.
  This branch does not modify external schedules or stop other Work executions.
- **Next action:** use the [short start prompt](start.md) in the sole implementation
  Work to recover the live app and advance the first real Korean-subtitle viewing
  slice; address related playback gaps with available tools. Existing development
  event tasks must be paused before that Work takes ownership; retain the read-only
  daily check. Final merge/release stays with the owner.
