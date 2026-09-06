# Current work

- **Milestone:** Korean-subtitle viewing and resumable preparation — in progress.
  Original import/library/playback/resume is preserved. No October feature is dropped.
- **Branch:** `app/korean-subtitles-resume`, Draft PR #4 now targets **main** directly.
  Live comparison confirmed main is an ancestor. This single integration candidate
  includes the unmerged #1/#3 changes; their branches/PRs are preserved. PR #2 was
  already merged into `harness/initial-workflow`. No final merge was performed.
  Read live coordinates before continuing. Latest implementation: `67f5e8e`.
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
- **Windows blocker correction:** Silero v6 VAD now runs its official bundled
  TorchScript model on CPU with the previous detection settings. Speech clips retain
  original waveform time offsets. The app rejects preloaded ORT and blocks subsequent
  imports, avoiding the initialization path entirely. Blanket Windows refusal is removed;
  this is not a claim that Windows/RTX setup or inference has run. Matching Torch and
  TorchAudio CPU/CUDA wheels are installed together. No permission for telemetry or
  private egress is added. Silence returns no speech before loading Whisper.
- **Actual model evidence:** `67f5e8e`, Linux CPU/Python 3.12.13. A 33-second public
  speech/gap fixture produced exactly the old ONNX VAD boundaries using JIT (0.555 s).
  Silence yielded no clips, four Torch threads restored, ORT absent from modules/native
  mappings, Python socket-connect audit recorded zero attempts. This does not prove
  native zero-packet operation or Windows behavior.
  The production CLI/HTTP ASR→Korean pipeline completed a 48-second speech/gap fixture
  in **95.93 s**, including pause/restarts. Paused at 2/3 and resumed only the last unit
  as attempt two, with saved transcript/batches unchanged. Cue starts 3.920/19.120/34.160 s
  retained the gaps; ready VTT survived restart byte-identically; watch position 5.25 s
  restored, Range exact, source unchanged, server log zero bytes. The initial external
  child-mapping observer failed on PID/procfs mismatch; that job was preserved/restarted.
- **Verification:** full Python **50 tests passed** (8.542 s), including real SQLite,
  FFmpeg and process interruption. Earlier DOM3 evidence remains valid for unchanged
  flows; this UI diff only changes the runtime diagnostic message. Setup `pip check`
  passed. Earlier append-checkpoint scale and supplied-version preservation evidence
  remains valid. Exact setup/measurements and limits: [subtitles](subtitles.md).
- **Independent review:** fresh reviewer checked the four-file runtime change at local
  `c19ff68` against `ba7a0b7`, independently passed 25 subtitle tests and real JIT silence
  with ORT absent. Found matching Torch/TorchAudio wheel setup omission; both CPU/CUDA
  instructions now install them together. No other actionable code findings. Published
  `67f5e8e` has the identical complete tree `c6c0ff038d1098461dff614d8b0cb3041832ea00`.
  Later changes are docs only; earlier storage/resume/search reviews remain valid.
- **Remaining:** no target Windows/RTX machine access here. CUDA libraries/drivers,
  bfloat16/12 GB fit, actual browser playback/readability/seek/resume, Japanese/mixed
  speech, long videos and human quality are unverified. Browser localhost was
  `ERR_BLOCKED_BY_CLIENT`; native tracing via ptrace was denied. Previous real English
  translation still has literal phrasing. Do not call these quality gates complete.
- **Next:** execute the documented Windows setup and actual target/browser
  ASR→Korean captions→seek/resume; diagnose CUDA loading/memory from those results.
  Continue feasible Japanese/mixed-speech CPU checks while target access is absent.
  Then measure a conservative non-generative enhancement candidate on 12 GB before
  adoption. Text search exists; visual/semantic analysis and explicit-feedback
  recommendations remain October scope. Consequential scope cuts/final merge require
  the owner. Do not wait for target access to implement independent product work.
- **Operations:** one Work writes; fresh reviewers only for risky changes. Old development/
  reviewer event tasks remain paused; the existing daily read-only check is enabled.
  Public package/model downloads are authorized. No private cloud inference or payloads.
