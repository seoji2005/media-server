# Current work

- **Milestone:** compatible playback, readable viewing controls and shared audio selection.
  This is an October checkpoint, not complete product or Windows/RTX acceptance.
- **Branch / PR / HEAD:** `app/compatible-renditions`, [Draft PR #8](https://github.com/seoji2005/media-server/pull/8).
  Read its live HEAD when resuming; the PR is the revision source. Base **main `4a8c20a`**
  includes owner-authorized PR #7. #8 still needs owner merge approval. One writer;
  use this checkout's AGENTS.md and [product contract](product.md).
- **What works:** import/library, verified playback and watch resume; separate compatible
  copies, audio selection and preparation retry. New ASR jobs use the heard voice;
  existing jobs retain theirs through pause/restart, with append-only caption versions.
  SQLite migrations are centralized. Caption selection stays visible; optional viewing
  panels open on demand and diagnostics live in Settings. Literal subtitle search and
  explicit-feedback title recommendations work. Evidence/limits: [renditions/audio/UI](compatible-renditions.md),
  [ASR/runtime](subtitles.md), [readability](subtitle-readability.md), [speech quality](speech-quality.md),
  [recommendations](recommendations.md). Fresh review's preference race was fixed/rechecked.
- **Current blockers:** no Windows/RTX access. A public long-film download returned a
  cancelled network approval; no suitable local 60+ minute input was available. Short
  CPU/browser probes do not replace either gate. ASR interruption repeats its stage.
  [Enhancement](enhancement-spike.md) has no adopted preset; visual/semantic scene analysis
  and Windows launch/polish remain open. HEVC/10-bit video encoding policy, spending and
  scope cuts need owner decisions. Each new audio choice can require another video copy.
- **Next action:** PR #8 awaits owner merge approval. Prioritize real 60+ minute processing,
  memory/recovery and Windows/RTX E2E when permitted input/hardware becomes available.
  The next unblocked product slice is timestamped visual scene navigation as a foundation
  for grounded scene search. Keep enhancement and semantic retrieval included; add content
  signals to recommendations after retrieval works. Do not expand diagnostics/harness.
