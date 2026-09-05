# Current work

## Authorized milestone and branch

The owner explicitly said **“구현 시작”** on 2026-09-05 for local video import → library
→ playback → persisted resume. This is the current app slice; models, subtitles and
enhancement are not implemented by it. Donor `seoji2005/media-clarity-studio` stays read-only.
One implementation agent owns app code; the coordinator verifies and publishes.

Branch: `app/import-play-resume`, starting parent
`dafa25998454cbe02ff524f9bf11f58f7a49cf95`. Keep harness PR #1 frozen, Open/Draft and
unmerged; publish the app as a separate Draft PR stacked on `harness/initial-workflow`.
Use `git rev-parse HEAD` and live PR coordinates on resume; this starting parent is not
the implementation's final SHA. Final merge/release remains an owner decision.

## Observable implementation

Python 3.12/FastAPI/SQLite local app with a responsive Korean library/player UI.
Browser picker/drop streams to app-owned staging, verifies persisted bytes and codecs,
atomically publishes into an exclusive file directory and commits one MediaItem with
a separate file identity. Originals are read-only, with no hard links. CLI source import
also verifies source identity/metadata and rereads its hash. Real thumbnails, bounded
HTTP single ranges, duplicate identity and transactional watch history are implemented.
Unsupported/missing media and failed saves have explicit states.

Default launch: `python -m media_clarity`, **http://127.0.0.1:8765**. Setup, codec limits,
data locations and recovery are in [README](../README.md). No external assets, telemetry,
media egress, models or donor mutations. A local data-dir process lock protects recovery;
it does not solve cloud Work serialization.

## Verification and limits

Evidence class: **synthetic fixture**, with real Linux processes/HTTP/SQLite/filesystems.
Python 3.12.13; FFmpeg/ffprobe 6.1.1; exact dependencies in requirements files.

- `python -m unittest discover -s tests -v`: **37 passed** (18 app/failure-boundary tests,
  19 receiver-policy tests). H.264/AAC fixture; source/copy hashes; duplicate/history
  retention; exact ranges; source-change/partial-copy/space/collision/commit rollback;
  missing/changed files; bool/NaN/infinity/out-of-range positions; Host/Origin/token/
  traversal/symlink rejection; decoder output/timeout bounds; cleanup failure ownership
  release. A child dies at the actual save method's commit boundary; the prior committed
  position survives. TestClient emits a non-failing httpx deprecation warning.
- Coordinator's actual HTTP/process probe: **25-second H.264/AAC, 2,563,495-byte** fixture.
  Source/copy SHA matches; exactly one item; full/start/offset/suffix bytes and HEAD match;
  malformed ranges/positions and hostile requests fail closed. Saved **8.25 seconds**
  survives forced termination and actual restart. Killing a live partial upload preserves
  the item and quarantines the partial on restart. Old token rejected/new token usable.
  Captured process logs omit fixture name/path/hash.
- Actual UI JavaScript in jsdom: safe title text, search/continue filters, metadata resume,
  close/reopen periodic autosave, ordered seek/pause writes, missing-file feedback pass.
  Removing the close-time timer reset reproduces the regression. This is **mocked DOM/
  media/HTTP**, not browser playback. Optional reproducible test: `tests/ui/player.cjs`.
- Actual browser access was blocked by the provided environment (`ERR_BLOCKED_BY_CLIENT`);
  no advertised local forwarding capability exists. No browser playback/seek/visual-quality
  PASS is claimed. **Windows install/locking/codecs, target RTX and human quality are
  unverified.** Browser source metadata is unavailable. Resume covers last acknowledged
  save; abrupt exit may lose unacknowledged seconds. Missing-file repair is manual backup
  restoration.

## Review and automation checkpoint

Separate Work reported fixed harness HEAD `dafa259…` code **PASS / R2 resolved**, tree
`b99e6a3abadb649e89d40a2ce18e4d4f5c5f1107`. Actual synchronize → independent review is
confirmed, but result publication was blocked: no run ID/history or cross-run serialization
could exclude duplicate comments. Event review → tool comment → coordinator resume remains
unverified. Manual relay is the disclosed minimum fallback.

Both PR #1 receivers were paused for this transition. Automatic writing remains disabled;
the daily check stays read-only. Same-Work checks cannot replace formal separate-Work review.
Retarget only the exact new PR and verified binding under [the protocol](engineering.md#event-handoff).

## One next action

If not yet published, complete relevant QA and publish a useful commit as a new stacked
Draft PR with explicit WIP/ready coordinates and concise review handoff. Otherwise read
the live Draft PR/body to recover its number and final SHA. Request separate-Work evaluation
of original safety, persistence, HTTP/privacy and stated browser/Windows limits.
Continue repairs within this slice without repeated permission. Do not start models or
claim this import checkpoint completes October P0.
