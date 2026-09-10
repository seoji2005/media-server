# Current work

- **Milestone:** remember caption choices and adjust timing while watching.
- **Branch / base:** `feat/caption-viewing-settings`, main
  `16d53d96025e0e00f0e8b29aa76c4be5c993a11a`.
  [PR #27](https://github.com/seoji2005/media-server/pull/27) is merged. Resolve live
  PRs, HEAD and checks before writing; one writer, AGENTS.md and product.md govern.
- **Authorization:** the owner requests multiple stages, review and merge after
  successful checks. Do not reinstate old one-stage or pending-approval limits.

## Current change

Caption version/source/Off and timing adjustments survive reopening and server
restart independently for each video's audio. Native Off/On participates. Earlier
and later controls step by 0.5 seconds within ±10 seconds; switching versions resets
its timing. Original time and automatic selection can be restored. Playback position
stays unchanged and caption search follows the adjusted time.

[Contract, API and validation](caption-viewing.md). Schema v10 adds only viewing
settings. VTT response timing changes without altering originals, captions,
transcripts, translations, checkpoints or hashes. Revision checks reject stale writes;
uncertain saves require a read before further edits. Missing versions stay Off with
a notice. No model or cloud inference is added.

Acceptance requires focused author checks, a fresh independent persistence/privacy
review, and final Ubuntu/Windows Python/DOM/actual Chrome CI. Final fixed HEAD,
review, CI attempts and merge facts belong in the live PR and existing validation
bundle. Pending CI and subjective quality must not be described as passed.

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
