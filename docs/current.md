# Current work

Live recovery base: Server `a66e9501d37dec66c7dfa6153c78c54b55ed6c8a`
(PR47 merged); Fetch `0d6aa28a4a0c6944c053e3d63e150908b44b9175`.
Both repositories had no open PR at recovery on September 12. PR47 final CI34678497176
and merge-main CI34678728658 succeeded on Windows Server 2025 and Ubuntu 24.04.
PR46 session-key launch and PR45 timing-warning correction are also merged.
Git/PR state is authoritative; historical failed revisions and reviews remain in Git
and preserved evidence. Synthetic CI is not model, viewing or target-device acceptance.
Existing cost/allowed-public-egress and reviewed, passing-CI development-merge
approvals persist. Release and subjective quality acceptance remain separate.

## October order

The owner wants to use the app on October 19. Target October 5 for integration,
October 11 for stabilization and October 12–18 for buffer; these are targets,
not guarantees. Prioritize the actual subtitle path and viewing quality, Windows
setup/everyday launch, real Fetch download to exact-video playback, 40–120-minute
interruption/recovery, then enhancement, search/recommendations and target viewing.
Preserve original media, completed results and all user corrections.

## Actual product and quality evidence

The current Work installed the repository runtime (Torch 2.8.0+cpu, Transformers
5.16.1 and requirements) and connected to Gemini 3.8 Flash with bounded official
PyPI/CPU/API checks and zero retries. Newer separately downloaded wheels were not
adopted. Only the Gemini key from the owner's saved environment file was injected;
keys never entered logs, reports or Git. All saved model archives, members and full
weight hashes were verified. No old trial DB was found, so the trial was a new run.

Unchanged PR44 main `7fde01e4274930a97a4e2c2405b0fe8deb456294` completed the actual
HTTP import/job path on public dialogue03, 762.048 seconds, with verified WAV/EAF
hashes and a byte-identical PCM Matroska wrapper. Qwen3-ASR-1.7B →
Qwen3-ForcedAligner-0.6B → Gemini 3.8 Flash kept the current profile and v5 prompt:
28 spans, 20 saved translation batches, 154 translated units and 208 display cues;
supervisor elapsed 1680.93 seconds. Speech limits were 2700/300 seconds and
translation 600/120 seconds (total/committed-output idle), zero automatic retries.
Consistent SQLite backups and the final checkpoint were saved throughout.

Output hashes, span continuity, cue validity and DB integrity passed. Actual HTTP
served Japanese/Korean VTT and prepared MP4; three byte ranges returned 206. A
same-process server/client check verified saved position, caption selection and
offset after restart and restored its viewing choices. Its two retained server
processes exited with -15. The original trial's psutil namespace mismatch means
its empty survivor report cannot prove every model/FFmpeg child exited. A corrected
future supervisor was prepared separately; it does not replace historical evidence.

Quality remains unaccepted. Around 138–167 seconds 千歩 became 店舗 and produced a
false shop story. Around 197–225 seconds overlapping turns lost the one-hour walking
detail. There are other omitted reactions and stance changes. Reference-assisted
corrections are separate review drafts; the baseline track is unchanged. Reference
CER 20.94% (930/4442) is a diagnostic, not a human omission score. Layout flags cover
16 cues; PR45 removes only a floating-point timing warning, leaving real warnings.

A 17-call short-window ASR diagnostic on previously used dialogue03/09 recovered
one phrase but introduced other errors. The first dialogue09 input failed the
video-only decoder; its eight completed dialogue03 calls were preserved, and only
the corrected lossless dialogue09 wrapper received new calls. A subsequent beam-2
diagnostic on three unchanged whole windows completed in 155.792 seconds with
zero retries; every transcription was identical to baseline. Neither candidate
was adopted. Model/prompt defaults remain unchanged. These are text comparisons,
not human listening, aligned Korean viewing or pristine-holdout acceptance.

## First-run setup

The merged hidden session-key launch (`--prompt-gemini-key` and
`start-media-clarity-gemini.cmd`) preserves valid inherited keys, allows blank
viewing-only startup and stops safely on invalid/cancelled/unavailable hidden input.
It does not persist a key or call Gemini. Child processes inherit the session
environment, including browser launchers; see subtitle docs for scope. A Linux
pseudo-terminal synthetic-key launch returned HTTP200 without echo/file storage.
Actual Windows 11 console input/double-click/reboot and RTX inference remain pending.

The merged `check-media-clarity.cmd` checks Python 3.12/64-bit, repository package
versions, actual FFmpeg/ffprobe and the isolated native model-runtime probe. It
opens no DB/media. Total 120 seconds, progress idle 75 seconds, retries zero;
raw native output is suppressed and completed rows survive limits. Full weight
hashes, actual inference and Gemini connectivity are explicitly separate.

## Active slice: offline cache restoration

`restore-qwen-models.cmd` / `scripts/restore_qwen_cache.py` restores the owner's
preserved public ASR/aligner cache bundles. Exact manifest hashes anchor metadata,
ordered archives, members and full weight hashes. Prerequisite checks happen before
GB-scale restoration. Configuration/native imports/CUDA availability are checked
in an isolated 60-second probe that does not require or load weights. It holds the
worker lease while the app lock remains held; restoration retakes the lease after
the native process exits. The app/worker OS locks are reused without opening the DB;
a running app/worker or custom qwen-paths configuration stops writes. Existing
matching files are reused, conflicting files stop, and unique incomplete files
remain as .partial. Only verified/flushed files are published with no-overwrite
links. Source/parent symlinks and Windows junctions are rejected. Source verification
can run separately with --verify-only and does not create a destination.

This slice reuses the PR47 setup process supervisor and factors the existing app/
worker OS-lock acquisition into one helper. Whole restore 1200 seconds, byte-progress
idle 90 seconds, automatic retries zero. The child receives no Gemini/Google key,
blocks Python network connections and makes no provider call or model inference.
It does not install dependencies or implement a new model-download path. Existing
Hugging Face internal retries still need resolution before a zero-retry installer.

Initial actual cache reuse stopped at model_cache_manifest_invalid because an
aligner manifest SHA constant was transcribed incompletely. Preserve that failed
run. The constant was recalculated from the saved manifest and a SHA-length guard
added. The initial evidence helper also assumed optional settings.json exists;
its missing before-snapshot is not preservation evidence. The corrected helper
records absent files explicitly. A new corrected run, not an unchanged retry,
verifies the real 15 archives and both existing full models. Actual timing and
preservation evidence are recorded in the review/PR; full new weight restoration
uses small synthetic fixtures locally and does not duplicate current GB assets.
Independent review found one P2 preflight gap: package/FFmpeg checks alone allowed
restoration with invalid device settings or a blocked native runtime. The isolated
runtime-only check above was added before hashing/writes; invalid configuration,
native import failure and missing CUDA now block model publication. Preserve the
initial reviewed revision. Require fresh independent delta review and fixed-HEAD CI.
Require uninvolved persistence/privacy review and fixed-HEAD Windows/Ubuntu CI
before development merge. Observe each CI at most ten minutes/ten polls.

## Remaining execution limits

The Work browser returned net::ERR_BLOCKED_BY_CLIENT. That route was stopped;
no browser/proxy/alternate-runner workaround is authorized. Real Fetch extension
capture/download → exact-video playback, native browser watching/seeking with the
actual subtitles and human listening remain unverified. Ordinary existing synthetic
CI still checks code; it is not a substitute for the blocked actual-media route.
Twelve minutes on Linux CPU does not replace 40–120-minute full-length acceptance,
Windows 11/RTX 4070 SUPER, enhancement or useful search/recommendations.
