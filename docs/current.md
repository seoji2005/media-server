# Current work

Live recovery base: Server `3524d738c9377c59faa8794a4e45cde4389b8f4e`
(PR56/57 merged); Fetch `b9fad12a91ab11cb007340bae74b279b3f6e91c9` (PR23 merged).
Server main CI34738936411 and Fetch main CI34691909315 passed. Codespaces PR51 remains separate and open at
this September 13 recovery; its work is preserved. Git/PR state is authoritative.
Existing cost/allowed-public-egress and reviewed, passing-CI development-merge
approvals persist. Release and subjective quality acceptance remain separate.

## October order

Active slice: recover the initial library connection. Failed/unread startup must
not render an empty-library invitation. Initial session and library reads share
ten seconds including response bodies, with zero automatic retries. A persistent
notice offers an explicit read-only retry; import controls wait for initial success.
Late timed-out responses cannot complete a newer attempt, and query/Continue
filters remain in the page. Incoming scene links still wait for a valid session.
The retry does not replay imports, settings writes or preparation commands.
This covers initial load, not automatic reconnection/token renewal after an
already-open app's server restarts; that existing path still requests page reload.

Product-JS regression reproduced the misleading empty state before the change.
Normal/failed/malformed startup, stalled headers/body, shared deadline, duplicate
clicks, late completion, filters and delayed scene entry pass under mocked HTTP.
Existing DOM suites pass. Actual Linux loopback HTTP/FFmpeg/SQLite checks inject
one failure at each temporary app read boundary and then reconnect/restart:
all DB rows, original bytes, supplied captions, offset and position survive.
Wrong Host/Origin and stale write tokens remain rejected. No model/API key/private
data use or security-boundary changes. Work browser limits below remain in force;
new retry UI native-browser interaction and human viewing are unverified.

Initial CI34739441697 failed: Linux passed Python/DOM but its browser fixture
injected a hidden file input before initial connection. It now uses the actual
enabled import button/file chooser and checks one isolated failed session read
followed by explicit reconnect. This extends the existing CI browser regression;
it does not use a new Work browser route or relax any timeout/security check.
Windows failed an older Qwen HTTP fixture's succeeded-state assertion. That test
started both a real supervisor and a manual synthetic executor for one queued job.
An isolated launch-failure probe reproduced the competing-owner failure locally;
the fixture now initializes jobs without that second owner. The original Windows
error code was not reported, so its exact cause remains unconfirmed; future failed
assertions include only the opaque error code. Product worker/model code is unchanged.
Final fixed-HEAD review and mandatory CI results belong to the PR.

Completed in PR57: preserve the newest requested library snapshot. An older GET that
finishes after a newer successful import/refresh could hide the newly listed item.
Ordinary refreshes and PR56's explicit import-result check now share one in-page
request revision. Older successes and errors cannot replace the current list;
a latest failed read keeps the last displayed list and reports its own error.
User filters/search stay unchanged except for the explicit full-library check.
No media/history write, automatic retry, new timeout or browser-storage layer.

PR56/57 passed independent fixed-revision review and CI34737420845/34738588730
before sequential development merge. The queued runs completed without rerun or
CI bypass. Both existing Chrome regressions used synthetic 20-second media;
they do not establish native upload/cancel/recovery or human viewing acceptance.

The new product-JS regression failed on the old response order and passes with
both ordinary and explicit result checks. Existing UI regressions pass. A real
loopback HTTP/FFmpeg/SQLite fixture captures a one-item response, imports a second
same-title video, reads both items, then releases the older one-item response.
The server retains both exact videos and the first item's caption/offset/position
after restart. This establishes the delayed-response scenario; DOM ordering is
mocked, and native browser viewing/upload remains unverified.

Completed in PR56: interrupt an import's response wait and explicitly check its result.
Upload progress no longer rounds 99.5% into a completed transfer and hides cancel.
The upload-complete event changes the control to stop waiting; abort does not
claim server rollback. A persistent recovery notice offers a bounded ten-second,
read-only full-library check with zero retries, including when existing search or
Continue filters would hide the imported video. It cannot upload or prepare a copy.
Stale XHR/read callbacks cannot release a newer upload or replace its notice.
Normal successful imports still prepare required playback copies. No server/storage
or security boundary changes, automatic upload retry or new upload size/time cap.

The regression reproduced the old cancellation failure with product JS and mock
XHR. A real socket HTTP/FFmpeg/SQLite test disconnects after all bytes arrive while
the isolated final-import boundary waits: an early list is empty, but the server
then commits. Explicit duplicate delivery and app restart preserve the same item,
user caption/offset/position, every DB row, exact original bytes and empty staging.
Native browser upload/cancel and Windows 11 hardware remain unverified; existing
browser restrictions below still apply. Fixed-review/CI results belong to the PR.

Completed in PR55: recover a failed caption-file load without changing viewing settings.
An inline, explicit reload beside caption selection reads the same selected VTT
with the same transcript/translation choice and timing offset. It makes no settings,
position or job write and does not replay/seek the video. The prior Off/reselect
workaround intentionally reset timing. Detached track events cannot affect a newer
load or video; native Off and uncertain/pending setting saves still take precedence.
Mock DOM/media regression failed before the control existed and passed afterward.
The socket HTTP/FFmpeg/SQLite regression checks an isolated failed VTT read, explicit
re-reads and app restart against exact caption bytes, every saved DB row and original
video bytes. Browser playback remains unverified under the limit documented below;
this is recovery behavior, not subtitle quality or a new model/prompt change.

Completed in PR54: explicit restart after failed native cleanup. A failed job can still
own a live guardian/compute process while its model cleanup stalls. Resume already
retired it; restart did not, leaving the replacement job queued behind that process.
Restart now retires the same job's process before queuing a replacement. The old
job, saved spans/batches and all subtitle versions remain preserved. A real child
regression failed before this fix and passed after it. Independent review and the
fixed revision's required CI belong to the PR.

A bounded Linux HTTP/worker/guardian/FFmpeg/SQLite run passed on a synthetic
120-minute timeline: 240 synthetic spans, 3,600 source units and 450 saved batches.
Pause plus Server process restart reused 90 saved spans; translation failure reused
1,600 saved units. Restart retired stalled cleanup, and an injected SQLite publish
failure resumed without new translation calls. Existing results, a user-supplied
caption, position, offset and original bytes stayed intact; consistent backups and
owned descendant cleanup passed. These are synthetic model/provider outputs, not
two-hour inference or viewing acceptance. See [evidence](evidence/subtitle-restart-recovery.json).

PR53 added the model-free `.venv-viewing` installer and normal launcher selection;
actual Linux installation/reuse and HTTP storage checks passed. See
[installation](runtime-install.md) for first-run and full-model setup commands.

At Server `8f59a27` and Fetch `b9fad12`, a separate Fetch → Server test
passed seven cases in 4.188 seconds, bounded at 120 seconds with zero automatic
retries. It used freshly compiled Fetch (166 source blobs checked) and actual
download/HTTP/FFmpeg/SQLite/Native framing. Duplicate delivery and explicit
lost-receipt retry preserved position revision 2, captions, −250 ms offset and
preferences; a same-title second video retained distinct correct IDs and bytes.
Wrong library/file/hash and stale position revision returned 409. Actual Server
process restart plus Native server-entry restored the exact video and 90 Range
bytes. Both DB integrity checks passed; original source trees and receipts stayed
unchanged and owned processes exited. Browser extension operation, human viewing
and Windows/RTX remain separate unverified gates.

Completed in PR52: two reproduced viewing reliability defects. Qwen PCM decoding now
rejects error-level FFmpeg output even with exit 0, before model calls or new
checkpoints. It retains only an error flag, with a drained pipe and no diagnostic
text in memory/logs/files. Valid shorter/delayed audio keeps its historical PCM;
there is no video-length equality heuristic or model/prompt change. This is a
bounded corruption check, not proof against every damaged container.

Position saves use a SQLite revision, one active request plus the newest pending
intent per item, five-second request bounds and immediate dialog close. A timed-out
write can still finish on the server; atomic revision checks reject stale writes.
The UI re-reads after uncertain responses before submitting a newer intent. Unsent
positions stay in this page and are labelled unconfirmed; refresh/browser exit can
lose an unconfirmed position. No browser-storage durability claim or automatic
retry of a failed request is added. Legacy position API calls remain accepted.
Schema 11 adds a position revision without rewriting existing history or media;
older app versions fail closed on a newer database.

Checks cover generated intact/truncated MP4, valid short/delayed audio, actual HTTP
handlers and SQLite preservation/restart, and delayed/lost responses under mocked
DOM/media. The socket HTTP fixture also starts/stops the real app and verifies
restored position/revision, supplied captions, offset and exact Range bytes.
Fixed-revision independent review and required Ubuntu/Windows CI belong to the PR.
Work browser playback remains blocked as described below. No new inference,
subjective subtitle quality, actual Windows 11/RTX or Fetch acceptance is claimed.

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

## Saved model restoration

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

PR48 independent review and required Windows/Ubuntu CI passed. Actual 15-archive
and full-model reuse took 27.51 seconds, preserving 17 tracked file states and the
DB/settings. The final isolated native gate separately passed in 3.697 seconds.
Initial failed manifest transcription, missing native preflight and the separate
child's non-inherited audit hook were corrected; failures/reviews remain in saved
evidence and PR48. Existing full-size reuse is not new full-size Windows restoration.

## Existing full runtime installation

`install-media-clarity.cmd` / `scripts/install_runtime.py` prepares a fresh repository
`.venv` and optionally chains the original pinned cache restore and final setup
check. See [installation](runtime-install.md). Existing environments are validated
without pip/package changes; invalid/partial environments are preserved and block
installation. Explicit first device selection is allowed under app/worker locks;
existing conflicting settings stop unchanged. Current Torch 2.8.0 CPU/cu126 and
repository requirements are retained; CUDA has no automatic CPU fallback.

Requirements are validated/snapshotted. Official PyTorch/PyPI binary downloads
precede an offline wheel install, pip check and the isolated weight-free native
probe. Connection/resume retries are zero; unknown pip versions without a resume
limit stop before network. The offline pip child installs its own socket guard;
--no-index alone would still allow direct-URL dependency traffic. There is no
automatic pip upgrade, source build, mirror,
model download or private media/API request. Completed wheels and partial venvs
remain in the checkout's ignored .setup-cache/.venv directories.

Installation has a 1800-second total / 120-second filesystem-byte-idle bound;
optional restore and final diagnostic have a separate 1320/90-second bound. Existing
owned process groups/Windows Jobs supervise descendants and retain completed checks.
Pip config/index/target injection and provider keys are removed from children while
existing TLS/proxy settings remain unchanged. Actual installation and preservation
results belong to the fixed revision's PR/evidence. Require fresh uninvolved review
and Windows/Ubuntu CI before development merge. CI: ten minutes/ten polls maximum.

## Remaining execution limits

The Work browser returned net::ERR_BLOCKED_BY_CLIENT. That route was stopped;
no browser/proxy/alternate-runner workaround is authorized. Real Fetch extension
capture/download → exact-video playback, native browser watching/seeking with the
actual subtitles and human listening remain unverified. Ordinary existing synthetic
CI still checks code; it is not a substitute for the blocked actual-media route.
Twelve minutes on Linux CPU does not replace 40–120-minute full-length acceptance,
Windows 11/RTX 4070 SUPER, enhancement or useful search/recommendations.
