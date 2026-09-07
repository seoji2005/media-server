# Viewing quality check · 2026-09-06

PR #9 merged as `bfce827`. This slice checks a different film, removes unusable black
search candidates, and runs an entire 12-minute input through the real subtitle pipeline.
The strongest new finding is **Korean dialogue quality needs work despite successful
processing and readable two-line rendering**. No replacement model was adopted.

## Different-film visual retrieval

Source: [The Great Train Robbery (1903), Library of Congress via Wikimedia Commons](https://commons.wikimedia.org/wiki/File:The_Great_Train_Robbery_(1903).webm),
marked public domain by that source. Downloaded 531,640,875 bytes through ordinary
permitted access; no cancelled download was retried or approval/network setting changed.
The [frozen manifest](../tests/fixtures/scene_holdout.json) retains source URL/hash and
**81 frames, 12 positive + 6 sampled-absent questions per language**. Labels were visually
checked and committed at `ad08c9c` before any model result. This is a project holdout;
unknown training overlap and one old black-and-white film limit generalization.

The existing SigLIP2 Base/16-224 ran offline, unchanged. CPU results:

| Language | First candidate correct | Correct within first 3 |
| --- | --- | --- |
| Korean | 8/12 | 10/12 |
| English control | 10/12 | 10/12 |

[Before-filter report](evidence/scene_holdout_baseline.json) retains ranks, model metadata
and frame hashes. Korean office gun-pointing ranked 6th and fighting on a train 17th:
objects/locations can match while the requested action fails. Do not claim action
understanding. One near-black frame was first for 6/18 Korean questions (including a
title question), and appeared in the first five for 8/18. Positive/absent scores happen
to separate in this film, but overlap in the [earlier film](scene-retrieval.md); no
universal relevance cutoff is justified.

The app now excludes only previews whose **maximum grayscale value is ≤8/255** from
visual candidates. Dark visible detail and title cards stay eligible. Images, vectors
and time previews are preserved; no migration/re-index is needed. An all-black sampled
set gets a “no images to compare” explanation, not a claim about the entire video's
content. [After-filter report](evidence/scene_holdout_filtered.json): 80/81 frames eligible,
no black result, the same 8/12 and 10/12 Korean metrics. This post-result fix is a
usability improvement, not a new held-out accuracy gain. Actual app-extracted JPEGs
matched all 81 frozen evaluation images byte-for-byte.

An extra one-second inspection at 274–284 s shows the lifting/throwing motion between
neighboring grid samples (274.222 and 284.194 s). The grid retains surrounding fighting,
but individual frames do not describe the motion or guarantee every brief action. This
small inspection does not establish a missed-scene rate or justify a new sampling system.

## Whole 12-minute subtitle execution

Used the already permitted 734.167-second *Tears of Steel* source; attribution/license
remain in [the original experiment](scene-retrieval.md). Real large-v3 ASR → MADLAD400
3B Korean translation → publication, four CPU threads, Linux/Python 3.12.13:
- ASR **346.834 s**, 56 source cues; translation **210.354 s**, 56 units.
- Pipeline **559.391 s** (about 9m19s; video RTF 0.762), 57 displayed cues.
- **0** source-text fallbacks; **3** reading-speed warnings.
- Peak process RAM **12,945.953 MiB** (~12.64 GiB); this is CPU RSS, **not VRAM**.

[Timing/checkpoint report](evidence/speech_twelve_minute.json). The direct production
job function used a timing wrapper around unchanged model methods; interpreter/Torch
startup is excluded. A short retrieval evaluation overlapped the early ASR run. The
movie contains substantial silence/action/credits; do not extrapolate this to a
60–120 minute dialogue-heavy movie. The attempted interruption did not execute before
completion; its failures are recorded. Earlier recovery evidence remains separate.

[12 saved dialogue cases](../tests/fixtures/speech_dialogue_quality.json) retain actual
ASR/MT output and context for the next comparison, including less problematic controls.
Given saved “Good ad-lib,” output “좋은 광고예요” changes the meaning; “멋진되고 싶어요”
is malformed, and adjacent dialogue has literal/passive phrasing and mixed register.
These are translation findings conditional on saved ASR, not independently scored
speech-recognition errors or human gold translations. Formatting rules cannot fix them.

## Verification and next step

At `b20fd99`: 8 scene tests passed (6.460 s), plus the scene DOM script. A first test run
caught a race in an existing lock-release assertion against the normal supervisor;
a bounded cross-thread wait retains the leak check without that false failure.
No full-suite repeat for this bounded ranking/UI change; prior evidence remains linked.

Actual Linux Chromium 149: generated Korean native captions (57 cues), Off/On, seek and
resume at 28.320 s; new-film ladder candidate → keyboard seek/play at 124.659 s;
absent-car candidates contain no black image; an all-black fixture gets the explicit
sampling explanation. Desktop/mobile screenshots were inspected. Page errors/external
page requests 0; production server log 0 bytes. Existing 22 subtitle rows and 16 file
rows were retained; only the explicitly watched sample's prior position changed.
Developer wrappers/weights/media/screenshots stayed outside Git; public structured
results and source attributions are retained here.

Translation comparison remains [partial](translation-comparison.md); local remains the
default. The later operational run below adds interruption evidence, without settling
natural long-dialogue quality, Windows/RTX or enhancement acceptance.

## 60-minute timeline: actual interruption and watching

Processing revision `175b8ac` (merged #10), Linux CPU/Python 3.12.13, four Torch threads,
installed large-v3/Silero/MADLAD. [Structured measurements](evidence/speech_long_resume.json).
No new download or cloud inference. The existing 734.167-second *Tears of Steel* audio
was split at 360 s; its second part starts at 3225.833 s, inserting 2865.833 s of silence.
The fixture has black 320×180/1-fps H.264 video and re-encoded 16-kHz/64-kbps AAC audio.
Its 60-minute duration tests source-time offsets and recovery, **not 60 minutes of speech**.

The actual FastAPI/uvicorn server, Jobs supervisor and worker entry point ran three
attempts. Observers delegated to unchanged model methods; the owning controller killed
only its server with SIGKILL. Existing jobs were quiescent before starting.

| Point | Actual result |
| --- | --- |
| ASR crash at 183.978 s | 20 segments produced, no transcript saved; all 20 regenerated with identical text/timing hashes |
| Translation crash | Whole transcript and 10/27 units survived in five batches; restarted worker made zero ASR calls and translated the remaining 17 units in order |
| Publication | One ready track, 35 display cues, zero source fallbacks, one reading-speed warning; total including both crashes 714.239 s |

The completed ASR took 274.901 s, including 41.701 s VAD. Decoded PCM was 230,400,000
bytes; VAD retained 105.248 s of speech. Peak worker RSS was 12,762.816 MiB, **not VRAM**.
Final checkpoints used 14 rows/2,963 payload bytes; database growth was 12,288 bytes.
Old database rows and both named sources/new managed copy passed preservation checks;
this was not a byte audit of every old managed file. Production server logs were empty.

Fresh probe review caught a race in using pre-kill polling as durable progress; actual
post-recovery snapshots were added before HTTP resume. The saved transcript/batch hashes
and resumed input sequence were checked against those snapshots. Worker lease release
was observed within 0.108/0.209 s including 100-ms polling; restart waited for release.
This does not retest overlapping orphan recovery or establish Windows behavior.

At UI revision `a1621a7`, real Chromium 149 displayed generated Korean native captions,
played/decoded the late interval, returned Range 206, switched captions Off/On and
restored **3230.690 s** after server restart. Screenshot inspected; page errors/external
page requests and server log bytes were zero. The 6.6-MB black fixture supplies neither
large-file startup evidence nor audible/human viewing acceptance.

An initial zero-silence-overlap assertion failed: the first late ASR/display cue starts
53 ms before the inserted audio boundary. This lead is recorded, not clamped away;
no cue lay wholly inside the long silence. There is no word-alignment gold or same-input
uninterrupted control. The displayed “왜 그녀는 이렇게 우리는 / 이미 그 하나를 시도”
is awkward Korean; successful recovery and two-line rendering do not resolve quality.

At that revision the UI distinguished ASR replay from resuming saved translation, including a warning
before pausing ASR; the previous generic preservation message hid the repeated work.
`node tests/ui/subtitles.cjs` passed with both interruption states and configuration-error
coverage. Main's [post-merge Linux/Windows check](https://github.com/seoji2005/media-server/actions/runs/34034514143)
passed; inspect the active PR's live checks for subsequent changes.

This run established the cost of losing partial ASR; the following change addresses
completed speech spans. It did not establish natural long-dialogue quality. Enhancement
comparisons are in [their existing record](enhancement-spike.md); no October feature
has been removed or counted complete by this operational check.

## Speech-span checkpoints — 2026-09-07

At `e6d2219`, real large-v3/int8 CPU ran the existing 48-second public JFK/silence
fixture in three modes through actual Jobs workers. Translation was a fixed Korean
fixture, not MADLAD. [Measured results](evidence/asr_span_resume.json):

| Run | Wall time including worker/model load | Result |
| --- | --- | --- |
| Prior whole-audio adapter | 44.98 s | Three cues |
| Uninterrupted speech spans | 51.46 s | Same text; maximum timing difference 20 ms |
| Kill second span, recover and resume | 59.51 s total | First saved span reused; final text/timing identical to uninterrupted spans |

The kill occurred after 23.43 s with one span durable through source time 14.896 s.
Call order was spans **1, 2 (interrupted), 2, 3**; resumed audio/prompt hashes matched
the control suffix. Saved payload, existing SRT track and source bytes stayed unchanged.
This short case adds recovery with modest overhead; it does not prove longer/mixed
speech quality. Full PCM decode and VAD still repeat, with no fixed replay cap for
uninterrupted speech. No new local browser or target RTX evidence is claimed.

Fresh review caught unintended prompt control tokens and valid Whisper end-time
overshoot; both were fixed and rechecked. Five focused tests cover real child kill,
stale/corrupt storage, source offsets/prompt restoration, legacy completed transcripts
and missing feature configuration. The first real control failed because restored
weights lacked `preprocessor_config.json` (128 versus 80 features); restoring it fixed
inference and the app now reports missing setup before running.

Validation: Python 142 tests passed before the final setup check; the final five-test
module and all seven DOM suites passed afterward. An initial run with the wrong
interpreter failed one existing subprocess test; restored venv execution passed all
31 subtitle tests. The npm wrapper was cancelled by environment approval, so the same
seven installed Node scripts ran directly (exit 0). Documentation links passed.
[CI run 34071493106](https://github.com/seoji2005/media-server/actions/runs/34071493106)
passed the integration of `3ead6b1` with base `175b8ac`: Linux ran 143 Python tests in
43.722 s and Windows Server 2025 ran 143 in 78.224 s. Both passed all seven DOM suites
and actual Chrome playback/native Korean captions, Range 206 and server restart with
7-second resume on the synthetic 20-second fixture. Source/copy preservation and quiet
logs passed; external page requests were zero. This establishes CPU/browser recovery,
not Windows 11/RTX inference or natural long-dialogue quality. For later revisions,
use the PR's current checks.
