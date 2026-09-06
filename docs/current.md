# Current work

- **Milestone:** compatible playback, shared audio selection and resumable time previews.
  An October checkpoint, not complete product or Windows/RTX acceptance.
- **Branch / PR / HEAD:** `app/compatible-renditions`, [Draft PR #8](https://github.com/seoji2005/media-server/pull/8).
  Read its live HEAD when resuming. Base **main `4a8c20a`** includes owner-approved #7;
  #8 needs separate owner merge approval. One writer; this checkout's AGENTS.md and
  [product contract](product.md) govern.
- **What works:** import, compatible copies, audio selection, playback/resume, real local
  ASR/Korean captions with recoverable jobs and preserved versions. Literal subtitle
  search, explicit-feedback title recommendations and optional viewing panels work.
  On-demand time previews now persist per image, resume and navigate back to the video.
  Evidence: [previews](previews.md), [renditions/audio/UI](compatible-renditions.md),
  [ASR/runtime](subtitles.md), [readability](subtitle-readability.md),
  [speech quality](speech-quality.md), [recommendations](recommendations.md).
- **Current blockers:** no Windows/RTX access or permitted local 60+ minute input; the
  earlier public-film download returned a cancelled network approval. ASR interruption
  repeats its stage. [Enhancement](enhancement-spike.md) has no adopted preset; semantic
  scene retrieval and Windows launch/polish remain open. Time sampling does not complete
  visual analysis. HEVC/10-bit encoding policy, spending and scope cuts need owner decisions.
- **Next action:** ground local scene retrieval in the saved frames and timestamps; first
  evaluate a small permitted sample with relevant queries before choosing/integrating a
  model. Keep enhancement and semantic retrieval included; improve recommendations after
  content signals work. Prioritize long-input recovery and Windows/RTX E2E when access is
  available. Do not expand diagnostics/harness or stack another PR over #8.
