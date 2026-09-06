# Current work

- **Milestone:** compatible playback renditions with original preservation, retry and
  legacy-library first-use preparation. Complete as a Draft PR checkpoint; Windows/RTX
  and long-input acceptance remain open.
- **Git:** owner-authorized [PR #7](https://github.com/seoji2005/media-server/pull/7)
  HEAD `30401e8` merged as **main `4a8c20a`**, same reviewed tree. New branch
  `app/compatible-renditions` starts directly from that main. Code checkpoints
  `1bd373c` → `4923206` → `f0f03ff`; this milestone's Draft PR targets main.
  The current merge approval was used for #7; the new PR needs owner merge approval.
- **New playback:** H.264 MKV remux to MP4 without video encoding; first unsupported
  audio (including AC3/EAC3/DTS/FLAC) becomes AAC 192 kbit/s stereo. AAC/MP3 is copied.
  Supported multi-audio MP4/MKV/WebM retain the first audio in the derivative, matching
  ASR selection. Player labels this policy; alternate-audio selection UI is still pending.
  HEVC/unsupported depth/chroma get distinct messages and no video transcoding.
- **Preservation/recovery:** original import commits first; browser and CLI then prepare
  a separate ID/SHA/duration rendition. Failure keeps the managed original and exposes
  retry on its card. Ready derivatives are not overwritten. Existing byte-integrity,
  local-origin/token/logging boundaries remain. Interrupted FFmpeg conversion starts
  again; unregistered copies go to recovery on restart. Existing subtitle resume is
  unchanged. Legacy formats are classified on first selection, preserving item IDs,
  watch history and subtitle rows. [Behavior and limits](compatible-renditions.md).
- **Verification:** full Python **95 passed** (21.672 s) at `4923206`; after the final
  position-bound fix, rendition **10 passed** (6.136 s) and app **25 passed** (4.758 s).
  Four DOM flows passed, including failed preparation/retry. Real FFmpeg regressions
  cover remux essence, AC3/AAC, first/default/unequal-length audio, source and Range
  identity, no-space/timeout/validation retry, actual process exit before commit,
  migration/history/caption preservation, HEVC/10-bit refusal and playable-end saving.
- **Review:** fresh read-only reviewer reproduced discarded-longer-audio rejection and
  legacy selection bypass; both fixed. Follow-up found original-versus-rendition end
  position mismatch; fixed at `f0f03ff`. Bounded final review found no remaining
  actionable findings and independently passed the two affected real-FFmpeg tests.
- **Actual model/browser:** public Japanese FLEURS 10.44 s speech in synthetic moving
  H.264/AC3 MKV imported/prepared in **0.885 s**; real CPU Whisper→MADLAD finished in
  **43.422 s**. Source bytes and 15 old tracks survived; derived Range exact and logs
  zero. Chromium **149.0.7827.0** decoded video/audio, displayed native Korean captions,
  supported Off/On, seek and **4.25 s** resume. Separate browser upload automatically
  remuxed AAC MKV and displayed imported captions. Server restart returned identical VTT.
  After review fixes, an actual legacy dual-audio case with a longer omitted stream
  prepared on click, used **10.496 s** playback, restored **4.253 s** and kept its subtitle
  row byte-identical. Final native ended event saved **10.496 s** successfully. Page
  errors/external page requests and app log bytes were zero in successful probes.
  This is short Linux headless evidence, not Windows/RTX, long-film or human listening.
- **Long-input block:** planned non-repeated 60+ minute CPU processing/time/memory/
  recovery run did not start. Public-domain film metadata was reachable, but download
  returned `network approval was cancelled before a decision was returned`. No suitable
  local long input exists. No network control bypass or fake repeated-speech substitute.
  [Details](compatible-renditions.md#long-input-gate-remains-blocked).
- **Subtitle/runtime retained:** sentence MT, batch two, GPU native bf16/CPU float32,
  marked source fallback for known content failures, append-only versions and separate
  presentation. UTF-8/CP949/EUC-KR SRT adjustments preserve exact uploaded bytes. New
  generated display targets 16 weighted characters/two lines, 834 ms–7 s and adult
  12 CPS; infeasible bounds are flagged, old VTT never reflows. [Readability](subtitle-readability.md).
  Translation checkpoints every 20 units or after a completed batch at least five
  seconds since save; no hard five-second inference loss bound. Interrupted ASR repeats
  its stage. Metadata-based model identity, direct managed-original decode and existing
  job/attempt/OS leases remain. [Pipeline/runtime diagnostics](subtitles.md).
- **App retained:** local import/library, verified Range playback, persisted watch
  position, subtitle generation/regeneration/pause/resume and selected-caption literal
  text search/seek. Explicit device preflight remains isolated/bounded with no silent
  CPU fallback, full weight loads or media input. It does not certify cuDNN/12 GB fit.
  SMI/ASS, embedded subtitle extraction and true word/shot alignment remain unfinished.
- **Other October scope:** [recommendations](recommendations.md) retain explicit
  opt-in/feedback and title-word matching; no watch/subtitle learning or external lookup.
  [Enhancement](enhancement-spike.md) is unfinished: SwinIR-S compressed live-action
  results did not justify adoption; no app preset yet. Grounded visual/semantic scene
  analysis is also unfinished; subtitle matching does not complete it. No silent cuts.
- **Next:** unblock permitted long-input acquisition, then real 60+ minute CPU ASR/MT,
  peak memory, checkpoint growth and interrupted recovery. Target Windows 11/RTX 4070
  SUPER 12 GB import→playback→ASR/Korean→seek/resume with timing/VRAM remains the first
  hardware gate. Windows launch/setup/recovery, enhancement candidate/integration and
  grounded visual search stay pending. HEVC video encoding policy, scope cuts, deletion
  and spending need owner decisions.
- **Operations:** one Work implements; fresh reviewers only for risky changes. Existing
  daily read-only check remains enabled; obsolete cross-Work loops stay paused. Public
  package/model/test downloads are authorized, subject to actual environment access.
  No private egress, cloud inference, telemetry or video downloading/generation/NAS features.
