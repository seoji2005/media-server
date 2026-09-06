# Current work

- **Milestone:** generated Korean subtitle readability and compatible SRT import.
  This completes an incremental caption milestone, not October product acceptance.
- **Git:** `app/readable-subtitles` is based directly on **main `4e6e447`**, the merged
  [PR #5](https://github.com/seoji2005/media-server/pull/5). Local reviewed code checkpoint `9cb9882`.
  Earlier stack work is integrated; no new stacked base. This milestone’s Draft PR
  targets main; final merge/release still needs the owner.
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
- **Runtime:** local Silero v6 TorchScript VAD, no ONNX Runtime loading. Windows blanket
  refusal was removed, but Windows/CUDA/bfloat16/12 GB remains untested. Windows still
  defaults to CUDA without complete availability preflight. Setup and earlier actual
  forced-stop/resume evidence: [subtitles](subtitles.md).
- **Actual milestone runs:** two existing public FLEURS Japanese/English samples fully
  regenerated with real CPU ASR/MT in 44.34/45.69 seconds, two display cues each. No
  source fallback; source hashes/Range exact, 12 preexisting tracks unchanged on restart,
  logs zero bytes. This repeats short speech, not a long-film or expanded-corpus result.
- **First real browser playback:** Linux headless Chromium 149 decoded H.264/AAC,
  advanced playback, rendered Korean native captions, sought through both cues, switched
  captions Off/On and restored 4.25 s after player close/page reload. Actual screenshots
  inspected. No page errors/external page requests; server log zero. Public black-video
  speech fixtures only: no audible/headful/Windows/fullscreen/real-film acceptance.
- **Verification:** Python **74 passed** (13.050 s), DOM4 flows passed. Fresh review found
  an overlap publication/retry failure and repeated-empty-SRT separator rejection;
  fixed at `9cb9882`, bounded rereview found no remaining actionable findings and
  independently passed 41 subtitle tests plus focused overlap/separator probes.
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
- **Next implementation:** Windows device/runtime diagnostics before first target run
  (actual CUDA/CTranslate2/bfloat16 availability, selected device and actionable setup
  errors). Target import→ASR→Korean→browser seek/resume and peak VRAM/timing is still the
  first external gate. Then minimal compatible renditions (remux/audio-only conversion,
  preserving the managed original) and selected-audio consistency; full HEVC/10-bit
  encoding policy needs owner decision. Run a permitted long speech video as a separate
  scale gate. Enhancement, grounded visual analysis/search and Windows launch/recovery
  remain included; consequential scope cuts/deletion/expense require owner decisions.
- **Operations:** one Work writes; fresh reviewers only for risky changes. Existing
  daily read-only check remains enabled; obsolete cross-Work loops stay paused. Public
  package/model/test-audio downloads are authorized; private cloud inference/telemetry
  or private payload egress is not. No video downloading/generation/NAS product features.
