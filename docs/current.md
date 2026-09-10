# Current work

- **Milestone:** bounded audio memory for long Qwen subtitle jobs.
- **Branch / base:** `perf/qwen-bounded-audio`, main
  `8da6fb4a506429bc7ef4db011aac69b962c2a4fe`.
  [PR #26](https://github.com/seoji2005/media-server/pull/26) is merged. Resolve the
  live [PRs](https://github.com/seoji2005/media-server/pulls), HEAD and checks before
  writing; one writer, AGENTS.md and [product](product.md) govern.
- **Authorization:** the owner's latest instruction requests multiple stages,
  review and merge after successful checks. Continue that scope; do not reinstate
  the obsolete one-stage-per-turn or pending-merge-approval limits.

## Current change and evidence

- Qwen's whole-video PCM used to be collected as a bytearray and copied into bytes.
  It now decodes to a private, automatically removed temporary file beside the owned
  input. Each recognition window reads at most 1,920,004 bytes, including one sample
  of lookahead. Existing v1/v2 segmentation, timestamps, raw evidence, profile and
  model identities remain unchanged. Decoder diagnostics remain suppressed.
- Disk usage is bounded by the existing decoded-output cap plus one FFmpeg packet;
  output over the cap is rejected. Two hours need about 440 MiB of temporary disk
  plus 32 MiB reserve. Timeout, decode error, disk exhaustion and generator close
  release the file. Original media and existing caption versions are untouched.
  Resume still decodes all audio before verifying saved spans; no persistent PCM
  cache or target-device inference speedup is claimed.
- [Measured comparison](evidence/qwen_audio_memory.json), local
  `3af74e9e86ae4b0a692afc17f18cb1ddb8e1eac5`: a two-hour synthetic H.264/AAC input
  passed real FFmpeg decode with deterministic ASR/alignment stubs. Parent peak RSS
  fell from 910.172 to 39.383 MiB (95.67%); 326 spans and their evidence hashes were
  identical. This excludes model memory, child FFmpeg and filesystem cache.
- A separate process resumed 150 saved spans at 55:15, executing only the remaining
  176 stub recognition calls and ending at 2:00:00 with the identical result hash.
  The actual SQLite job flow also resumed to 326 spans and 327 translated units,
  publishing one synthetic track. No translation or partial track preceded the
  deliberate interruption. Production HTTP returned unchanged VTT and end-of-file
  Range bytes before/after server restart; originals and saved data were preserved.
- Both versions of the prior **actual Qwen** 35-second public sample revalidated
  their entire recognition-audio hashes and saved evidence through the new decoder
  with zero model calls. This verifies compatibility, not new transcription quality.
- Author and fresh reviewer each passed 36 focused tests on Linux. The reviewer
  approved code `3af74e9`, independently comparing 97 initial/resume cases across
  both profiles, including 13 handoffs and nine quiet cuts. Real FFmpeg tests cover
  AAC/AC3 track selection, delayed timing, size limits, timeouts, low disk and close,
  failure/abrupt-exit cleanup. Windows native behavior requires final PR CI success.
  Subsequent edits are documentation/evidence only. Keep final CI/merge facts in
  the live PR and preserve raw attempts in the owner's validation bundle.

## Existing integration

- New jobs remain **Qwen3-ASR-1.7B + Qwen3-ForcedAligner-0.6B + Gemini 3.1 Flash-Lite**.
  [Setup and recovery](qwen-subtitles.md). Qwen v2's aligned phrase handoff resolved
  the hard seam in the short public sample. Gemini faithful-context-v5 preserved
  Obon and consistent register there. Historical jobs/profiles and all five sample
  subtitle versions remain intact; no general quality acceptance is implied.
- Saved-source translation, original/source caption switching, scene search and
  opt-in recommendations remain. [Companion APIs](companion-library.md) support
  provided captions, original identity, idempotent receipts and bounded lookup.
- PR #26 passed [CI 34447808585](https://github.com/seoji2005/media-server/actions/runs/34447808585):
  224 Python tests per OS (one Windows-only skip on Ubuntu), seven DOM suites,
  actual synthetic-media Chrome playback and restart on Ubuntu/Windows. Its earlier
  Windows log and timestamp-fixture failures and fixes remain in Git/PR evidence.

## Remaining product gates

- Natural long-video/multilingual transcription, alignment and translation quality,
  plus subjective caption timing/readability. The two-hour resource test uses model
  stubs and must not be called a long-video model-quality pass.
- Windows 11 / RTX 4070 SUPER 12 GB installation, VRAM, actual inference and recovery.
  Linux CPU history and Windows synthetic CI do not establish this gate.
- Actual saved-caption screen review remains blocked here: the supplied browser's
  local navigation returned `ERR_BLOCKED_BY_CLIENT`, and standalone Chrome previously
  failed with socket `EPERM`. Reuse saved outputs when a reachable runtime is available.
- Conservative enhancement still requires actual visual comparison and adoption.
  Fetch/Compass must adopt their contracts; Pocket requires a verified accessible
  contract. iPhone/LAN synchronization is separate from these local APIs.
