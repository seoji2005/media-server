# Acoustic ASR pilot and free API access — 2026-09-08

The owner asked to try free APIs, compare WhisperJAV and Subtitle Nexus, and use
SRT-based material reflecting difficult speech in adult media. SRT contains text,
not sound: this experiment creates a **non-graphic synthetic acoustic pilot** from
an authored script. It does not use private media, erotic performances or recordings
of adult-media nonverbal vocalizations. ASR selection in the product is unchanged.

## Input and what can be concluded

Six Japanese utterances were synthesized separately using Gemini 2.5 Flash Preview
TTS. They include short corrections/reactions, negation, requested soft speech and
whispering. Generated clips total 17.34575 seconds; six calls cost an estimated
$0.00441650 under the published paid rates. They are synthetic voices, not actors or
recordings representative of natural adult dialogue. Requested style is not a
verified acoustic property.

The [offline builder](../scripts/prepare_acoustic_asr_probe.py) produces one common
mono PCM16/24 kHz WAV and an 18-cue UTF-8 SRT:

| Condition | Material |
|---|---|
| Source | All six generated clips, with 0.65-second added gaps |
| Quiet + noise | Same clips at -18 dB; seeded Gaussian noise at 10 dB SNR measured over each entire clip, including its pauses |
| Overlap | Three pairs; second voice starts one second after the first |
| Non-speech | Silence, synthetic noise bursts and a click; no speech expected |

The full WAV is **92.144375 seconds**. SHA-256:
`119dcf1deb46877b279b55f8d242fcc8216c05ea25579d21bced09068084c3f8`.
The SRT is the **intended TTS script**, not independently listened-to verbatim gold.
Its times describe clip placement, not validated word boundaries. Original clips,
generated audio/SRT and actual ASR outputs are retained in the separate downloadable
experiment bundle, outside Git. WAV hash/duration and all 18 SRT cues were verified.

Consequently, report utterance coverage and concrete output defects, **not WER/CER,
accuracy percentages or a definitive real-media ranking**. The same six lines repeat;
an engine can use earlier clearer audio to interpret a later difficult section.
Gemini TTS plus Gemini ASR can also favor that provider. Real recordings and independent
listening/annotation are required before adopting an ASR change.

## Completed inference

Media Server's production `LocalModels(..., asr_only=True).transcribe_parts` ran at
main `8e98ef2`, with its actual preflight, local Silero 6.0.0 VAD, frozen speech spans,
large-v3/int8 and four CPU threads. WAV audio was losslessly wrapped in Matroska for
the adapter's normal decode path. This is actual model inference, not mocked responses;
it is not an app/job/browser/restart or Windows/RTX test.

Gemini 3.1 Flash-Lite received the **same complete WAV**, a verbatim-transcription
instruction and JSON cue schema. Neither reference SRT nor source wording was sent.
The request used the existing configured system HTTPS route for this permitted public
experiment; it does not validate production's direct-only Gemini transport. No ASR
API adapter was added to the product. Every generation was attempted once.

| Engine | Measured time | Estimated API cost |
|---|---:|---:|
| Media Server large-v3, CPU int8 | 128.374 s; RTF 1.393 | $0 API fee; local compute/power not priced |
| Gemini 3.1 Flash-Lite | 15.347 s generation request; **29.185 s including token-count preflight** | $0.00203075 |
| WhisperJAV balanced/aggressive large-v2, CPU int8 | 48.29 s reported processing; RTF 0.524 | $0 API fee; local compute/power not priced |
| WhisperJAV balanced/aggressive large-v3, CPU int8 | 48.00 s reported processing; **50.139 s process wall time**; processing RTF 0.521 | $0 API fee; local compute/power not priced |

CPU time includes preflight/model loading/VAD/recognition within the adapter runner,
but excludes Python launch and prior container wrapping. API request time includes
request upload/response, but excludes TTS creation and local serialization. These are
one-run observations on this work host, not target GPU speed claims. WhisperJAV's
reported processing excludes CLI startup; model downloads/installations are excluded
from every inference time. The two WhisperJAV models were run sequentially with four
CPU threads and already downloaded weights. The installed CLI uses Silero 6.2.1;
the app's Silero 6.0.0 environment was preserved.

A fresh, uninvolved AI reviewer inspected text/coverage and checked the timing/cost
records; it did not listen to the audio. Entirely missing intended utterances:

| Condition | Media Server | Gemini | WhisperJAV v2 | WhisperJAV v3 |
|---|---:|---:|---:|---:|
| Source | 2/6 | 0/6 | 3/6 | 2/6 |
| Quiet + noise | 3/6 | 0/6 | 2/6 | 2/6 |
| Overlap | 1/6 | 1/6 | 0/6 | 1/6 |

This count accepts a partially retained utterance as present, so it is **not a count
of fully correct lines**. Gemini loses parts of two other overlapping lines; Media
Server drops a negation fragment and repeats another overlapping line. Both corrupt
the fast repeated direction word; a TTS pronunciation defect cannot be excluded until
listening review. Kanji/kana spelling differences are not counted as meaning errors.
No engine emitted a speech caption for the artificial non-speech control. WhisperJAV
adds an identifiable branding cue after speech; the originals preserve it, but it is
excluded from speech/coverage counts. Its v2/v3 statistics report 13/16 speech cues;
the corresponding exported SRTs contain 14/17 cues including branding.

WhisperJAV v2 retains a fragment of every overlapping line, but merges three source
utterances into an 11.99-second cue and changes a quiet utterance's meaning. V3 recovers
one source line that v2 omits, while losing the overlapping correction. Both still omit
the requested whisper and one soft utterance in the source/quiet sections. Thus these
outputs do not support a universal v2/v3 winner. Cue interval overlap alone would
overstate recognition: a long merged cue does not mean every intervening line survived.
V3 also starts one source subtitle about 1.05 seconds before that source clip begins;
preserving words and aligning readable subtitles are separate acceptance questions.

Media Server's missing source/quiet utterances are also absent from its recorded VAD
spans. This identifies speech detection as a concrete next investigation; it does not
show that the Whisper recognizer itself cannot recover those words.

## WhisperJAV and Subtitle Nexus

[WhisperJAV](https://github.com/meizhong986/WhisperJAV) is a pipeline, not a separate
ASR model. The fixed release is [v1.9.0](https://github.com/meizhong986/WhisperJAV/releases/tag/v1.9.0),
commit `ed5847ed73ab281c278efa88f421e34c1e94855c`, MIT. The CLI balanced/aggressive
profile uses large-v2, native VAD and subtitle postprocessing. Its newer ensemble
profile combines other engines and is a different, heavier comparison.

The isolated CLI environment reuses the existing CPU Torch runtime without altering
the app environment. Only core/CLI dependencies were installed. Upstream Git dependency
commits and resolved package versions are retained with the experiment; pinning
WhisperJAV alone does not pin those moving dependencies.

Both model binaries were downloaded and SHA-256 verified:

| Model | Pinned Hugging Face revision | model.bin SHA-256 |
|---|---|---|
| large-v3 | `edaa852ec7e145841d8ffdb056a99866b5f0a478` | `69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1` |
| large-v2 | `f0fe81560cb8b68660e564f55dd99207059c092e` | `bf2a9746382e1aa7ffff6b3a0d137ed9edbd9670c3b87e5d35f5e85e70d0333a` |

The first large-v2 invocation failed before ASR because this experiment's download
allowlist omitted its required `vocabulary.txt`. The CLI returned exit zero while
its statistics reported a failed file: exit code alone is not acceptance. The missing
pinned file was restored; initial logs/statistics were preserved, and retry uses fresh
output/temp/statistics paths. Its metadata lookup had one timeout/retry. Downloads,
installation and each local inference command have explicit limits below ten minutes.

The repaired large-v2 run completed: its log and statistics say success, and its actual
SRT was inspected. The terminal poll was cancelled before returning its process exit
status, so that status remains unverified; the successful output is independent
evidence. The subsequent large-v3 run saved exit code 0, process wall time, successful
statistics and its SRT through a separate wrapper. Do not rerun v2 merely to recover a
terminal status. Upstream metadata incorrectly labels itself 1.0.0; the pinned source,
installed package and CLI banner establish WhisperJAV 1.9.0.

Reproduction after installing the pinned CLI and supplying its model cache (change
`large-v2` to `large-v3` and use fresh output paths for the second run):

```sh
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 HF_HUB_OFFLINE=1 \
HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
HF_HUB_CACHE=/path/to/pinned-cache TRANSFORMERS_OFFLINE=1 \
timeout 540 whisperjav acoustic-pilot.wav \
  --mode balanced --sensitivity aggressive --model large-v2 \
  --device cpu --compute-type int8 --language japanese --subs-language native \
  --accept-cpu-mode --output-dir output-v2 --temp-dir temp-v2 \
  --stats-file stats-v2.json --keep-temp
```

The actual preset uses Japanese explicitly, beam 3, best-of 2, VAD threshold 0.25,
30 ms minimum speech and 300 ms silence/padding. Media Server uses automatic language,
beam 5 and its separate front VAD (threshold 0.5, 0 ms minimum speech, 2-second minimum
silence and 400 ms padding). Scene
splitting, decoding and subtitle postprocessing also differ. The same large-v3 weights
reduce one confound but do not isolate VAD, prove a speed ratio, or test Windows/GPU.
The source clips, manifest and builder reproduce the common input without new TTS calls:
`python prepare_acoustic_asr_probe.py source new-output` (NumPy required).

[Subtitle Nexus models](https://subtitlenexus.com/ai/models/) include Japanese-only
`sakura`, `sakura-preview` aimed at soft/whispered speech and the earlier multilingual `lulu`.
These are service model names; internal ASR weights/pipeline versions are not public.
The [API specification](https://subtitlenexus.com/api/v1/openapi.json) requires a key.
Use `audio_language:"ja"`, `subtitle_language:"ja"`, an accessible version slug and
`visibility:"PRIVATE"`; verify that the result is actual source transcription before
including it in an ASR comparison. API visibility defaults to PUBLIC, although PRIVATE
and UNLISTED exist. Account permission for PRIVATE must be checked. Its
[privacy policy](https://subtitlenexus.com/terms/view/privacy-policy/) distinguishes
private uploaded originals from potentially public derived subtitles/previews.
No Nexus account/key was available and no file was uploaded to it.

## Keys and free access

Official information checked September 8. A free allowance still requires an account
and key; no usable unauthenticated official endpoint for our own file was established.

| Priority | Key | Confirmed public offer and limits |
|---|---|---|
| First | [Groq](https://console.groq.com/keys) | Both Whisper variants are in Free plan: 20 requests/min, 2,000/day, 7,200 audio seconds/hour and 28,800/day; max 25 MB/file. Verify account limits before sending. |
| First | [Mistral Studio](https://console.mistral.ai/) | Free API mode, no card required. Exact free Voxtral availability/allowance is not established from public docs; inspect model access and limits first. One key can also test Small 4 translation. |
| Required for requested comparator | [Subtitle Nexus](https://subtitlenexus.com/accounts/api_key/) | Terms mention free offerings, but current free balance/eligible model cannot be verified publicly. Query user info, versions and cost before upload. |
| Optional | [Deepgram](https://console.deepgram.com/signup) | New account $200 credit, no card required, public models/endpoints included. |
| Optional | [ElevenLabs](https://elevenlabs.io/app/developers/api-keys) | Current API price table lists 4h30m Scribe v2 in Free/Pay-as-you-go; actual account entitlement/remaining allowance must be checked. |

Sources: [Groq limits](https://console.groq.com/docs/rate-limits),
[Groq file limits](https://console.groq.com/docs/speech-to-text),
[Mistral free API setup](https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key),
[Deepgram pricing](https://deepgram.com/pricing),
[ElevenLabs API pricing](https://elevenlabs.io/pricing/api),
[Nexus terms](https://subtitlenexus.com/terms/view/terms-and-conditions/),
[Gemini TTS](https://ai.google.dev/gemini-api/docs/generate-content/speech-generation),
[Gemini rates](https://ai.google.dev/gemini-api/docs/pricing).

This pilot uses only authored synthetic material. Before private audio use, account
privacy choices matter: Groq offers self-service ZDR; Mistral free data can be used for
improvement unless opted out; ElevenLabs logging defaults on; Deepgram model-improvement
opt-out may change price. [Earlier pricing/policy comparison](cloud-speech-and-translation.md).
Free access, training opt-out, retention and unrestricted content acceptance are separate.
