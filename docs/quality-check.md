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

Next: reuse the saved transcript to compare one local translation candidate with
conversation context on the frozen dialogue cases, then inspect held-out dialogue
before adoption. Windows/RTX, 60+ minute processing/recovery and a natural enhancement
preset remain unverified or unadopted. None has been removed from October scope.
