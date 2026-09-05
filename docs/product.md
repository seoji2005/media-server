# Product contract

## Outcome and boundaries

By mid-October 2026, practically usable on Windows 11, Ryzen 5 7500F, 64 GB RAM,
RTX 4070 SUPER 12 GB. Before then use Work/cloud for all honest available execution,
including CPU model runs. Cloud limitations are evidence boundaries, not reasons
to postpone work that can run. The product is for watching, not editing.

October P0: local video library; permitted local/downloaded imports; playback and
resume; real Japanese/English/mixed-language ASR; Korean translated subtitles and
subtitle playback; resumable processing jobs; conservative real-video enhancement /
upscaling; original/enhanced switching; original preservation; Windows setup and diagnostics.

Not P0: NAS, generation, distributed infrastructure, multi-user/cloud collaboration,
advanced recommendation and automatic downloading. No editor-first UI or speculative
abstractions for these. Enhancement targets live-action and dynamic scenes with
natural detail and temporal consistency; invented textures and excessive sharpening
are failures, not improvements. Human review is required for subjective adoption.

## Starting architecture (provisional, not installed or implemented)

Python 3.12 + FastAPI, SQLite, a small local browser UI and FFmpeg/FFprobe is the
working hypothesis: one modular local application, straightforward Python model
integration, transactional persistence and an inspectable player. Keep frontend
dependencies minimal until interactions justify them. Inspect actual browser codec
support; add a derived compatible rendition if necessary, preserving the original.
Reconsider a desktop shell if local file selection or playback compatibility prevents
a usable Windows flow. Do not choose infrastructure solely for a cloud preview.

| Identity | Meaning |
| --- | --- |
| MediaItem | One user-visible video and its watch history |
| Rendition/file | Original or derived playable file, its own ID and integrity metadata |
| Derived artifact | Transcript, translation, subtitle or other output, linked to its input |
| Job / attempt | Requested processing versus one execution/retry; separate IDs |

Copy from original read-only input to app-owned staging; verify before publication.
No source hard links, overwrites or deletion. A failed subtitle/enhancement job must
leave original playback available. Content hashes validate bytes, not user identity.
Keep immutable source transcript separate from Korean translation and subtitle timing.
Use model/config/input identity to invalidate stale processing outputs when needed.

## First product slice, when implementation is requested

- Outcome: permitted local video → MediaItem → library → playback → persisted resume.
- Non-goals: ASR, translation, enhancement, downloading, editing and model benchmarking.
- Acceptance: import a supported file; preserve source hash; show one item; play and
  seek; save position; restart the actual process and resume the same item.
- Failures: malformed/unsupported input, source changing during copy, partial copy,
  destination collision, insufficient space, duplicate import, missing managed file,
  invalid resume value, restart during save, cross-origin request and private log leakage.
- Verify: focused unit/integration tests, generated playable FFmpeg fixture, API/range
  requests, browser flow and actual process restart; inspect original/copy hashes and DB.
  Record unavailable browser/Windows checks explicitly. No private media needed in cloud.

Then obtain real ASR → Korean translation → subtitle playback outputs from a permitted
non-private Japanese/English/mixed-language sample. Do not wait for a perfect model
selection framework. Compare enough real output to expose omissions/hallucinations;
record license, machine, model/version, elapsed time and limitations honestly.

P0 delivery requires real long-video recovery, subtitle quality, natural enhancement,
Windows setup and target RTX evidence beyond the first slice. No percentages or
release claims based only on fixture counts. Unknown 12 GB fit remains unknown until measured.
