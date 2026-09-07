# Current work

- **Milestone:** real long-timeline recovery and moving-video enhancement comparisons;
  clarify ASR replay versus saved translation in the watching UI.
- **Branch / PR / HEAD:** `app/long-resume`, based on owner-approved #10 merge `175b8ac`.
  Resolve live Draft/HEAD in [open PRs](https://github.com/seoji2005/media-server/pulls).
  Draft #11 needs separate merge approval. One writer; AGENTS.md and
  [product contract](product.md) govern; no harness redesign.
- **What works:** import/compatible copies, shared audio, playback/resume, real ASR/Korean
  captions and recoverable jobs, literal/visual scene search, previews and explicit-feedback
  recommendations. [Model/recovery and viewing evidence](quality-check.md), [scene setup](scene-search.md),
  [ASR/runtime](subtitles.md), [readability](subtitle-readability.md),
  [renditions/audio/UI](compatible-renditions.md). [One verification command](../README.md#검증과-작업-방식)
  now includes all seven DOM suites and real browser import/captions/playback/server restart.
- **Current blockers:** no Windows 11/RTX access or natural 60+ minute speech input. ASR
  interruption repeats its stage; the new sparse timeline confirms that loss and saved
  translation reuse, without establishing long-dialogue quality or target performance.
  [Enhancement](enhancement-spike.md#moving-filter-baseline--2026-09-07) has no
  adopted preset: neither the image model nor the mild filter justified adoption. Action/absent-scene search
  and natural Korean dialogue remain weak. CI spending was approved on 2026-09-06;
  Linux and Windows CPU jobs now execute; inspect [live results](https://github.com/seoji2005/media-server/actions/workflows/verify.yml).
  Earlier long-film/larger-encoder requests ended in cancelled approval; do not bypass them.
- **Next action:** bound ASR restart loss with a small checkpointed interval design and
  boundary/restart validation, using the measured lost work as its acceptance case.
  Natural long-dialogue quality and useful enhancement remain open; do not infer quality
  from a padded timeline or slight sharpening. Windows/RTX
  access takes priority whenever available. Keep all October features included.
  [Gemini comparison/budget](translation-comparison.md#post-payment-diagnosis) remains
  incomplete (16/80); local stays default and private egress remains opt-in.
