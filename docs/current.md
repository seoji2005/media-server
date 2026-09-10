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
- **Real Gemini follow-up, September 10:** resumed the saved-source job through
  the platform's configured HTTPS route: two genuine requests (8 + 1 targets),
  29.712 seconds, all nine Korean units saved, zero source fallbacks. Original
  transcript/times, sample hash and older tracks are unchanged. Product HTTP routes
  returned byte-identical Korean/source VTT before and after a real server process
  restart, with no new inference. Nine translation units yield 11 display cues.
  The two timing-review indications remain; the hard seam still repeats the
  return-home phrase around 30 seconds. This is a short public sample, not a
  general translation-quality acceptance.
- **Network fix:** earlier direct DNS failure was real, but the conclusion that
  Work could not reach Google was incomplete. Earlier experiment scripts already
  used the platform's system HTTPS route. The production client now supports
  explicit `MEDIA_GEMINI_USE_SYSTEM_HTTPS=1`; direct remains the default. Official
  destination, verified TLS, no redirects/retries and sanitized errors remain.
  [Setup](qwen-subtitles.md) explains the trust decision. The failed direct attempt
  is preserved in the evidence; the successful route did not bypass network policy.
- **Checks:** [CI run 34421676924](https://github.com/seoji2005/media-server/actions/runs/34421676924)
  passed on published implementation `fe6b008a8db30e9783255c95901851b6ecac7b1d`:
  209 Python tests on each OS (one Windows-only skip on Ubuntu), all seven DOM
  suites, and actual H.264/AAC browser playback plus server restart on Ubuntu and
  Windows. Browser media/inference were synthetic, not real Gemini/GPU evidence.
  These results predate the system HTTPS change. Independent
  code review approved `3c9bd40dff2e8c67ff82584e313826f68423406a`; the found symbol,
  language-tag and ruby source-loss defects are resolved. The HTTPS change passed
  21 focused tests with opt-in enabled. Independent limited review approved
  `0814a9543e02a8ac937b3ba1f035ec691e7f9b28` after fixing the flag's interference
  with Windows/macOS proxy discovery and isolating the default-route test. Actual
  native OS proxy discovery remains untested. Chrome 153 was installed portably,
  but normal launch failed with socket `EPERM` before page creation; actual new
  translated-caption display is still unverified in this Work runtime.
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
- **Next:** the real translation and saved-output/server-restart part of this stage
  is complete. Reuse the saved Korean/source versions for actual browser display
  verification in a runtime that permits normal browser sockets; do not repeat
  ASR or paid translation. Respect the owner's one-stage-per-turn instruction.
  Final merge remains an owner decision; long-video/RTX and enhancement gates stay
  separate. Preserve both failed and successful evidence.
