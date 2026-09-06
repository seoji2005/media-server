# Current work

- **Milestone:** Korean-subtitle viewing and resumable preparation — in progress.
  The public multilingual CPU execution/correction checkpoint is complete; target
  viewing and overall October acceptance are not. No included feature is dropped.
- **Branch:** `app/korean-subtitles-resume`, Draft PR #4 targets **main** directly.
  Main was confirmed an ancestor; this integration candidate includes #1/#3 changes.
  Their branches/PRs remain preserved; #2 had merged into `harness/initial-workflow`.
  No final merge. Read live coordinates before continuing. Implementation: `5ea410c`.
- **App:** import/library/original playback/Range/watch-position resume; UTF-8/CP949/
  EUC-KR SRT with original bytes and append-only versions. Explicit regeneration keeps
  previous captions available. Selected-caption text search/seek uses browser memory;
  it does not complete visual/semantic analysis. UI remains awaiting actual playback.
- **Pipeline:** source ASR and Korean translation are separate. Adjacent fragments join
  within sentence/time/length bounds, preserving their outer interval. MADLAD batch two,
  CUDA bfloat16/CPU float32; known content failures save marked source text and continue.
  Runtime errors preserve completed batches for resume. Append commits every 20 units
  or five seconds at batch boundaries; existing job/attempt/OS worker guards stay.
  Model identity checks metadata/packages/options, without full weight scans. FFmpeg
  reads the verified managed original directly; no extra processing video copy.
- **Observed fixes:** actual Korean speech produced `15m`, causing needless MT. Explicit
  numeric units no longer disqualify otherwise Hangul-only text. Actual MADLAD emitted
  literal HTML entities; generated output now decodes once before validation and safe
  VTT escaping. Source/fallback strings stay intact. Pipeline v5 rejects unfinished old
  results; restart creates a new job while preserving old checkpoints/ready versions.
- **Runtime:** Silero v6 bundled TorchScript VAD on CPU, original-time speech clips and
  restored Torch threads. ORT preloading is refused and future imports blocked. Blanket
  Windows refusal is removed, but no Windows/RTX execution has occurred. Install matching
  Torch/TorchAudio from the same CPU/CUDA wheel index. Setup: [subtitles](subtitles.md).
- **Actual execution:** Linux CPU/Python 3.12.13, large-v3 + MADLAD. Seven public FLEURS
  Japanese/English/Korean and concatenated language cases completed. Two corrected cases
  reran: Korean 49.51→23.20 s with exact ASR pass-through; mixed 81.36→79.98 s with entity
  syntax removed. These are individual short runs, not speed/quality benchmarks.
  After server restart all nine old/new tracks and transcripts were unchanged, VTT
  byte-identical, Range exact and source hashes preserved; server logs zero bytes.
  Japanese word/proper-name errors, an omitted English connector and awkward MT remain.
  CPU float32 ASR repeated two int8 errors, so production precision stayed unchanged.
  Attribution, all cases, corrections and limits: [speech quality](speech-quality.md).
- **Earlier valid evidence:** actual 48-second CPU speech/gap pipeline at `67f5e8e`
  paused after 2/3 units and resumed only the final unit across forced server restart;
  transcript/batches and 5.25 s watch position persisted. Prior JIT/ONNX VAD boundaries
  matched; standalone ORT modules/native mappings absent, Python connect audit zero.
  These observations are not native packet tracing or Windows proof. Details and
  earlier scale/model setup evidence remain in [subtitles](subtitles.md).
- **Verification/review:** full Python **53 passed** (10.141 s), real DB/FFmpeg/process
  coverage. New regressions cover numeric foreign-word boundaries, generated markup,
  single decoding and exact saved content after failure/resume. Fresh reviewer found no
  actionable findings and independently passed 28 subtitle tests (4.154 s) at local
  `9b7d469`; published `5ea410c` has the identical complete tree
  `f56413f637730d536695035b89b4c723d51d59ee`. Previous DOM3/runtime/storage reviews remain
  valid in unchanged scopes; neither DOM nor this review establishes playback quality.
- **Remaining gates:** no target Windows/RTX access here; CUDA/driver/bfloat16/12 GB,
  actual browser decoding/captions/seek/resume and human quality remain unverified.
  Browser localhost previously returned `ERR_BLOCKED_BY_CLIENT`; native ptrace was
  denied. Natural code-switching, long films and long-cue readability remain unchecked.
- **Next:** target Windows/browser ASR→Korean→playback/resume remains the first external
  gate; measure a conservative non-generative enhancement candidate on 12 GB before
  adoption. While access is absent, the next independent product slice is basic local
  recommendations from explicit feedback. Visual/semantic analysis and enhancement
  remain included October work; do not claim subtitle matching completes them.
  Consequential scope cuts and final merge/release need the owner.
- **Operations:** one Work writes, fresh reviewers only for risky changes. Old developer/
  reviewer event tasks stay paused; the existing daily read-only check is enabled.
  Public package/model/test-audio downloads are authorized; no private cloud inference,
  telemetry permission or private payload egress is added.
