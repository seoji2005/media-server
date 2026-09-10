# Current work

- **Milestone:** owner-directed subtitle integration and minimal companion APIs.
  New application/API jobs use **Qwen3-ASR-1.7B + Qwen3-ForcedAligner-0.6B +
  Gemini 3.1 Flash-Lite**. [Setup and recovery](qwen-subtitles.md).
- **Branch / base:** `feat/qwen-subtitles-integration`, integration base
  `b2bb7b868ac2381d306a1eae4741bd47ad854014`.
  [PR #26](https://github.com/seoji2005/media-server/pull/26) carries the milestone;
  consult its live state, HEAD and checks before writing. One writer;
  [product](product.md) and AGENTS.md govern.
- **Owner authorization, September 10:** the latest instruction requests several
  stages in one turn, followed by review and merge if checks pass. It supersedes
  the earlier one-stage-per-turn limit and pending final-merge approval.

## Implemented

- Bounded all-audio local recognition, separate alignment and durable raw/official
  evidence. Unresolved text remains available without publishing partial captions.
  Schema v9 preserves historical jobs and subtitle versions. Provided foreign
  captions can bypass ASR. Originals and private corrections remain untouched.
- Qwen v2 defers a forced 30-second window's trailing audio at a verified internal
  phrase boundary after at least 20 seconds. Recognition overlaps by at most ten
  seconds; committed spans stay contiguous. Resume verifies the full recognized
  audio hash and evidence, reuses committed work and continues from its saved end.
  No text deduplication removes intentional repetitions. Historical v1 jobs retain
  their original window/evidence rules; whole-audio decode still occurs on resume.
- Gemini requires exact target IDs/counts. New `faithful-context-v5` retains up to
  two verified preceding source/Korean pairs, bounded to 400 characters per field,
  with identical context on resume. Its prompt preserves named cultural references
  instead of substituting Korean analogues. Historical v1–v4 prompts, request shapes,
  identities and checkpoints remain unchanged.
- Explicit `MEDIA_GEMINI_USE_SYSTEM_HTTPS=1` supports the platform's configured
  HTTPS route. Direct remains the default. Official destination, verified TLS,
  no redirects/retries and sanitized failures remain. See setup for the trust choice.
- Safe server logging covers asyncio too. Only the native Windows proactor socket
  shutdown reset is suppressed; unrelated callback failures stay visible with
  sanitized tracebacks and stack information.
- [Companion APIs](companion-library.md): original-identity checked, idempotent
  provided SRT/VTT import, Korean language tags and safe ruby parsing; opt-in
  included-only keyset library pages and bounded lookup. Existing playback, caption
  versions, saved-source retranslation, checkpoints, search and preferences remain.

## Execution and review evidence

- Actual Linux CPU float32 inference used the pinned Qwen models on the same public
  35-second Japanese sample. At local `1105e51fa72d1066b74353e1b7d890c0fde7a3ff`,
  the first 0–30-second recognition committed 0–27.36 seconds. A deliberate
  interruption saved that evidence without translation or a partial track. A new
  process verified/reused it and ran actual ASR/alignment only for 27.36–35 seconds.
  First stage: 67.190 seconds; resume including one real Gemini request: 46.493 seconds.
  Eight source units replace the old nine; the hard `帰っ / 帰って` seam becomes one
  return-home sentence. This is one short sample, not general transcription acceptance.
- That v4 translation introduced a separate error: Japanese Obon became “우리 추석”.
  The failed output is preserved. On the same eight saved source units, v5 at local
  `1ec0416e6549ed92091cbd0693e4fd2bf0fc226c` made one genuine Gemini request,
  completing 8/8 targets in 13.299 seconds without new speech inference. It retained
  “오봉”, consistent casual register and the single return-home sentence. Zero source
  fallbacks; two timing-review indications remain. All five old/new tracks survive.
- Production HTTP routes returned byte-identical final Korean/source VTT before
  and after a server process restart, without inference. Old/new tracks, originals,
  prior jobs and speech evidence remain unchanged. Raw attempts, source/alignment
  evidence and comparison outputs are preserved in the owner's validation bundle.
- Fresh independent review approved the full PR through local `1105e51` (62 focused
  tests plus a 105-second simulated checkpoint/resume exercise), then the logging
  and v5 follow-up through `1ec0416` (22 tests, including interrupted v4 recovery and
  historical request compatibility). The author also passed 49 focused follow-up
  tests, with one Windows-only skip on Linux. Review used no live model/Windows GPU.
- [CI 34445850181](https://github.com/seoji2005/media-server/actions/runs/34445850181)
  at remote `ddfad6a13194216d1457efd496a49e5099dc12b4` passed 221 Python tests and
  seven DOM suites on each OS. Ubuntu browser playback/restart passed; Windows
  failed the quiet-output gate with an asyncio connection-reset traceback. This
  failure prompted the logging fix above, not a same-code rerun. The PR's final
  checks record validation of the corrected tree; require success before merge.
  CI browser media/inference are synthetic, separate from actual model quality.

## Remaining product work

- Validate long-video and multilingual seams, timing and translation quality; check
  actual saved-caption display and subjective readability. The supplied cloud
  browser could connect but local navigation returned `ERR_BLOCKED_BY_CLIENT`;
  standalone Chrome previously failed with socket `EPERM`. No actual-caption
  screenshot/playback was obtained here. Reuse saved outputs for display testing.
- Verify Windows 11 / RTX 4070 SUPER 12 GB model installation, VRAM use, inference
  and recovery. Linux CPU results and Windows synthetic CI do not cover this gate.
- Evaluate and adopt a conservative enhancement preset through actual visual review.
- Fetch/Compass must adopt their contracts and verify their browser flows. Pocket's
  repository/PR returned 404; pack/events await its verified contract. iPhone/LAN
  synchronization is not implemented by the local companion APIs.
- These remaining product gates are separate from the scoped integration merge.
  Preserve failed and successful evidence; do not repeat paid inference merely to
  recheck playback or retune prompts against this one sample.
