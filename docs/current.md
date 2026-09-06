# Current work

- **Milestone:** subtitle runtime/device preflight and clean child-process exit.
  This is a Windows bring-up prerequisite; target Windows/RTX acceptance is still open.
- **Git:** owner-authorized [PR #6](https://github.com/seoji2005/media-server/pull/6)
  HEAD `0753303` merged as **main `4d1f451`**, with the same reviewed tree.
  `app/model-preflight` starts directly from that main. Local code checkpoints
  `bc4a596` → `e2bcd10`; this milestone's Draft PR targets main. Final merge still
  requires the owner; the previous approval was used for #6.
- **App:** local import/library/original playback/Range/persisted watch position;
  append-only UTF-8/CP949/EUC-KR SRT and explicit regeneration that keeps old captions.
  SRT now accepts one-digit hours/position settings, sorts cues, skips empty/outside
  cues and clips at video end, with adjustment counts and exact uploaded bytes retained.
  Size/count/control/timestamp checks stay. SMI/ASS and embedded subtitle extraction
  remain unsupported. Selected-caption text search/seek is literal browser-memory
  matching; it does not complete visual/semantic analysis.
- **New generated presentation:** benchmark-informed 16 weighted characters per line,
  two lines, 834 ms–7 s and adult 12 CPS targets. Translation sentences/checkpoints
  stay intact; a separate stored presentation splits only at word boundaries within
  the original interval. Infeasible bounds/fast text/overlaps are flagged without
  dropping content. Fallback markers follow each split. Old ready VTT never reflows.
  [Rules, commands, actual evidence and limits](subtitle-readability.md).
- **Pipeline retained:** adjacent ASR fragments join within sentence/time/length bounds;
  MADLAD batch two, GPU bfloat16/CPU float32. Known content failures save marked source
  text and continue; runtime failures preserve completed translation batches for resume.
  Commits occur every 20 units or after a batch completes at least five seconds since
  the last save; five seconds is not a hard loss bound during inference. Interrupted
  ASR repeats that stage. Model identity uses metadata/options/packages, not full weight
  scans; FFmpeg reads the verified managed original without another processing copy.
  Pipeline v5 handles numeric Korean units and generated HTML entities. Source/fallback
  text is preserved. Existing job/attempt/OS worker guards remain.
- **Runtime preflight:** session shows the selected default/configured CPU or GPU
  without importing heavy runtimes. **자막 만들기 준비 → 실행 환경 확인** and
  `doctor --models` run an isolated, bounded check. Basic doctor still works without
  optional models. Worker startup checks Torch CUDA, native bf16, CTranslate2 device/
  precision and compatible package imports before ASR. No silent CPU fallback, weight
  loading or media reading in the diagnostic; pipeline/checkpoint identity is unchanged.
  Fixed diagnostics distinguish CPU wheels, missing ASR CUDA/precision and mismatched
  TorchAudio. Ready means basic preflight, not full inference/cuDNN/12 GB certification.
- **Process safety:** diagnostic child retains the existing OS worker lease through
  controlled exit; server supervisor serialization prevents competing inference.
  Timeout kills/reaps the probe and parent EOF ends it. Native output is suppressed;
  status JSON is bounded/validated. Both diagnostic and subtitle worker now watch the
  parent via an unbuffered read, fixing a reproduced Python shutdown abort after
  otherwise successful work. Torch thread counts survive Silero preflight imports.
- **Actual milestone runs:** installed Linux CPU runtime passed doctor in 1.947 s.
  Explicit CUDA with a CPU wheel returned `model_cuda_unavailable` in 1.285 s, keeping
  CUDA selected (placeholder model file layout for that environment-only negative
  check). Real Japanese FLEURS ASR→MT regenerated in 40.91 s with unchanged output VTT,
  source/Range exact, 14 old tracks unchanged after restart and logs zero bytes.
  Repeated short speech only; no expanded quality corpus or long-film evidence.
- **Browser:** actual Linux Chromium 149 showed CPU selection and passed the on-demand
  diagnostic while library requests remained available. Japanese/English H.264/AAC
  playback, two-line native captions, seek, Off/On and 4.25 s resume passed again.
  Screenshots inspected; no page errors/external page requests, server log zero.
  This is headless public black-video speech, not audible/headful/Windows/film acceptance.
- **Verification:** full Python **85 passed** (14.108 s), DOM4 flows passed including
  new device/failure/busy controls. Focused 11 diagnostic tests passed after the fix.
  Fresh review found the lease could release before native teardown; fixed at
  `e2bcd10` with controlled exit under the lease. Bounded rereview found no remaining
  actionable findings. Final actual API probe passed in 1.626 s; an in-process observer
  confirmed no heavy model runtime/ORT was loaded in the server after diagnostics.
  Setup/limits and evidence: [subtitles](subtitles.md#runtime-preflight).
  Previous caption layout/review evidence remains in [readability](subtitle-readability.md).
- **Recommendations retained:** explicit feedback and separate opt-in (default excluded),
  literal title-word matching, up to 12 candidates with unrelated discovery when
  available. No subtitle/watch-history learning or external metadata. Revision guards
  preserve exclusions under stale writes. [Behavior/evidence](recommendations.md).
- **Enhancement retained as unfinished:** public live-action SwinIR-S x2 CPU probe ran
  72 frames (~0.087 fps at 384×256 crop input). Compressed input did not justify adoption;
  no app preset/integration. Next candidate needs compression-aware and motion/full-size
  evaluation plus real 12 GB measurement. [Experiment](enhancement-spike.md).
- **Quality limits:** short ASR/MT has recognition/wording errors; new layout can still
  split a Korean phrase awkwardly and cannot fix excessive reading speed or exact
  word/shot alignment. [Speech checks](speech-quality.md). Long films, natural mixed
  speech, large-file startup latency and human viewing/recommendation relevance remain
  unchecked. Playback integrity is unchanged in this milestone.
- **Next:** target Windows/RTX import→ASR→Korean→browser seek/resume and peak VRAM/
  timing remains the first external gate. Locally, run a permitted 60+ minute speech
  input through the real CPU pipeline and measure time, memory, checkpoint growth and
  recovery. Then implement minimal compatible renditions (remux/audio-only conversion,
  preserving the managed original) and selected-audio consistency. Full HEVC/10-bit
  encoding policy needs owner decision. Enhancement, grounded visual analysis/search
  and Windows launch/recovery remain included; consequential scope cuts/deletion/
  expense require owner decisions. Do not substitute repeated short probes for the
  long-input or target-hardware gate.
- **Operations:** one Work writes; fresh reviewers only for risky changes. Existing
  daily read-only check remains enabled; obsolete cross-Work loops stay paused. Public
  package/model/test-audio downloads are authorized; private cloud inference/telemetry
  or private payload egress is not. No video downloading/generation/NAS product features.
