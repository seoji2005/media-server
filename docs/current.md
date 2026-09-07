# Current work

- **Milestone:** a simple Windows viewing launcher, alongside completed real ASR
  speech/dialogue comparisons; preserve existing startup/recovery and quiet default CLI.
- **Branch / PR / HEAD:** `app/windows-viewing-launch`, from main `7d09815` after
  [PR #11](https://github.com/seoji2005/media-server/pull/11) merged. Resolve live work in
  [open PRs](https://github.com/seoji2005/media-server/pulls). One writer; [product](product.md) and AGENTS.md govern.
- **What works:** import/compatible copies, shared audio, playback/resume, actual local
  ASR/Korean captions, recoverable jobs, literal/visual scene search, previews and explicit
  feedback. ASR spans survive [actual worker kill](quality-check.md#speech-span-checkpoints--2026-09-07).
  [Six speech/dialogue comparisons](speech-quality.md#span-boundary-comparison--2026-09-07)
  retained normalized words; two fresh-process resumes matched text/timing exactly.
  The [Windows launcher](../README.md#설치와-실행) opens the local page only after this
  server binds; browser failure leaves it usable. [Checks and limits](quality-check.md#windows-viewing-launcher--2026-09-07).
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
- **Next action:** complete the launcher's Linux/Windows CI, then inspect Korean output
  from the already permitted film dialogue through actual translation and caption display.
  Target Windows/RTX takes priority on access; natural long speech and useful enhancement
  remain open. Keep all October features included.
  [Gemini comparison](translation-comparison.md#post-payment-diagnosis) remains incomplete
  (16/80); local stays default and private egress stays opt-in.
