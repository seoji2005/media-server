# Current work

- **Milestone:** [Acoustic ASR pilot and free API access](asr-acoustic-comparison.md)
  completed actual CPU Media Server/WhisperJAV v2/v3 and Gemini API inference on a
  common 92-second synthetic WAV. Intended SRT is not listened-to gold; no real-media
  quality winner or ASR default change. [Gemini default](cloud-speech-and-translation.md):
  Gemini 3.1 Flash-Lite is initially selected in the UI, with a labeled cloud action and
  source-faithful context. Local MADLAD stays selectable; ASR remains local. Historical
  Gemini jobs retain the exact original model/prompt during resume and restart.
- **Branch / PR / HEAD:** `research/asr-acoustic-comparison`, based on main `8e98ef2` after
  [PR #23](https://github.com/seoji2005/media-server/pull/23) merged. Resolve live work in
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
- **Next action:** Obtain Groq/Mistral/Subtitle Nexus keys and check the account's free
  allowance/model access before extending the same public audio comparison. This host
  now has pinned large-v2/v3 weights and completed CPU inference; the earlier 1.3 GB
  disk blocker is obsolete. Recheck capacity before any further model download.
  Investigate short/quiet utterances absent from Media Server's saved VAD spans;
  do not promote a preset from this repeated synthetic pilot alone. A full fresh
  ASR → Gemini app/job path and target GPU validation remain open. Mistral Small 4 is the next translation API
  candidate if a key is supplied. Qwen's incorporated Alibaba terms restrict sexually
  explicit material, changing its priority for this owner's criteria. Groq large-v3,
  Voxtral Mini Transcribe V2 and Scribe v2 are researched ASR candidates, with no calls
  to those services or integration yet. Gemini's public audio pilot completed one ASR
  call; no private audio was uploaded. [Costs, policy and limits](cloud-speech-and-translation.md).
  Gemini 3.8 and 3.1 Lite each completed 80
  attempts with 79 valid outputs; both blocked the same non-graphic trauma report.
  The new fidelity prompt's nine-case public spot check returned 9/9, including that
  report, but has no contemporaneous control and still softened some wording. It is
  not a new full quality or refusal benchmark.
  2.5 Lite returned 404 twice despite being listed, so it was stopped. The owner-provided
  Gemini authorization key is retained privately in this work environment, never Git.
  [Integration and limits](subtitles.md#optional-gemini-retranslation). Establish runtime
  capacity before downloading any further local weights.
  [Qwen3.5 Q6_K](translation-comparison.md#qwen35-q6_k-comparison--2026-09-07)
  completed 80 cases but is not adopted: 64 matched the response format and several
  Japanese inputs remained Japanese. The qualitative assessment favored MADLAD.
  [contextual Qwen3-4B](translation-comparison.md#contextual-qwen-comparison--2026-09-07)
  completed all 80 inputs but is not adopted: clock-time corruption and changed actions
  remain. The UI now defaults to Gemini for fresh and saved-transcript translation,
  while local MADLAD stays available. Speech recognition remains local. Starting cloud
  work still requires the labeled action; simply opening a video sends nothing.
  [sentence splitting and decoding settings](translation-comparison.md#bounded-decoding-comparison--2026-09-07)
  did not establish a general improvement, so none was adopted. Saved ASR can now be
  reused when translator updates arrive. Preserve the frozen comparison rather than
  treating it as a new holdout. Idioms, register and omissions remain unresolved.
  Target Windows/RTX takes priority on access; natural long speech and useful enhancement
  remain open. Keep all October features included.
  The earlier [16/80 Gemini results](translation-comparison.md#post-payment-diagnosis)
  were reused in the completed comparison. Empty-provider API calls remain local for
  compatibility; UI calls explicitly send the selected provider.
