# Current work

Live recovery base is Server `b4846ee3108742da97806d7ac5be3f5a2193fdff`
(PR46 merged), Fetch `0d6aa28a4a0c6944c053e3d63e150908b44b9175`.
PR46 CI34676198953 and merge-main CI34676537273 succeeded on Ubuntu/Windows
after independent privacy and fixture-delta review. The key launch helper is merged;
that does not establish target-device or viewing acceptance.
PR45 CI34673272608 and merge-main CI34673519391 succeeded on Ubuntu/Windows.
The actual model trial below used unchanged PR44 main
`7fde01e4274930a97a4e2c2405b0fe8deb456294`, not the newer launch changes.
PR44 CI34663790987 and main CI34664078212 succeeded. Earlier PR43 main
CI34660439190 failed; PR44 fixed the preparation-event fixture and added browser
stage diagnostics. Those checks are synthetic product CI, not model quality or
Windows 11/RTX acceptance. Existing cost/allowed-public-egress and reviewed,
passing-CI development-merge approvals persist; release and subjective acceptance
remain separate.

## Actual product trial: September 12

The current Work installed the repository runtime: Torch 2.8.0+cpu and
Transformers 5.16.1, plus the requirements files. Bounded official CPU/PyPI
installs and the actual Gemini 3.8 Flash preflight succeeded with zero retries.
The separately downloaded newer Torch/Transformers wheels were not adopted.
Only the Gemini key from the owner's saved environment file was injected;
credentials were not added to logs, artifacts or Git.

After runtime preflight, all saved ASR/aligner archive members and full model
SHA256 values were verified and restored. No old trial DB was found, so this
was a new run on unchanged main above, not a resume of the lost 18 spans.
The public dialogue03 WAV/EAF hashes matched. Its complete 762.048-second audio
was wrapped with a synthetic background and byte-identical decoded PCM.

Actual product HTTP import and subtitle job completed Qwen3-ASR-1.7B →
Qwen3-ForcedAligner-0.6B → Gemini 3.8 Flash using the current model/profile/prompt:
28 spans through 762.048 seconds, 20 translation batches, 154 translated units,
208 display cues, succeeded; supervisor elapsed 1680.93 seconds. Automatic
retries were zero. Bounds remained speech 2700/300 seconds and translation
600/120 seconds (total/committed-output idle). Consistent SQLite backups were
saved throughout, and the final checkpoint was durably saved. Originals and the
completed baseline track remain unchanged.

Output hashes, span continuity, cue validation and the DB integrity check passed.
Actual HTTP served Japanese/Korean VTT and prepared an MP4 rendition; three byte
ranges returned 206. A same-process test server/client verified saved position
and caption selection/offset after restart and restored its viewing choices.
That check's two retained server processes exited with -15. The trial supervisor's
psutil process enumeration did not match the execution PID namespace; its empty
survivor report is not proof that every model/FFmpeg descendant exited. A corrected
future supervisor was prepared separately, not substituted into historical evidence.

Text comparison of all 154 units found material quality issues: the reference's
千歩 became 店舗, producing a false shop/points story around 138–167 seconds;
overlapping turns around 197–225 seconds lost the one-hour walking detail and
became an awkward merged sentence. Reference-assisted corrections remain review
material, not evidence of unaided model quality. Automated reference CER is 20.94%
(930 edits / 4442 normalized characters); overlapping speakers, fillers and
orthography make this diagnostic rather than a human omission score. Layout
flags cover 16 cues (15 short, two fast, one limited; categories overlap).
Full audio coverage does not establish complete or faithful dialogue recognition.

The local browser returned `net::ERR_BLOCKED_BY_CLIENT`; that route was stopped
without browser/proxy/alternate-runner workarounds. Human listening, native browser
playback/seeking with these outputs, real Fetch extension download → exact-video
playback, useful enhancement and search/recommendation quality remain unverified.
This reference was used in earlier translation comparisons and is not a pristine
holdout. Twelve minutes on Linux CPU does not replace 40–120-minute acceptance
or Windows 11/RTX 4070 SUPER testing.

## Merged correction: PR45

Actual evidence exposed a floating-point-only timing warning. Publication now
ignores differences within 1e-9 seconds, while retaining zero-duration units,
forced cuts and real corrections. This does not rewrite saved evidence, tracks,
text, timing or user edits. The baseline track has 28 review spans; applying the
corrected predicate to its evidence leaves 27 real review spans. Regression tests
reproduce the original false warning and retain the meaningful warning cases.

Initial PR45 CI34672525701: Ubuntu passed; Windows passed 294 Python tests,
11 DOM suites and the first browser phase, then timed out at restart resume
(browser.mjs:215). The logged state did not establish the direct cause. General
card opening restores time then autoplays, so polling a narrow 7±0.25-second
window can miss a correct restore. The test now verifies the saved position and
arms native seek observation before opening, records the first restored position,
and pauses before playback advances it. A missing/wrong restore still fails;
there is no restore-time assignment, deadline increase or unchanged CI rerun.
Separate uninvolved reviewers passed the production warning change and the browser
observation change at their fixed revisions. The final PR and merge CI passed as
recorded above; this does not change the actual-quality limits.

## Ordered October work: first run and quality

The owner confirmed October 19 leave and requested execution in order. Prioritize
ASR/translation quality, Windows setup and everyday launch, real Fetch companion
download to exact-video playback, 40–120-minute interruption/recovery, then integrated
enhancement, search/recommendation quality and target-device viewing. Keep the
October 5 integration / October 11 stabilization targets and the remaining week as
buffer. These are targets; the complete scope remains in the product contract.

A bounded ASR-only diagnostic compares existing approximately 30-second windows
with two contiguous shorter windows near 15 seconds, using unchanged Qwen weights,
auto language, prompt, precision and decoding. Four dialogue03 windows reuse verified
baseline payloads/audio hashes; three dialogue09 windows use new baseline inference.
The original product output and all user/reference-assisted edits stay unchanged.
An initial diagnostic passed dialogue09 WAV directly to the product's video-only
decoder and failed before that file's inference. Preserve that failed run and its
eight completed dialogue03 calls. The corrected dialogue09 input is a lossless
Matroska wrapper with matching full decoded PCM; do not relax the product whitelist
or rerun the completed dialogue03 calls. This is a new corrected diagnostic, not an
automatic retry or a product HTTP acceptance run.

The short input recovered the one-hour walking phrase in one dialogue03 window,
but did not fix the thousand-steps/shop error and introduced other transcription
errors, including dialogue09's AI terms. Do not adopt a global chunk-size change
from these results. Both references were used previously; neither is a pristine
holdout. Text inspection is not human listening, alignment or Korean viewing quality.

The optional `--prompt-gemini-key` / `start-media-clarity-gemini.cmd` launch asks for
a hidden, session-only key before app creation. Valid inherited keys skip input;
blank input starts viewing only. Invalid or unavailable hidden input stops safely.
No key is saved to app files, registry, arguments or logs, and prompting does not
contact Gemini. The process environment is inherited by children, including browser
launchers; see the subtitle documentation for the exact scope. `doctor` reports
presence/format only. This is an everyday launch improvement, not a complete
installer or a model/API connectivity check.

Local checks cover credential cancellation/validation, environment restoration,
child inheritance, diagnostics without key disclosure and existing startup/model
diagnostics. A real Linux pseudo-terminal launch with a synthetic key returned
HTTP 200, did not echo/store the key, and the owned server exited with -15. No browser
was attempted. Windows CMD dispatch is checked in required CI; actual Windows 11
console input/double-click/reboot and RTX inference remain unverified.

Require an uninvolved privacy review and fixed-HEAD Ubuntu/Windows CI for launch
changes before development merge. Observe CI at most ten minutes/ten polls; preserve
failures rather than extending caps or retrying unchanged failures. Continue bounded
Windows runtime/model setup and diagnostic packaging next. The blocked local browser
route still prevents real extension/playback acceptance in this Work.

First PR46 CI34675874046: Ubuntu passed; Windows ran 301 Python tests and failed
one new credential fixture before the DOM/browser stages. The fixture cleared the
entire environment, so Windows `Path.home()` could not resolve its normal user
directory during CLI construction. Restrict fixture isolation to removing only the
Gemini key and preserve the rest of the user environment. This changes the test
setup, not production storage paths, key handling or timeout/skip policy. Require
new fixed-revision review/CI; retain the original failed run.

## Setup check helper

`check-media-clarity.cmd` / `scripts/check_setup.py` checks Python 3.12/64-bit,
the checked-out base/Qwen requirements (including local Torch CPU/CUDA tags), actual
FFmpeg/ffprobe version execution, and the existing isolated model-runtime diagnostic.
Missing prerequisites stop the native model check. Readiness is prerequisite evidence:
full model hashes, actual inference, per-codec playback and Gemini connectivity remain
explicitly unchecked. No installation, download, provider call or media scan occurs.
It neither opens nor migrates the media DB; native diagnostics reuse the worker lease
in the existing library. Missing library roots are reported without being created.

The lightweight checker owns a POSIX process group or the existing Windows kill-on-close
Job before its child handshake. Whole check: 120 seconds, progress idle: 75 seconds,
zero retries; FFmpeg/ffprobe each retain 10 seconds and the model probe 60 seconds.
On a bound it stops its owned group/Job and returns completed checks. Diagnostic output
is bounded and raw native output is suppressed. Gemini/Google key values are excluded
from the checker child environment; the parent's presence/format boolean is informational.
Normal console output gives actionable states; `--json` returns shareable diagnostics
without media paths, titles or key values.

Local targeted tests cover version mismatch, unsupported metadata, missing dependencies,
real isolated missing-library checks, total/idle deadlines preserving completed results
and an unrelated process, plus launcher behavior. A fresh temporary library referencing
previously SHA-verified model assets passed the actual Linux CPU native-runtime check
without creating a DB or loading ASR/aligner weights. Windows CMD dispatch remains a
required CI check; real Windows 11 setup, RTX and viewing acceptance are still pending.
Require an independent review of the new supervisor/privacy boundary and fixed-revision
Ubuntu/Windows CI before development merge. Model restoration and bounded installation
remain the next setup work; do not call this an installer.

Initial independent review reproduced two supervisor defects before CI: a POSIX
worker exiting first could leave its descendants alive, and a row written during
the last polling interval could be lost at the deadline. Keep the failed revision
in history. The correction observes POSIX exit with `waitid(WNOWAIT)` so the owned
leader remains waitable until group cleanup, then always cleans the group and reaps
it. Windows retains its kill-on-close Job. Bounded output is drained before deadline
decisions and after cleanup; a timeout remains blocked even if a final ready event
was written. Regressions cover normal/error worker exit with a live descendant,
an item arriving in the final interval, and total/idle caps preserving an unrelated
process. The native CPU prerequisite result is not descendant-lifecycle acceptance.

First PR47 CI34677770376: Ubuntu passed; Windows failed the timeout fixture when
deleting the temporary progress file (WinError 32). The log does not expose the
inner shutdown exception, so its exact cause remains unproven. Inspection found
that a redundant direct kill after Windows Job closure could race termination and
skip the owned handle wait. The correction waits after Job closure without that
second kill; wait and pipe closure also run if shutdown signaling raises. A remaining
temporary-file cleanup error returns a sanitized blocked result with completed
checks, rather than discarding them in a traceback. Keep the first failed CI;
require fresh independent delta review and Windows/Ubuntu CI on the correction.
