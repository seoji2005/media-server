# Open a saved companion scene

Media Server can open a companion scene on an explicitly included, directly playable
original using audio track 0. It opens paused at the requested time. Seeking or closing
before pressing play leaves the previous watch position and watched time unchanged.
After playback starts, ordinary position saving resumes. `end_ms` describes the saved
scene; it does not stop playback at that endpoint.

This integrates the proposal in [PR #15](https://github.com/seoji2005/media-server/pull/15)
on main `d9fb017`, with schema **v7** after v6's saved-transcript provenance. The donor
branch is preserved. It supplies the Media Server side only: Compass must still verify
its adapter against the landed revision. No device sync or remote access is added.

## Local interface

All routes retain the loopback Host/origin boundary. These two GET routes also require
the current `X-Media-Token` from `/api/session`, as all POST routes already do. A scene
link contains no token; tokens are neither persisted nor sent to another service.

| Route | Result |
| --- | --- |
| `GET /api/companion/identity` | Version 1, product `media-server`, logical `server_id` and `library_id` |
| `GET /api/library/{item_id}/moment-reference` | Version 2, both logical IDs, item ID, original file/hash/time basis and duration in integer milliseconds |
| `POST /api/library/{item_id}/moment-entry` | Revalidate the exact reference plus integer `start_ms` and nullable integer `end_ms`; return the validated times |

The reference's `timeline` contains `basis: original-file`, `unit: milliseconds`,
`zero: HTMLMediaElement.currentTime=0`, the immutable `file_id`, and `sha256`.
The POST requires exactly the returned reference fields plus both scene-time fields.
Start must be within the original duration; a provided end must be later than start
and no later than that duration. Foreign, stale, excluded, missing or unsupported
references fail without preparation or inference.

The local page accepts `#moment=` followed by the URI-encoded JSON POST body. It removes
that fragment from the address before API calls, obtains its own session token and
validates the scene. Existing fragments can also open a scene in an already loaded
page. No token or scene payload goes into an HTTP query string or referrer.

## Preservation and limits

Logical IDs are generated transactionally once, remain stable across restart and a
stopped database copy, and differ for separately created libraries. A current database
with a missing/corrupt identity fails startup instead of inventing a replacement.
Independently writable clones share those IDs and are unsupported; this is not a
physical-server or backup-recovery identity scheme.

Renditions, another audio track and unclassified legacy originals are refused. Ordinary
playback can still prepare those items separately. This contract does not map times
between original and prepared media or enable Compass Moments automatically.

At local code `d4efccc`, eight targeted SQLite/API tests passed, including rollback,
abrupt exit before migration commit, identity corruption/restore, original preservation,
token/origin checks and unchanged v6 retranslation rows. The full Linux suite ran 164
tests in 45.437 s with one Windows-only skip; all seven DOM suites passed. A separate
probe actually created data using unmodified `d9fb017`, including generated fixture
captions and a queued retranslation, then upgraded it using this code: every existing
row and original byte hash matched, foreign-key checks passed and identity survived a
second startup. Synthetic model results are plumbing evidence, not model quality.

The mandatory Chrome test now exercises initial and subsequent scene links, rejected
foreign references, paused seeking/closing with no position writes, and saving after
explicit playback. Local Chrome remains unavailable (socket EPERM); its result must be
read from the integration PR's Linux/Windows CI. Target Windows 11/RTX, iPhone and the
actual Compass-to-landed-server round trip remain separate, unmeasured checks.
