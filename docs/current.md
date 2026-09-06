# Current work

- **Milestone:** PR #8 merged; first real Korean visual-retrieval evaluation completed.
  Retrieval is not yet connected to the app; October product acceptance remains open.
- **Branch / PR / HEAD:** `app/scene-retrieval`; find its live Draft PR/HEAD in
  [open PRs](https://github.com/seoji2005/media-server/pulls). Base **main `f0b0010`**
  includes owner-approved #8 (`940fe5a`). The next PR needs separate merge approval.
  One writer; this checkout's AGENTS.md and [product contract](product.md) govern.
- **What works:** import, compatible copies, shared audio selection, playback/resume,
  real ASR/Korean captions with recoverable jobs and preserved versions; literal caption
  search, title/feedback recommendations and on-demand time previews. New offline
  [retrieval evaluation](scene-retrieval.md) measured Korean/English queries on 36 public
  frames. Supporting evidence: [previews](previews.md), [renditions/audio/UI](compatible-renditions.md),
  [ASR/runtime](subtitles.md), [readability](subtitle-readability.md), [speech quality](speech-quality.md).
- **Current blockers:** no Windows/RTX access or suitable local 60+ minute input. Earlier
  long-film download and latest upper-size retrieval-model lookup returned cancelled
  network approval. A permitted short-film sample/model download succeeded separately;
  it does not replace long ASR or target checks. ASR interruption repeats its stage.
  [Enhancement](enhancement-spike.md) has no adopted preset; semantic search integration,
  held-out retrieval/no-match quality and Windows polish remain open. HEVC/10-bit policy,
  spending and scope cuts still require owner decisions.
- **Next action:** connect an explicitly approximate visual shortlist to the selected
  video's saved preview images/timestamps, preserving existing viewing and private scope.
  Do not add query translation by default: small measured gain, added cost and distortions.
  Compare a larger native encoder when permitted; do not imply it was tested. Prioritize
  long-input recovery and Windows/RTX when access is available. Keep enhancement and
  semantic retrieval included; do not expand diagnostics/harness.
