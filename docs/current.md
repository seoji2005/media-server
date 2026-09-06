# Current work

- **Milestone:** approximate visual search now works inside the selected video's player,
  with saved images/timestamps and restartable preparation. October acceptance remains open.
- **Branch / PR / HEAD:** `app/scene-retrieval`, [Draft PR #9](https://github.com/seoji2005/media-server/pull/9).
  Resolve live HEAD there; verified code `029f9e0`, followed by documentation. Base main
  `f0b0010` includes owner-approved #8. #9 still needs separate merge approval.
  One writer; this checkout's AGENTS.md and [product contract](product.md) govern.
- **What works:** import/compatible copies, shared audio, playback/resume, real ASR/Korean
  captions and recoverable jobs, literal caption search, explicit-feedback recommendations,
  time previews and selected-video visual candidates. [Scene search setup/results](scene-search.md),
  [retrieval development evaluation](scene-retrieval.md), [previews](previews.md),
  [renditions/audio/UI](compatible-renditions.md), [ASR/runtime](subtitles.md),
  [readability](subtitle-readability.md), [speech quality](speech-quality.md).
- **Current blockers:** no Windows/RTX access or suitable local 60+ minute ASR input.
  Earlier long-film download and larger retrieval-model lookup ended in cancelled network
  approval; neither was retried here. The permitted short-film/model were reused locally.
  ASR interruption still repeats its stage. [Enhancement](enhancement-spike.md) has no
  adopted preset; held-out visual quality/absent-scene handling and Windows polish remain
  open. HEVC/10-bit policy, spending and scope cuts require owner decisions.
- **Next action:** test different permitted live-action content for useful visual candidates
  and missed short scenes before extending analysis into recommendations. Prioritize long
  ASR recovery and Windows/RTX as soon as input/access is available. Keep enhancement and
  semantic retrieval included; avoid expanding diagnostics/harness or adding default query
  translation without better evidence.
