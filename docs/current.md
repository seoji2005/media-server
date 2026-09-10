# Current work

- **Milestone:** measure Qwen loading, preparation, inference, decoding and cleanup
  on the unchanged production speech path before choosing a reuse strategy.
- **Branch / content base:** `feat/qwen-stage-cost`, main PR #29 merge
  `10815499df8d5d9046ac15ee95e44c857837a687`. The recovered local base has the
  identical tree `897daee05b473e6394badb410e9038f2b2e45358`.
- **Authorization:** continue the owner's multi-stage implementation, independent
  review and merge after successful checks. This is not final release approval.

## Current change

Qwen exposes optional bounded phase aggregates, disabled during normal app work.
An offline [speech probe](qwen-subtitles.md#measure-local-speech-cost) calls the actual
`transcribe_parts` path and writes a fresh, explicitly selected output directory.
No model residency, call order, checkpoint schema, profile, identity, translation,
DB or player change. Saved spans still skip model calls. Input/model identity must
remain unchanged; failed/unfinished samples are never reported as complete.

Local fixture checks cover enabled/disabled identical results and runtime identity,
saved-prefix/full resume, CUDA synchronization boundaries, failure cleanup and
redacted/exclusive probe outputs. Fresh independent review found and resolved a
CUDA-observer cleanup failure and recovery provenance bypass, including rejected
and in-run changed evidence. Final bounded rereview approved the fixes.

The fixed CPU runtime and pinned model files were explicitly installed/downloaded.
[Actual 35-second cost and restart evidence](evidence/qwen_speech_cost.json): fresh
speech runs took 83.515 and 88.591 seconds with identical canonical parts hashes.
The first included 9.237 seconds of model loading, so it was not the dominant cost
in this short CPU case. Full saved recovery made zero model calls (0.122 seconds
speech stage; setup/imports separate). No Gemini/network attempts or old-track writes.
A 605.350-second continuous public dialogue is now running through this same speech
path; its result is pending. It is previously studied audio, not a new holdout.

## Reconciled integration

- PR #29 merged after fresh independent review and final Windows/Ubuntu
  [CI 34470638573](https://github.com/seoji2005/media-server/actions/runs/34470638573).
  Each OS passed 242 Python tests (one Windows-only skip on Ubuntu), eight DOM
  suites and actual synthetic Chrome startup/restart/preparation. Final Windows
  desktop/mobile screenshots were inspected. The Windows feed failure was fixed
  with the same FFmpeg release, a versioned URL and verified SHA-256.
- Identity-bound `#item` opens the delivered video paused with saved caption choice,
  Off/offset, audio and watch position; preparation requires an explicit action.
  [Saved public-sample HTTP evidence](evidence/item_entry_saved_playback.json)
  preserves five tracks, canonical bytes and all DB rows without inference.
  The independently owned Fetch adapter still must adopt this contract.
- PR #28 caption settings and Fetch provided-caption delivery are already integrated;
  do not recreate them or edit the independently owned Fetch branch.
- Qwen reloads both models per new span, and alignment determines the next boundary.
  Batching ASR first would change checkpoint semantics. The prior 35-second times
  are not a comparable speed pair because one reused its first 30 seconds.

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
