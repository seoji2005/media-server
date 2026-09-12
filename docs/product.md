# Product contract

Prepare permitted local videos for comfortable watching in a refined, smooth
personal media app. The owner is a viewer, not a routine editor or model operator.

Target: Windows 11, Ryzen 5 7500F, RAM 64 GB, RTX 4070 SUPER 12 GB.
The owner confirmed leave starts October 19, 2026; plan usable by October 11.
Aim for an October 5 integration candidate and October 6–11 stabilization.
An extra week improves quality, not scope. These are targets, not delivery claims.

## October scope

- Local import/library; playback, seeking and persisted resume.
- Real Japanese/English/mixed ASR, Korean translation and timed subtitle playback.
- Resumable processing jobs, including interruption and failure recovery.
- Conservative natural live-action enhancement/upscaling; original/enhanced switching.
- Grounded content/scene analysis and search with time navigation.
- Basic local recommendations using explicit feedback.
- Polished viewing flows, original preservation, clean Windows setup/diagnostics/recovery.

Exclude all video downloading, AI video generation, NAS, distributed/multi-user/cloud
collaboration, cross-device sync and advanced recommendation research. Importing
already-downloaded permitted files is allowed. Never silently drop included features
or count unresolved quality gates as complete.

## Structure and safety

Prefer a custom library/UI/runtime when quality and control justify maintenance.
Use established codecs/player components. Custom code does not prove superiority or
privacy. Keep the current Python 3.12/FastAPI/SQLite/local browser/FFmpeg foundation
unless a concrete product problem justifies changing it; no speculative microservices.

| Identity | Responsibility |
| --- | --- |
| MediaItem | One library card and watch history |
| Rendition/file | Original or playable derivative, separate identity/integrity |
| Derived artifact | Transcript, translation, subtitle or analysis linked to inputs |
| Job / attempt | Requested processing versus one execution/retry |

Read sources without mutation; copy to owned staging, verify, then publish.
No source hard links, overwrites or automatic deletion. Hash equality identifies
bytes, not semantic identity; similar videos never authorize deletion.
Failed subtitles/enhancement must leave the original watchable. Keep source transcript,
translation and timing separate; changed inputs/model/config invalidate stale results.

Protect media, subtitles, thumbnails, prompts, analysis and search/taste/watch history.
Private scopes stay out of general search/recommendations/alerts and external metadata.
Verify offline operation and absence of private payloads in logs/Git; no private
egress by default. Development cloud samples must be permitted and non-private.
Owner-approved Gemini translation is an explicit per-video choice: send recognized/saved
dialogue and bounded neighboring text only, with egress/billing disclosure. No media,
titles, paths, watch history or credentials enter prompts. Under the owner's September 8
instruction, Gemini is the initial UI selection; starting it requires a labeled Gemini
action with visible egress/billing disclosure. Merely opening a video sends nothing.
The September 9 owner instruction fixes new ASR to Qwen3-ASR-1.7B plus
Qwen3-ForcedAligner-0.6B. The September 11 owner-approved continuation adopts
Gemini 3.8 Flash for new jobs with the evaluated v5 prompt/context and low thinking.
Historical Lite/v1–v5 jobs retain their exact saved configurations. New API requests
omitting a provider use Gemini; explicit local requests are rejected. Existing jobs
retain their saved settings. Minimal local companion caption and library APIs are
authorized by the owner's integration feedback; cross-device synchronization remains
a separate pending contract.
Never automatically retry or switch providers. Fresh Gemini jobs recognize
speech locally and send only the validated transcript for translation; saved-transcript
retranslation skips ASR. Media/audio never enter either cloud path.

## Quality and delivery

- One card holds versions/subtitles. Original playback and ready subtitles never wait
  for enhancement. Inspect few-step playback, keyboard access, readable subtitles,
  seek/resume, switching, loading and recovery in the real browser, not screenshots alone.
- Obtain real ASR → Korean subtitles → playback early. Check supplied subtitles before
  unnecessary ASR. Prefer quality while runtime remains usable. Inspect omissions,
  hallucinations, translation distortion and timing; record model/version, license,
  machine, elapsed time and limits. Do not build a model-selection framework first.
- Diagnose before enhancement; good media may need none. Compare moving faces/hands,
  fast action, darkness and camera motion. Flicker, altered shapes/identity and invented
  texture fail. Use human-reviewed conservative presets, automated checks and original
  fallback without requiring the owner to inspect every video. Probe 12 GB feasibility
  early; only target measurements establish fit. Generative reconstruction is excluded.
- Search needs evidence/timestamps; distinguish subtitle matching from visual analysis.
  Judge retrieval on a small relevant sample. Pre-watch summaries avoid spoilers.
- Recommendations prioritize like/dislike/less-of-this. Watch time is secondary;
  unseen is not disliked; allow excluding history from learning. Check that feedback
  changes relevant suggestions and preserves useful diversity.
- Validate actual restart and interrupted jobs, long-video recovery, source/copy
  integrity, duplicate import, partial copy, disk-full, missing/changed files and
  invalid positions. Preserve useful regressions from real failures.
- Use cloud/CPU for feasible work now; Windows installation/codecs, target RTX and
  human viewing quality remain separate gates. Record limits honestly; environment
  blocks need not stop independent work.

Current implementation/evidence and the next slice live in [current](current.md).
The first useful viewing milestone adds real Korean subtitles and processing recovery
to import/play/resume; then integrate enhancement, search/recommendations and Windows
polish. Final acceptance covers the complete October scope, not a fixture count.
