# Current work

- **Milestone:** resume completed ASR speech spans after interruption; compare recovery
  with actual local Whisper while retaining prior jobs, captions and original files.
- **Branch / PR / HEAD:** `app/long-resume`, based on owner-approved #10 merge `175b8ac`.
  Owner authorized continuation and merge on 2026-09-07; resolve live HEAD/merge state in
  [PR #11](https://github.com/seoji2005/media-server/pull/11). One writer; [product](product.md) and AGENTS.md govern.
- **What works:** import/compatible copies, shared audio, playback/resume, actual local
  ASR/Korean captions, recoverable jobs, literal/visual scene search, previews and explicit
  feedback. New ASR spans survive actual worker kill with identical resumed text/timing on
  a short repeated English fixture; [evidence and limits](quality-check.md#speech-span-checkpoints--2026-09-07).
  [Runtime/recovery](subtitles.md), [readability](subtitle-readability.md),
  [audio/UI](compatible-renditions.md), [scene search](scene-search.md).
  [Verification](../README.md#검증과-작업-방식) runs Python, all seven DOM suites and real browser checks.
- **Current blockers:** no Windows 11/RTX access or natural 60+ minute speech validation.
  ASR still decodes/VADs the whole audio on resume; uninterrupted speech has no replay cap.
  [Enhancement](enhancement-spike.md#moving-filter-baseline--2026-09-07) has no adopted preset.
  Natural Korean and action/absent-scene retrieval quality remain weak. Local Chrome
  currently fails with socket EPERM; [Linux/Windows CPU CI](https://github.com/seoji2005/media-server/actions/workflows/verify.yml)
  is available under the owner's spending approval. Earlier long-film/larger-encoder
  requests ended in cancelled approval; do not bypass them.
- **Next action:** check span-boundary recognition/context on existing permitted non-repeated
  dialogue and language-change samples; extend input length when permitted material is
  available. Target Windows/RTX takes priority on access. Keep all October features included.
  [Gemini comparison](translation-comparison.md#post-payment-diagnosis) remains incomplete
  (16/80); local stays default and private egress stays opt-in.
