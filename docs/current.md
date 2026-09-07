# Current work

- **Milestone:** explicit Gemini retranslation of saved original dialogue; text-only
  requests, durable per-request results and provider-preserving resume/restart.
- **Branch / PR / HEAD:** `app/gemini-translation`, based on main `633192b` after
  [PR #19](https://github.com/seoji2005/media-server/pull/19) merged. Resolve live work in
  [open PRs](https://github.com/seoji2005/media-server/pulls). One writer; [product](product.md) and AGENTS.md govern.
- **What works:** import/compatible copies, shared audio, playback/resume, actual local
  ASR/Korean captions, recoverable jobs, literal/visual scene search, previews and explicit
  feedback. ASR spans survive [actual worker kill](quality-check.md#speech-span-checkpoints--2026-09-07).
  [Six speech/dialogue comparisons](speech-quality.md#span-boundary-comparison--2026-09-07)
  retained normalized words; two fresh-process resumes matched text/timing exactly.
  The [Windows launcher](../README.md#설치와-실행) opens the local page only after this
  server binds; browser failure leaves it usable. [Checks and limits](quality-check.md#windows-viewing-launcher--2026-09-07).
  [Original caption switching](subtitles.md#watching-with-existing-subtitles) reuses saved
  ASR without inference. It helps inspect translations; it does not fix their meaning.
  [Native tokenization](translation-comparison.md#native-tokenizer-repair--2026-09-07)
  restores rare characters that the fast tokenizer dropped or exposed as byte tokens.
  [Saved-transcript retranslation](subtitles.md#translating-a-saved-transcript-again)
  uses only MT files/runtime; [actual server/worker execution](evidence/retranslation.json)
  took 16.289 s without ASR weights, ASR imports or external Python socket attempts.
  [Companion scene entry](companion-moments.md) integrates the separate PR #15 proposal
  through schema v7; donor branch stays intact. Compass needs a landed-revision round trip.
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
- **Next action:** configure `GEMINI_API_KEY`, verify the production saved-transcript
  path against the real API, and complete the remaining 64 comparison inputs using the
  16 preserved results. Owner authorized Gemini; its previous temporary key is absent.
  [Integration and limits](subtitles.md#optional-gemini-retranslation). No real Gemini
  execution or quality adoption is claimed by the fixture checks. Establish runtime
  capacity before downloading any further local weights.
  [Qwen3.5 Q6_K](translation-comparison.md#qwen35-q6_k-comparison--2026-09-07)
  completed 80 cases but is not adopted: 64 matched the response format and several
  Japanese inputs remained Japanese. The qualitative assessment favored MADLAD.
  [contextual Qwen3-4B](translation-comparison.md#contextual-qwen-comparison--2026-09-07)
  completed all 80 inputs but is not adopted: clock-time corruption and changed actions
  remain. Default translation is MADLAD; saved-transcript retranslation also offers
  explicit Gemini. Fresh speech recognition and translation remain local.
  [sentence splitting and decoding settings](translation-comparison.md#bounded-decoding-comparison--2026-09-07)
  did not establish a general improvement, so none was adopted. Saved ASR can now be
  reused when translator updates arrive. Preserve the frozen comparison rather than
  treating it as a new holdout. Idioms, register and omissions remain unresolved.
  Target Windows/RTX takes priority on access; natural long speech and useful enhancement
  remain open. Keep all October features included.
  [Gemini comparison](translation-comparison.md#post-payment-diagnosis) remains incomplete
  (16/80); local stays default and private egress stays opt-in.
