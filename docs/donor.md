# Selective donor audit

Read-only source: `seoji2005/media-clarity-studio` at
`13461ba36353066f33c006f0ee9a557c3f1cadaf`. Fixed snapshot, not a claim about current main.
No donor application code is migrated in this harness. Decisions below guide later work.
Source paths are relative to that donor repository.

| Candidate and evidence | Decision | Cost judgment / retained failure knowledge |
| --- | --- | --- |
| `src/media_clarity/artifact_store.py`, `hash_file` (271–283) | Reuse small helper when needed | Bounded-memory stdlib SHA-256 is cheap to extract and validate. Keep file hash separate from MediaItem ID. |
| Same file, `add_file`, `_stream_to_temp`, `_promote` (369–550) | Adapt | Copy→fsync→verify→no-overwrite publication and descriptor checks are valuable. Extract the small algorithm; the entire 583-line store adds unnecessary job/schema coupling. Donor hard links only staging→CAS; never link user source. Validate actual Windows publication behavior. |
| Same file, managed names / `resolve_inside_root` (119–237); `tests/test_artifact_store.py` (314–324) | Adapt checks | UUID managed names avoid Windows reserved-name complexity. Retain containment/symlink escape checks; external import paths need a different policy from managed artifact paths. |
| `src/media_clarity/job_runtime.py` (608–627, 1086–1159, 1409–1438) | Replace; reuse ideas/tests only | The 2,289-line runtime costs more to integrate than a sequential SQLite job/attempt worker. Retain verified completed outputs, stale-running recovery and input/model/config cache invalidation when processing is built. Playback resume is independent. |
| `src/media_clarity/subtitle_contracts.py` (551–578, 825–851, 2230–2272) | Reuse ideas/tests only | Keep finite intervals, original timebase, immutable source and separate Korean translation with source links. Replacing the 4,147-line validator is cheaper than preserving advanced capability/coverage machinery. |
| `scripts/smoke_task_022.py` (31–80, 119–152); `src/media_clarity/synthetic_slice.py` (211–234) | Reuse test idea; replace production code | Generated fixture, original hashes and subtitle round trip are useful. Discard exact six-second FFV1/PCM restrictions and iCloud assumptions; these do not establish real-video compatibility. |
| `tests/test_artifact_store.py` (134–145, 202–219); `tests/test_job_runtime.py` (935–970, 1170–1188, 1287–1326); `tests/test_subtitle_contracts.py` (716–729) | Reuse tests/ideas only | Port collision, changing input, empty completed output, interrupted attempt, private diagnostic leakage and detached timebase cases against new interfaces. Validate duplicates before making dictionaries. |

Discard giant historical AGENTS/STATUS/TASK/REVIEW documents, PR reconciliation and
experiment-only invariants. Preserve failure knowledge, not old identifiers or gates.
An existing file or successful subprocess exit alone never proves a usable artifact.
An interrupted copy/job must not expose a partial result as complete or impair originals.

Audit evidence: 36 donor ArtifactStore and 8 synthetic-slice unit tests passed on Linux
CPU using temporary fixtures. **Synthetic fixture** only: this audit did not run real
models, browser playback, the actual FFmpeg smoke command, Windows or target RTX.
