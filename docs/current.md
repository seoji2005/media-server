# Current work

- **Milestone:** Korean-subtitle/recommendation checkpoint integrated; first conservative
  enhancement feasibility experiment. Target viewing and overall October acceptance
  remain incomplete. No included feature is dropped.
- **Branch:** `app/enhancement-spike`, based on **main `ce6f2b6`**. Owner authorized
  merge of #4 at `e5fa042`; merged main has the identical reviewed tree. #1 is merged;
  #3's HEAD is an ancestor of main and its superseded PR was closed, preserving its
  branch/history. #2 had merged into `harness/initial-workflow`. The new experiment
  will use one Draft PR directly to main; no approval for its final merge is inferred.
- **App:** import/library/original playback/Range/watch-position resume; UTF-8/CP949/
  EUC-KR SRT with original bytes and append-only versions. Explicit regeneration keeps
  previous captions available. Selected-caption text search/seek uses browser memory;
  it does not complete visual/semantic analysis. UI remains awaiting actual playback.
- **Recommendations:** explicit like/dislike/less-of-this plus separate item opt-in.
  New and existing imports default excluded; excluded candidates and feedback do not
  enter scoring. Included unrated titles match included feedback words; no subtitle,
  watch-history or external metadata learning. Up to 12 suggestions, reserving every
  fourth place for unrelated discovery when available. This is literal title matching,
  with acknowledged filename/language/relevance limits, not semantic understanding.
  Pending saves survive same-item reopen; atomic revision checks reject stale writes
  that could undo exclusion. Lost responses require rereading saved state before edits.
  Usage, privacy and limits: [recommendations](recommendations.md).
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
- **Recommendation execution:** production CLI/HTTP on seven generated clips verified
  opt-in defaults, related ranking changes, discovery, exclusion and stale-write 409.
  Forced server kill/restart preserved preference/recommendation responses, position
  1.25 s and byte-identical VTT; seven Range checks exact, source unchanged, log zero
  bytes. No private inputs or model inference; 1.870 s is a functional probe only.
- **Enhancement:** offline SwinIR-S lightweight x2 probe and actual public live-action
  CPU comparisons: 72 frames, all finite, source bytes preserved, about 0.087 fps on
  384×256 input crops. No app integration or adopted preset. The clean close-up improves
  RGB PSNR, but CRF-28 input is slightly worse than ordinary enlargement and visibly
  retains/emphasizes damaged detail. This candidate is not accepted as a general
  video preset. Fresh probe review's source-cache finding was fixed and rechecked;
  boundary and fixed-diagnostic checks passed. Commands, attribution, measurements and
  limitations: [enhancement feasibility](enhancement-spike.md).
- **Verification/review:** full Python **61 passed** (12.593 s), real DB/FFmpeg/process
  coverage. DOM4 flows passed; the new delayed-save/reopen case passed after correction.
  Fresh reviewer found an older save could undo exclusion after same-item reopen at
  local `3475d13`. Fixed pending-write sequencing and atomic revision rejection at
  `a23a93d`; bounded rereview found no remaining actionable findings, independently
  passed eight recommendation tests (3.504 s), DOM, and a simultaneous SQLite write
  conflict check. Published `34463f8` has identical complete tree
  `fb71e31e6467181fe6fb0a98bc1ebfeeb62c5d07`. Prior subtitle/runtime/storage review
  evidence remains valid in unchanged scopes. DOM/review is not real browser playback.
- **Remaining gates:** no target Windows/RTX access here; CUDA/driver/bfloat16/12 GB,
  actual browser decoding/captions/seek/resume and human quality remain unverified.
  Browser localhost previously returned `ERR_BLOCKED_BY_CLIENT`; native ptrace was
  denied. Natural code-switching, long films, long-cue readability and human recommendation
  relevance remain unchecked. Browser presentation of the new controls is not accepted yet.
- **Next:** target Windows/browser ASR→Korean→playback/resume remains the first external
  gate; the enhancement probe can now measure CUDA timing/memory/output on that PC.
  Before adoption, evaluate a compression-aware pixel-loss candidate on the same local
  samples and check real motion/full-size performance on 12 GB. Visual/semantic analysis and enhancement
  remain included October work; do not claim subtitle matching completes them.
  Consequential scope cuts and final merge/release need the owner.
- **Operations:** one Work writes, fresh reviewers only for risky changes. Old developer/
  reviewer event tasks stay paused; the existing daily read-only check is enabled.
  Public package/model/test-audio downloads are authorized; no private cloud inference,
  telemetry permission or private payload egress is added.
