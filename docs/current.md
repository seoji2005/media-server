# Current work

- **Milestone:** September 9 owner-directed subtitle integration and minimal companion
  APIs. New application/API jobs use **Qwen3-ASR-1.7B + Qwen3-ForcedAligner-0.6B +
  Gemini 3.1 Flash-Lite**. [Setup and recovery](qwen-subtitles.md).
- **Branch / base:** `feat/qwen-subtitles-integration`, main
  `b2bb7b868ac2381d306a1eae4741bd47ad854014` (PR #25 merged).
  [Draft PR #26](https://github.com/seoji2005/media-server/pull/26) was published
  after the owner's September 10 approval. Its published implementation commit is
  `fe6b008a8db30e9783255c95901851b6ecac7b1d`, whose tree matches local `4cd6d80`.
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
- **Real Gemini follow-up, September 10:** the owner supplied a key and authorized
  use. A new saved-source retranslation job verified and reused all nine actual
  Qwen phrases. The first eight-target request failed before reaching Google:
  endpoint DNS returned `EAI_AGAIN` / temporary name-resolution failure. A separate
  no-key connectivity check reproduced that failure; the environment rejected
  network permission escalation. Zero translated units or new tracks were
  published. The previous tracks, source transcript and original sample hash are
  unchanged. Key validity remains untested; this is not an authentication failure.
- **Checks:** [CI run 34421676924](https://github.com/seoji2005/media-server/actions/runs/34421676924)
  passed on published implementation `fe6b008a8db30e9783255c95901851b6ecac7b1d`:
  209 Python tests on each OS (one Windows-only skip on Ubuntu), all seven DOM
  suites, and actual H.264/AAC browser playback plus server restart on Ubuntu and
  Windows. Browser media/inference were synthetic, not real Gemini/GPU evidence.
  These results predate this documentation-only checkpoint. Independent
  code review approved `3c9bd40dff2e8c67ff82584e313826f68423406a`; the found symbol,
  language-tag and ruby source-loss defects are resolved. The current Work runtime
  still lacks a browser executable, so real translated-caption display has not
  been checked here. No product code changed for the failed cloud attempt.
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
- **Next:** finish this one stage when an authorized runtime can reach the official
  Gemini endpoint: resume the failed saved-source retranslation, verify the new
  Korean version and source/timing preservation, then check display and restart in
  an actual browser. Do not ask again for key-use approval or repeat ASR. Preserve
  the failed attempt and stop after this stage, as the owner requested. Final merge
  remains an owner decision; long-video/RTX and enhancement gates stay separate.
