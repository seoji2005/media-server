# Current work

- **Milestone:** preserve the working viewing flow with repeatable checks. #9 is merged;
  #10 includes different-film retrieval, whole 12-minute subtitles and partial translation comparison.
- **Branch / PR / HEAD:** `app/scene-quality`; resolve its live Draft PR/HEAD in
  [open PRs](https://github.com/seoji2005/media-server/pulls). Base main `bfce827` includes
  owner-approved #9. The Draft needs separate merge approval. One writer;
  AGENTS.md and [product contract](product.md) govern; no harness redesign.
- **What works:** import/compatible copies, shared audio, playback/resume, real ASR/Korean
  captions and recoverable jobs, literal/visual scene search, previews and explicit-feedback
  recommendations. [New quality findings](quality-check.md), [scene setup](scene-search.md),
  [ASR/runtime](subtitles.md), [readability](subtitle-readability.md),
  [renditions/audio/UI](compatible-renditions.md). [One verification command](../README.md#검증과-작업-방식)
  now includes all seven DOM suites and real browser import/captions/playback/server restart.
- **Current blockers:** no Windows 11/RTX access or natural 60+ minute speech input. ASR
  interruption repeats its stage; the 12-minute run supplied no interruption proof.
  [Enhancement](enhancement-spike.md) has no adopted preset. Action/absent-scene search
  and natural Korean dialogue remain weak. CI spending was approved on 2026-09-06;
  Linux and Windows CPU jobs now execute; inspect [live results](https://github.com/seoji2005/media-server/actions/workflows/verify.yml).
  Earlier long-film/larger-encoder requests ended in cancelled approval; do not bypass them.
- **Next action:** resolve any failing live check before new implementation; measure
  long-timeline interruption/repeated work using existing permitted
  media (operational evidence only); use natural long dialogue separately for ASR quality.
  Avoid chunked ASR design before measuring loss. Next product experiment is one
  compression-aware enhancement candidate against the failed baseline. Windows/RTX
  access takes priority whenever available. Keep all October features included.
  [Gemini comparison/budget](translation-comparison.md#post-payment-diagnosis) remains
  incomplete (16/80); local stays default and private egress remains opt-in.
