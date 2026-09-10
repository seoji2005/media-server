# Current work

- **Milestone:** open the exact companion-delivered video with its saved viewing settings.
- **Branch / base:** `feat/verified-item-entry`, main
  `c0e27079995a9db9c2ae22f0b247c24a5560a0f6` (PR #28 merged).
  Resolve live PRs/HEAD/checks before writing; one writer and AGENTS.md govern.
- **Authorization:** continue the owner's multi-stage implementation, independent
  review and merge after successful checks. This is not final release approval.

## Current change

A bounded, identity-bound `#item` and authenticated POST open the existing player
using current audio, watch position and caption choice/Off/offset. New imports do
not need recommendation inclusion. Original and selected rendition integrity are
checked; changed identity/media fail. Entry stays paused and does not write watch
history before Play. Missing renditions have an explicit preparation action.
Invalid/late entries do not replace the current player. No schema, model or cloud
processing change. [Contract](companion-library.md#open-a-specific-imported-video).

Focused author Python/API and all eight DOM suites passed locally. Real browser
startup/restart and synthetic MKV/provided-caption preparation checks are added to
the existing Ubuntu/Windows CI; their final results and independent review remain
pending. Local DOM/TestClient are not actual browser or socket execution. Keep final
fixed HEAD, review and CI/merge facts in the PR, not a growing ledger here.

## Reconciled next work

- PR #28 already passed final Ubuntu/Windows CI and merged. Its caption choice,
  source/Off, offset and canonical-byte preservation are retained; do not redo it.
- Fetch is ahead of the supplied analysis: provided-caption delivery/retry and root
  library opening are implemented there. Do not recreate the Server caption API or
  modify the independently owned Fetch branch. It must adopt this new item entry.
- Qwen reloads ASR and alignment weights for every new span. Alignment determines
  the next span boundary, so batching ASR first changes checkpoint semantics. Measure
  loading/preparation/inference/cleanup separately before choosing reuse. Existing
  35-second runs are not a comparable speed pair (one reused the first 30 seconds).
  No actual model environment/weights or target GPU is available in the recovered
  runtime; new long natural-video inference remains unexecuted.

## Existing integration

- New jobs remain **Qwen3-ASR-1.7B + Qwen3-ForcedAligner-0.6B + Gemini 3.1 Flash-Lite**.
  [Setup and recovery](qwen-subtitles.md). The actual 35-second public sample's v2
  handoff removed its hard seam, and faithful-context-v5 preserved Obon/register.
  All five saved sample versions remain; this is not broad quality acceptance.
  Saved playback requires no paid inference.
- PR #27 passed [CI 34453769503](https://github.com/seoji2005/media-server/actions/runs/34453769503):
  231 tests per OS (one Windows-only skip on Ubuntu), seven DOM suites, actual
  synthetic Chrome playback and server restart. Its fresh review independently
  compared 97 initial/resume cases.
- [Two-hour resource measurement](evidence/qwen_audio_memory.json): real FFmpeg with
  deterministic model stubs reduced parent peak RSS from 910.172 to 39.383 MiB.
  Both paths produced identical 326 spans; interruption at 55:15 resumed only the
  remaining 176 stub calls. SQLite publication and HTTP/restart preserved originals
  and VTT. This excludes model/child FFmpeg memory and establishes no long natural
  video quality/speed claim. About 440 MiB temporary disk plus 32 MiB reserve is
  required; resume still decodes all source audio.
- Saved-source translation, scene search, opt-in local recommendations and companion
  caption/library APIs remain integrated.

## Remaining product gates

- Natural long-video/multilingual ASR, alignment, translation and subjective timing/
  readability. Resource stubs and synthetic captions do not establish this gate.
- Windows 11 / RTX 4070 SUPER 12 GB installation, VRAM, actual inference and recovery.
  Linux CPU history and Windows synthetic CI do not establish target-device fitness.
- Actual saved-caption screen review here remains blocked by prior local Chrome
  socket EPERM and supplied browser ERR_BLOCKED_BY_CLIENT. Synthetic CI screens
  verify UI behavior, not the real public sample's display quality.
- Conservative enhancement needs visual comparison and adoption. Fetch/Compass must
  adopt their contracts; Pocket needs a verified accessible contract. iPhone/LAN
  synchronization is separate from the local companion APIs.
