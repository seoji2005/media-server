# Current work

- **Milestone:** Korean-subtitle viewing and resumable preparation — in progress.
  Original import/library/playback/resume is preserved. No October feature is dropped.
- **Branch:** `app/korean-subtitles-resume`, Draft PR #4 now targets **main** directly.
  Live comparison confirmed main is an ancestor. This single integration candidate
  includes the unmerged #1/#3 changes; their branches/PRs are preserved. PR #2 was
  already merged into `harness/initial-workflow`. No final merge was performed.
  Read live coordinates before continuing. Latest implementation: `f2a3ba3`.
- **Implemented:** strict UTF-8/CP949/EUC-KR SRT import with original bytes and previous
  caption versions preserved. Explicit new-version generation remains available after
  SRT import. Native subtitle selection and selected-caption text search/seek are ready
  for browser evaluation; search stays in browser memory and clears on player close.
- **Pipeline correction:** adjacent source fragments join within sentence/time/length
  bounds and retain their combined interval. MADLAD batches two units, uses CUDA
  bfloat16/CPU float32, and passes pure Hangul units through. Known content failures
  preserve source text with saved warnings and visible `[원문]`; runtime failures
  retain completed results for resume. New batches append every 20 units or after
  five seconds at a batch boundary. Job/attempt and OS worker guards remain unchanged.
  Model identity uses file metadata/packages/options, not full weight byte scans.
  FFmpeg reads the verified managed original directly; no extra processing video copy.
  Old ready tracks remain readable; the new pipeline requires restarting old unfinished
  jobs, preserving their prior checkpoints and caption versions.
- **Actual model evidence:** at `f2a3ba3`, public 11-second English speech repeated three
  times in a synthetic MP4 completed actual CPU ASR/three Korean cues in **133.10 s**,
  including pause and forced server restarts. Paused at 2/3, preserved batch bytes and
  transcript hash, resumed only the last unit as attempt two. Previous/new ready VTTs
  survived restart unchanged; watch position 5.25 s restored; Range exact, source hash
  unchanged, server log zero bytes. Short author-written English/Japanese fragment
  pairs also ran through real MADLAD: joined Japanese retained the conditional meaning;
  English still sounded literal. These are limited CPU results, not broad quality proof.
- **Verification:** full Python **47 tests passed** (8.557 s); three mocked DOM/media/HTTP
  suites passed; harness/diff checks passed. Synthetic bookkeeping for 250/500/1,000/
  2,000/4,000 units took 0.014/0.021/0.038/0.091/0.148 s; stored bytes grow by appended
  batch, not rewritten prefixes. These are Linux measurements, not Windows disk timings.
  Actual metadata identity took 71.52 ms. Details and limits: [subtitles](subtitles.md).
- **Independent review:** fresh reviewer inspected the seven-file implementation diff
  at local `ff9bf86` against `c95a039`: no actionable findings; independently passed
  22 subtitle tests and subtitle DOM test. Published `f2a3ba3` has exactly the same
  complete tree (`f3cdbd5a66383e929a4a18348875b19138b8e1bd`). Subsequent changes are
  documentation only. Earlier scene-search/privacy reviews remain valid in unchanged scope.
- **Remaining blockers:** Windows inference fails closed before queueing/import because
  official ORT wheels may emit initialization ETW before the disable API. Linux forces
  ORT's pre-init disable flag and API. Public download authorization does not authorize
  telemetry/private egress. The original telemetry connection was rejected by automatic
  approval review; the corrected Linux adapter ran. No safe Windows runtime is verified.
  Browser localhost remains `ERR_BLOCKED_BY_CLIENT`; native network tracing was denied
  (`ptrace`). Actual browser playback/readability/seek, Windows/CUDA bfloat16/12 GB fit,
  Japanese/mixed speech, long videos and human quality remain unverified.
- **Next:** remove the Windows runtime blocker using a verified telemetry-free runtime
  and obtain target/browser ASR→Korean captions→seek/resume evidence. Then measure a
  conservative non-generative enhancement candidate on 12 GB before adoption. Subtitle
  text search is implemented; visual/semantic analysis and explicit-feedback recommendations
  remain unfinished October scope. Do not silently treat text search as full scene analysis
  or claim a scope cut; any consequential narrowing/final merge requires the owner.
- **Operations:** one Work writes; fresh reviewers only for risky changes. Old development/
  reviewer event tasks remain paused; the existing daily read-only check is enabled.
  Public package/model downloads are authorized. No private cloud inference or payloads.
