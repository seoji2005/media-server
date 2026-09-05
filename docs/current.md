# Current work

## Authorized milestone and branch

The owner explicitly said **“구현 시작”** on 2026-09-05 for local video import → library
→ playback → persisted resume. This is the current app slice; models, subtitles and
enhancement are not implemented by it. Donor `seoji2005/media-clarity-studio` stays read-only.
One implementation agent owns app code; the coordinator verifies and publishes.

Branch: `app/import-play-resume`, starting parent
`dafa25998454cbe02ff524f9bf11f58f7a49cf95`. App [Draft PR #2](https://github.com/seoji2005/media-server/pull/2)
is stacked on `harness/initial-workflow`; harness PR #1 stays frozen/unmerged. This repair
starts from independently reviewed HEAD `2cba21bb3817a3fe8637e8426d2d16da12ecf846`.
Use `git rev-parse HEAD` and live PR coordinates on resume; those historical coordinates
are not a claim about the latest head. Final merge/release remains an owner decision.

## Observable implementation

Python 3.12/FastAPI/SQLite local app with a responsive Korean library/player UI.
Browser picker/drop streams to app-owned staging, verifies persisted bytes and codecs,
atomically publishes into an exclusive file directory and commits one MediaItem with
a separate file identity. Originals are read-only, with no hard links. CLI source import
also verifies source identity/metadata and rereads its hash. Real thumbnails, bounded
HTTP single ranges, duplicate identity and transactional watch history are implemented.
Unsupported/missing media and failed saves have explicit states.

Current repair: same-size managed-file mutations now fail before playback with
`managed_file_changed`. A full SHA pass seeds a bounded metadata/block-digest cache;
subsequent ranges validate only their aligned blocks plus identity/change metadata.
The response keeps the verified descriptor and never emits a block with a mismatched
digest. Detected changes appear unavailable in the library and duplicate import fails.
Library listing is lazy; first use, changed identity/metadata, restart and eviction rehash.

Default launch: `python -m media_clarity`, **http://127.0.0.1:8765**. Setup, codec limits,
data locations and recovery are in [README](../README.md). No external assets, telemetry,
media egress, models or donor mutations. A local data-dir process lock protects recovery;
it does not solve cloud Work serialization.

## Verification and limits

Evidence class: **synthetic fixture**, with real Linux processes/HTTP/SQLite/filesystems.
Python 3.12.13; FFmpeg/ffprobe 6.1.1; exact dependencies in requirements files.

- Repair: `python -m unittest discover -s tests -v`: **43 passed** (24 app/decoder cases,
  including six integrity regressions, and 19 receiver-policy cases). The new same-size cold/warm test run
  against untouched `2cba21b…` produces **two assertion failures, zero errors** (200 vs 409).
  New checks cover mtime restoration; full/Range/HEAD failure; duplicate/library state;
  cache reuse, replacement, eviction and restart; changes during hashing; and first/later
  block rejection even when metadata is mocked unchanged. Native Windows execution
  remains unverified. Harness check, compile and diff checks pass.
  Subsequent focused checks also pass for exact cross-block HTTP 206 bytes and descriptor
  closure when response-header cancellation happens before the body generator starts
  (the latter adds one test, making 44 test methods total).
- Coordinator repair probe: actual HTTP/process on a **128 MiB synthetic MP4**. First
  Range invokes one full scan; eight subsequent ranges invoke none (QA wrapper counts
  `_scan_content` calls, not measured disk I/O). Same-size/mtime-restored mutations give
  GET/Range/HEAD 409 with no ETag and an unavailable item, including after process restart.
  A mutation at 100 MiB during streaming terminates after 1 MiB with an incomplete-response
  error; the changed byte is never received. Source SHA is preserved and captured logs
  omit fixture path/title/hash. Browser behavior remains untested.
- Prior app evidence remains relevant: H.264/AAC fixture; source/copy hashes; duplicate/history
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
  close/reopen periodic autosave, ordered seek/pause writes, missing/changed-file feedback
  and media-error refresh of the library pass.
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

Separate Work reported PR #2 HEAD `2cba21b…` **CHANGES_REQUESTED**: size-only playback
validation served a same-size mutation with the old SHA ETag. This is the repair target;
the same-Work tests above do not replace its independent rereview. Its result was relayed
by the owner; GitHub result publication was `BLOCKED_ENV/CONTROL`, not an event round trip.

The latest owner policy enables only the reviewer's **PR #2 merge-event read-only review
and report in its Work**. The coordinator receiver is paused; automatic comments, repairs
and follow-on implementation are off. The daily check stays read-only. Reservation state
is external; this code change does not retarget or reactivate it.

## One next action

If this repair is not yet published, push it to existing Draft PR #2. Otherwise recover
the live ready base/head and request separate-Work limited rereview of same-size mutation
rejection, cache reuse/
invalidation and response-byte integrity. Preserve the disclosed browser/Windows limits
and merge-only review automation policy. Continue repairs within this slice without
repeated permission. Do not start models or claim this checkpoint completes October P0.
