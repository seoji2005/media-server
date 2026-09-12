# Current work

Live recovery base is Server `7fde01e4274930a97a4e2c2405b0fe8deb456294`
(PR44 merged), Fetch `0d6aa28a4a0c6944c053e3d63e150908b44b9175`.
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

## Current correction: PR45

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
observation change at their fixed revisions. Require new fixed-HEAD Ubuntu/Windows
CI before merge. Observe at most ten minutes/ten polls; preserve any failure and
stop rather than extending caps or retrying unchanged failures.
