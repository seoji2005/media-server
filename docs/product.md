# Product contract

## Outcome and boundaries

A personal service prepares relevant videos for comfortable watching and improves
subsequent choices from explicit feedback. The owner is a viewer, not a routine editor,
file organizer or model operator. Preserve a unified, polished experience.

Target near-finished daily use **before the owner's October 2026 leave starts** on
Windows 11, Ryzen 5 7500F, 64 GB RAM, RTX 4070 SUPER 12 GB. The owner names October
12 or 19, 2026; neither is confirmed. Plan readiness by October 11 for the earlier start.
If October 19 is confirmed, use the extra week for quality and defects, not automatic
scope expansion. These are planning targets, not a delivery guarantee. Use Work/cloud
for all honest available execution,
including CPU model runs. Cloud limitations are evidence boundaries, not reasons
to postpone work that can run. The product is for watching, not editing.

October P0: local video library; permitted local/downloaded imports; playback and
resume; real Japanese/English/mixed-language ASR; Korean translated subtitles and
subtitle playback; resumable processing jobs; conservative real-video enhancement /
upscaling; original/enhanced switching; original preservation; Windows setup and diagnostics;
grounded content/scene analysis, content/scene search with time navigation, and basic
local preference recommendations from explicit feedback. Near-finished includes coherent
polished flows and failure recovery, not disconnected demonstrations.

Not this release: **all video downloading** (manual and automatic), AI video generation,
NAS integration, distributed infrastructure, multi-user/cloud collaboration, cross-device
sync and advanced recommendation research. Importing already-downloaded local files is
allowed; basic local recommendation remains included. No editor-first UI or speculative
abstractions for these. Enhancement targets live-action and dynamic scenes with
natural detail and temporal consistency; invented textures and excessive sharpening
are failures, not improvements. Human review is required for subjective adoption.

Later, permitted-source discovery/collection and an independent generation engine may
join the same experience; these are deferred goals, not current authorization. Preserve
the distinction between recommending, storing and spending compute on an item. Automatic
collection or generation must never count as the owner's positive feedback.

## Starting architecture (first import/play/resume slice implemented)

Prefer a custom library, UI and orchestration over a required Jellyfin foundation when
actual quality/control justify maintenance cost. Superiority is unproven. Use established
codecs, FFmpeg and appropriate player components. Reconsider only for concrete delivery/
reliability problems and present options before changing the owner-preferred direction.
Custom code does not itself establish local safety; verify offline operation and egress.

Python 3.12 + FastAPI, SQLite, a local browser UI and FFmpeg/FFprobe is the
implemented first-slice foundation: one modular local application, straightforward Python model
integration, transactional persistence and an inspectable player. Keep frontend
dependencies proportional to quality/maintenance needs; minimizing their count is not
the product goal. Inspect actual browser codec
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

## Watching and intelligence quality

- One card contains available versions/subtitles and persistent watch history. Hashes
  identify bytes, not semantic identity; similar versions never authorize original deletion.
  Original playback and subtitle readiness must not wait for enhancement completion.
- Build the watching UI early. Review selection, seeking, restart/resume, subtitle and
  rendition switching in the real browser: few-step playback, readable subtitles, keyboard
  access, smooth interaction and clear loading/error recovery without an editor. Preserve
  the owner's refined, Apple-like visual preference; screenshots alone prove little.
- Prefer quality over speed while execution remains usable. Assess supplied subtitles
  before unnecessary ASR. Inspect real omissions, hallucinations, translation distortion
  and timing; declare adoption criteria before comparing actual outputs.
- Diagnose before enhancement; already-good media may need no processing. Compare faces,
  hands, fast motion, darkness and camera movement during playback. Flicker, identity/shape
  changes or invented texture fail. Use human-reviewed conservative presets, automatic
  checks and original fallback, without requiring manual review of every video. Generative
  reconstruction is excluded from this release.
- Analysis/search results need evidence and timestamps. Label subtitle-only versus visual
  analysis honestly; keyword matching is not proof of visual understanding. Avoid spoilers
  in pre-watch summaries. Evaluate relevant scene retrieval on a small judged sample.
- Recommendations should reduce choosing time. Prioritize explicit like/dislike/less-of-this;
  watch time is secondary, unseen is not disliked, and exclusion from taste learning must
  be possible. Show that explicit feedback changes relevant suggestions on sample items.
- Protect videos, subtitles, thumbnails, prompts, analysis, search and taste history equally.
  Private scopes stay out of general search/recommendations/alerts and external metadata
  calls. Verify offline behavior and private-payload absence in logs/Git; no private cloud
  samples, telemetry or inference by default.

## First product slice, authorized on 2026-09-05

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

The import/play/resume slice is an engineering checkpoint. The first useful viewing
milestone additionally requires real Korean subtitles and interrupted processing recovery.
Probe natural live-action enhancement and 12 GB feasibility early while integrating
subtitles, then add version switching/fallback. Grounded analysis/search/basic recommendation
may proceed on completed inputs while enhancement has an isolated hardware blocker.
Finish with integrated UX, real long-video recovery and clean Windows installation.
Do not silently omit included features or count unresolved checks as complete. Reserve
integration/defect-correction time now: aim for an integrated candidate by October 5 and
stabilization October 6–11. Reassess against actual progress without silently cutting
required quality. Exact leave confirmation must not postpone feasible work. Target RTX
checks require actual hardware access even if cloud preparation meets these dates.

P0 delivery requires real long-video recovery, subtitle quality, natural enhancement,
Windows setup and target RTX evidence beyond the first slice. No percentages or
release claims based only on fixture counts. Unknown 12 GB fit remains unknown until measured.
