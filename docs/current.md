# Current work

- **Milestone:** September 9 owner-directed subtitle integration and minimal companion
  APIs. New application/API jobs use **Qwen3-ASR-1.7B + Qwen3-ForcedAligner-0.6B +
  Gemini 3.1 Flash-Lite**. [Setup and recovery](qwen-subtitles.md).
- **Branch / base:** `feat/qwen-subtitles-integration`, main
  `b2bb7b868ac2381d306a1eae4741bd47ad854014` (PR #25 merged; no open PR at handoff).
  Resolve live [PRs](https://github.com/seoji2005/media-server/pulls) before writing.
  One writer; [product](product.md) and AGENTS.md govern.
- **Changed:** all-audio bounded local recognition followed by separate alignment;
  source/punctuation-preserving phrase construction; raw and official time evidence;
  unresolved text preserved without publishing partial captions; exact Gemini target
  count/IDs with historical request profiles retained. New schema v9 preserves old
  jobs and subtitle versions. Provided foreign captions can bypass ASR entirely.
- **Companion support:** [provided SRT/VTT with identity, language and idempotent
  receipts; opt-in keyset pages and bounded lookup](companion-library.md). Existing
  endpoints and original playback remain. Fetch and Compass must adopt these APIs
  and verify their own browser flows; no companion repository changed here.
- **Actual evidence:** [35-second Qwen adapter/job execution](evidence/qwen_product_integration.json)
  on Linux CPU float32. First pass stopped after an official timestamp overshot a
  5-second window by 40 ms. After the bounded final-tick fix, the first 30-second
  actual output was reused by exact decoded-audio hash and the last 5 seconds reran
  through real ASR/alignment. Nine translation units were saved through synthetic
  Gemini transport. No actual Gemini translation-quality claim; the failed first
  result is retained. The hard window seam remains flagged.
- **Checks:** implementation snapshot `b69af8e` ran 204 Python tests (one
  Windows-only skip) and passed all seven DOM suites. Review corrections passed
  55 focused tests; the final ruby correction passed all seven companion-subtitle
  tests. Native-tokenizer adapter probes passed 24 expected outcomes. Independent
  code review approved `3c9bd40dff2e8c67ff82584e313826f68423406a`; the found symbol,
  language-tag and ruby source-loss defects are resolved. These are Linux checks,
  not model-quality evidence. Actual server startup succeeded; browser smoke could
  not launch because Chrome is absent. No new GitHub CI result is available.
- **Publication blocked:** automatic approval review rejected GitHub writes because
  publishing to `seoji2005/media-server` lacks explicit destination approval. The
  connected account owns this private repository with write access, but that check
  did not clear the block. No remote branch, PR or main change was made. Local
  commits and the proposed Draft PR are ready for owner approval to publish.
- **Existing functionality retained:** import/compatible copies; selected audio;
  playback/seek/restart; old supplied/generated caption versions; saved-source
  retranslation; speech/translation checkpoints; literal/visual scene search,
  previews, explicit preferences and companion moment entry. Historical evidence
  stays in Git and the linked feature documents; don't repeat model comparisons.
- **Unfinished product gates:** natural long-video quality, Windows 11/RTX 4070 SUPER
  12 GB inference and installation, subjective Korean/timing quality, and adoption
  of a conservative enhancement preset. None is declared complete by these changes.
  Whole-audio decode remains on speech resume; only model work is bounded/reused.
  Pocket's repository/PR returned 404, so pack/events integration awaits its verified
  contract. iPhone/LAN synchronization is not implemented by these local APIs.
- **Next:** after explicit publication approval, upload the reviewed branch and open
  its Draft PR, then inspect Linux/Windows CI. Final merge remains an owner decision.
  Reuse actual results and preserve failures; target-device and enhancement decisions
  require their own evidence, without restarting model comparisons.
