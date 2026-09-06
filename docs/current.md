# Current work

- **Milestone:** compatible playback and a viewing-first UI. H.264 MKV/audio preparation
  is implemented; this follow-up improves readable controls and hides optional panels.
  This is an October checkpoint, not complete product or Windows/RTX acceptance.
- **Branch / PR / HEAD:** `app/compatible-renditions`, [Draft PR #8](https://github.com/seoji2005/media-server/pull/8).
  Read its live HEAD when resuming; the PR is the revision source. Base **main `4a8c20a`**
  includes owner-authorized PR #7. #8 still needs owner merge approval. One writer;
  use the current checkout's AGENTS.md and [product contract](product.md).
- **What works:** import/library, verified playback and watch resume; separate compatible
  copies with first-audio consistency and failure retry; local ASR→Korean, append-only
  captions, sentence translation and resumable translation batches. Subtitle selection
  stays visible; preparation, scene search and taste open on demand. Diagnostics live
  in Settings. Literal subtitle search and explicit-feedback title recommendations work.
  Evidence/limits: [renditions and UI](compatible-renditions.md), [ASR/runtime](subtitles.md),
  [readability](subtitle-readability.md), [speech quality](speech-quality.md), [recommendations](recommendations.md).
- **Current blockers:** no Windows/RTX access. A public long-film download returned a
  cancelled network approval; no suitable local 60+ minute input was available. Short
  CPU/browser probes do not replace either gate. ASR interruption repeats the ASR stage.
  [Enhancement](enhancement-spike.md) has no adopted preset; visual/semantic scene analysis
  remains unimplemented. Alternate audio selection and Windows launch/polish remain open.
  HEVC/10-bit video encoding policy, spending and scope cuts need owner decisions.
- **Next action:** PR #8's browser verification is complete; owner merge approval remains.
  Next add explicit audio selection shared by playback and ASR; consolidate the migrations
  needed for that change. On access becoming available, prioritize real 60+ minute
  processing/memory/recovery and Windows/RTX E2E. Keep enhancement and visual search
  included; feed future content analysis into recommendations after retrieval works.
