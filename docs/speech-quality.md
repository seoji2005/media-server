# Real multilingual speech check

On 2026-09-06, the production CLI/HTTP app completed seven public speech cases on
Linux CPU. This found two correctable caption defects and remaining ASR/translation
errors. It is not a Windows, browser, natural code-switching or human quality sign-off.

## Inputs and method

Audio attribution: **FLEURS**, Conneau et al. (2022),
[original Google dataset](https://huggingface.co/datasets/google/fleurs),
[paper](https://arxiv.org/abs/2205.12446), **CC-BY-4.0**. Individual test WAVs and
reference transcriptions came from the
[FluidInference extraction](https://huggingface.co/datasets/FluidInference/fleurs-full/tree/1cca811bb8ea4d370345f108f00518167040282c),
pinned revision `1cca811bb8ea4d370345f108f00518167040282c`.
The five source WAVs total 60.54 seconds. Their download hashes remained unchanged.
No private media was used. Audio, reference transcripts, generated captions and DBs
are excluded from Git; the table records sample IDs and observations only.

FFmpeg wrapped each public WAV in a black 320×180/10 fps H.264/AAC MP4 for actual
import → large-v3 ASR → MADLAD Korean translation → ready VTT HTTP retrieval.
Mixed cases concatenate `ja_jp_0000`, `en_us_0000`, `ja_jp_0001`, with 0.5 or 3 seconds
of appended silence after each clip. Original leading/trailing silence is retained:
these are **not** 0.5/3-second speech pauses or natural within-sentence code-switches.

Runtime: Linux, 9 EPYC vCPUs, 21 GiB RAM, no GPU, Python 3.12.13; four OMP/MKL
threads. Pinned model/runtime versions and installation commands are in
[subtitles](subtitles.md) and [runtime packages](model-runtime-linux-cpu.txt).
Production CPU ASR uses int8; MADLAD uses float32, batch two, beam four. Times include
the import/job wait and model loading, measured once per case. Do not extrapolate
these short runs to two-hour films or target GPU speed/memory.

## Observed baseline at f1663ee

| Case | Audio seconds | End-to-end seconds | Text inspection against reference |
| --- | --- | --- | --- |
| ja_jp_0000 | 10.44 | 40.66 | ASR changed “course” to “configuration”; Korean inherited the wrong meaning. |
| ja_jp_0001 | 14.22 | 40.21 | Normalized Japanese matched; Korean compressed the instruction and religious place names. |
| ja_jp_0002 | 12.84 | 59.01 | ASR misspelled Barcelona/Catalan; MT restored familiar names. Four source cues became one long Korean cue. |
| en_us_0000 | 10.56 | 43.63 | Main content retained; plural inflection differs from reference, Korean remains literal. |
| ko_kr_0000 | 12.48 | 49.51 | ASR confused a Korean word and wrote a measurement as 15m; this unnecessarily triggered Korean-to-Korean MT. |
| Mixed, +0.5 s | 36.72 | 81.36 | All three utterances present; English “However” omitted. MT emitted literal entities and duplicate quotes. |
| Mixed, +3 s | 44.22 | 80.25 | All three utterances and English connector present; Japanese “course” error remained. |

Japanese character comparison used NFKC, case folding and alphanumeric characters
only, then Levenshtein distance: 3/45, 0/46 and 7/71 edits for the three individual
samples. This tiny diagnostic is not a general accuracy estimate. Text/reference
inspection is not listening, native caption display or a blind human quality review.

## Correction and repeated execution at 5ea410c

- Korean-only units containing explicit numeric units such as `15m` now pass through
  unchanged. Other foreign letters still require translation. Classification removes
  only known numeric notation from its temporary copy; it never alters the transcript.
- Generated translation entities decode once before validation and escaped WebVTT
  output. Imported/source/fallback text never takes this new normalization path.
  Pipeline v5 prevents reuse of unfinished v4 results; existing ready versions remain.
- The same Korean sample completed in **23.20 s** and the saved caption exactly matched
  its ASR text. This prevents further rewording; the original recognition error remains.
- The same short mixed sample completed in **79.98 s** with unchanged ASR/timing and
  three Korean units. Literal entity syntax disappeared. Duplicate quotation marks,
  the omitted English connector and the Japanese word error remain unfixed.
- All nine baseline/corrected tracks, their source transcripts and saved cue arrays
  survived a subsequent production-server startup unchanged; VTT bytes matched exactly.
  Range bytes matched and source MP4 hashes were unchanged in every run. All three
  production-server log files were zero bytes.

A separate, temporary **CPU float32 ASR** comparison on `ja_jp_0000` and `ja_jp_0002`
took 41.59/39.73 seconds (ASR only). It produced the same mistaken Japanese text as
int8. Precision alone did not resolve these two cases; production settings were kept.
This comparison did not run MADLAD or the target CUDA ASR path.

Verification: `python -m unittest discover -s tests -q` — **53 passed**, 10.141 s,
exit 0. New regressions cover foreign-word boundaries, inert generated markup,
single decoding, source fallback and saved results across failure/resume. A fresh
reviewer independently passed 28 subtitle tests (4.154 s) with no actionable findings
at local `9b7d469`, complete tree `f56413f637730d536695035b89b4c723d51d59ee`, identical
to published `5ea410c`. That review supplies no real-model/browser/Windows evidence.

At that stage, remaining gates included natural rapid language changes, omissions/proper nouns, fluent Korean,
long-cue readability, long films, actual browser caption playback/seek/resume, Windows
setup, CUDA bfloat16 and 12 GB fit. Successful jobs do not make these gates complete.

The [12-minute viewing quality check](quality-check.md) extends real execution to an
entire short film and records conditional translation errors and browser caption playback.
It does not establish 60+ minute recovery or target Windows/RTX readiness.

## Span-boundary comparison — 2026-09-07

At `3ead6b1`, the prior whole-audio adapter and new checkpointed speech spans ran on
six cases below, using the same pinned large-v3/int8 CPU setup. FLEURS recordings were
restored from the pinned source above; their bytes remained unchanged. Film dialogue
uses a 52-second Tears of Steel excerpt, source time 18–70 s ([attribution](scene-retrieval.md)).
These are actual ASR calls, with **no translation inference**. [Compact results and method](evidence/asr_span_quality.json).

| Case | Prior / spans, seconds | Text inspection |
| --- | --- | --- |
| Japanese 0000 | 25.63 / 26.56 | Same course/configuration error; 3/45 normalized reference edits in both. |
| Japanese 0002 | 25.27 / 25.58 | Same proper-name errors; 7/71 edits in both. |
| Korean 0000 | 22.87 / 23.27 | Same text and 3/53 edits, including numeric notation differences. |
| Mixed, appended 0.5 s | 43.53 / 54.42 | Same normalized words; However still missing in both. Punctuation and cue partition differ. |
| Mixed, appended 3 s | 43.83 / 51.55 | Same text, including However. |
| Film dialogue | 41.70 / 53.73 | Same text; 12 versus 15 source cues yield the same 12 translation-input strings. |

No added lexical omission/repetition appeared in this sample after the earlier
normalization; that is not a general accuracy claim. Punctuation, timing and translation
quality remain separate. The film has no independent spoken-word gold in this check.
Mixed inputs are concatenated read speech, with original silence retained, not natural
code-switching. The short-gap English VAD onset was 0.772 s later within its source
utterance than in the long-gap case; its relationship to the missing connector needs
an isolated test before changing VAD policy.

Fresh processes resumed the long-gap mixture and film after receiving their first saved
span. Both returned exactly the uninterrupted parts/text/timing (40.39 / 32.12 s for
remaining processing). This checks adapter context restoration; the separate
[actual worker-kill test](quality-check.md#speech-span-checkpoints--2026-09-07) covers DB recovery.
Single-run timings include decode/VAD/model load, exclude worker startup, and show
overhead rather than a speed improvement. No new browser, MT, memory or target RTX
claim is made. Keep the processing code unchanged on this evidence; prioritize the
everyday Windows launch path next, while recognition and enhancement quality remain open.
