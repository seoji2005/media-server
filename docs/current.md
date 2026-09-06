# Current work

- **Milestone:** real model interruption/recovery across a 60-minute synthetic timeline;
  clarify ASR replay versus saved translation in the watching UI.
- **Branch / PR / HEAD:** `app/long-resume`, based on owner-approved #10 merge `175b8ac`.
  Resolve live Draft/HEAD in [open PRs](https://github.com/seoji2005/media-server/pulls).
  The new Draft needs separate merge approval. One writer; AGENTS.md and
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
  [Enhancement](enhancement-spike.md) has no adopted preset. Action/absent-scene search
  and natural Korean dialogue remain weak. CI spending was approved on 2026-09-06;
  Linux and Windows CPU jobs now execute; inspect [live results](https://github.com/seoji2005/media-server/actions/workflows/verify.yml).
  Earlier long-film/larger-encoder requests ended in cancelled approval; do not bypass them.
- **Next action:** resolve failing live checks, then compare one compression-aware
  enhancement candidate against the failed baseline. Natural long-dialogue ASR and
  bounded ASR recovery remain open; do not infer quality from a padded timeline. Windows/RTX
  access takes priority whenever available. Keep all October features included.
  [Gemini comparison/budget](translation-comparison.md#post-payment-diagnosis) remains
  incomplete (16/80); local stays default and private egress remains opt-in.
