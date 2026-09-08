# Cloud ASR trials — 2026-09-08

The owner supplied Groq, Mistral, Subtitle Nexus and Deepgram keys and asked to add
Gemini 3.8 Flash. Keys are retained in owner-only private files outside Git and the
downloadable results. The same [92.144375-second acoustic pilot](asr-acoustic-comparison.md)
was sent without reference SRT/source wording. Its SHA-256 remains
`119dcf1deb46877b279b55f8d242fcc8216c05ea25579d21bced09068084c3f8`.
This is public authored synthetic material, not private media. Production ASR,
translation defaults and direct-only production transport are unchanged.

## Actual access and requests

Groq lists both Whisper variants. Mistral lists `voxtral-mini-2602`; its first model
query timed out after 15 seconds and one query with a longer connection deadline
succeeded. Gemini confirms `gemini-3.8-flash` supports generation and token counting.
Deepgram lists a project, but its balance endpoint returns 403 for this key.
An ordinary inference key need not grant billing access; no broader key is required
to continue this small experiment.

Nexus authentication and model listing succeeded. Both `sakura-2606` and
`sakura-preview-2608` quote **10 TOKEN per request**. The account reports zero tokens,
zero subtitle request credits and zero daily downloads. Although the quote response
says `can_purchase:true`, upload initialization returns **403, insufficient requests
or tokens**. No audio bytes were uploaded to Nexus and no transcription job was
created. Funding and usable download entitlement are needed before testing it; a
successful cost query does not prove sufficient balance. No top-up or plan purchase
was made. See [official API schema](https://subtitlenexus.com/api/v1/openapi.json).

Completed inference:

| Engine | Successful inference HTTP time | Common-audio list-price equivalent |
|---|---:|---:|
| Groq Whisper large-v3 | 25.267 s | $0.00284112 |
| Groq Whisper large-v3 Turbo | 16.987 s | $0.00102383 |
| Mistral Voxtral Mini Transcribe 2 | 11.849 s | $0.00460722 |
| Deepgram Nova-3 | 22.295 s | $0.00660368, opt-out adjustment unknown |
| Gemini 3.8 Flash | 17.461 s generation; **32.620 s with token-count preflight** | $0.00479025 |

These one-run timings include upload/response through this host's existing configured
system HTTPS route. They exclude account/model discovery, local serialization and
Python startup. They are not provider-compute latency or target-device performance.
The earlier Gemini 3.1 Lite generation was 15.347 s, or 29.185 s with its preflight.

Groq large-v3 first had a 15.023-second connection/read timeout. That attempt remains
saved separately: processing and billing are unknown. One explicit retry with a
30-second connection deadline produced the successful response above. The total
request-wait time across those attempts is 40.289 s, excluding the gap between them.
Other engines each received one transcription submission. A terminal poll for the
initial access-discovery runner was cancelled; the saved per-request files establish
the individual outcomes, not that runner's unreturned exit code.

The five completed-response list estimates total **$0.01986609**, excluding the
ambiguous first Groq attempt. This is not a receipt or confirmed free-credit usage.
Groq responses expose a 2,000-request limit but no billing plan. Mistral reports
`prompt_audio_seconds:91`: at the documented rate that is **$0.00455**, slightly below
the common-file-length estimate. Its `request_count:3` is a usage field inside one
HTTP response, not three observed client requests. Deepgram's billing access is
denied, and its training opt-out can affect price. Gemini cost uses generation usage
(2,304 audio + 83 text input tokens, 800 output tokens), not the larger countTokens
estimate. Its returned model is `gemini-3.8-flash`, standard service tier.

Rate sources: [Groq $0.111/$0.04 per hour](https://console.groq.com/docs/speech-to-text),
[Voxtral $0.003/min](https://docs.mistral.ai/models/voxtral-mini-transcribe-26-02),
[Deepgram Nova-3 prerecorded mono $0.0043/min](https://deepgram.com/pricing),
[Gemini 3.8 $0.75/M input, $3.75/M output through 2026-12-31](https://ai.google.dev/gemini-api/docs/pricing).

## Text coverage and subtitle defects

An independent read-only AI reviewer compared saved outputs to the intended TTS
script. It did not listen to the audio. A partially retained line counts as present;
these numbers measure **entirely missing intended utterances**, not correct lines.

| Engine | Source /6 | Quiet + noise /6 | Overlap /6 | Other material defect |
|---|---:|---:|---:|---|
| Gemini 3.8 Flash | 0 | 0 | 0 | One source cue begins about 0.52 s before its clip |
| Deepgram Nova-3 | 0 | 0 | 0 | Partial overlapping phrases lost; last cue extends into non-speech |
| Groq large-v3 | 0 | 0 | 0 | Invented thanks-for-watching line in non-speech |
| Mistral Voxtral | 0 | 0 | 1 | Overlap correction absent; merged cue up to 13.1 s |
| Groq Turbo | 0 | 0 | 6 | Two invented thanks-for-watching lines; last cue exceeds audio duration |
| Earlier Gemini 3.1 Lite | 0 | 0 | 1 | Partial loss in two additional overlapping lines |
| Media Server large-v3 CPU | 2 | 3 | 1 | Missing source/quiet speech is absent from saved VAD spans |
| WhisperJAV large-v2 CPU | 3 | 2 | 0 | Partial loss and long merged cues |
| WhisperJAV large-v3 CPU | 2 | 2 | 1 | Partial loss and timing defects |

Gemini 3.8 preserves the overlapping correction that 3.1 Lite omits. It also writes
the intended repeated direction word correctly where most other engines produce
similar unusual syllables. Without listening, that could be contextual reconstruction
of imperfect TTS, rather than more faithful acoustic recognition. The repeated script
and Gemini-generated source audio may favor it. Its cues are relatively short (maximum
3.55 s), but plausible cue bounds do not establish accurate word alignment.

Deepgram retains a fragment of every line, yet mixes or loses important overlapping
phrases and changes a quiet question's meaning. Its final 12.08-second cue ends at
80.835 s, after the 79.144375 s start of the non-speech control. The actual word sequence
ends near 71.875 s while punctuation extends further: classify this as timing spillover,
not clear newly invented speech. The returned model version is `2026-08-03.6336`,
`general-nova-3`.

Groq large-v3 emits an invented caption at 79.86–88.62 s in the non-speech control.
Its otherwise bounded cues can last 10.32 s and span long intervening silences. Turbo
replaces all six overlapping lines with an invented closing message, then repeats it.
Its last cue ends at 111.24 s, about 19.10 s beyond the input. **HTTP 200 is not valid
subtitle output**: Turbo fails the experiment's duration bounds. Its original JSON
and diagnostic raw SRT remain untrimmed. Importing a syntactically parseable SRT through
a compatibility reader that clips timestamps would not repair the invented text.

Mistral preserves the source/quiet lines but omits one overlapping line and fragments
of others. Nine cues include a 13.1-second source cue and an 11.8-second noisy cue;
readable subtitle segmentation would require further work. Explicit language was
omitted because its API does not support language selection with timestamp granularity.

## Request settings and decision

- Groq: original WAV, Japanese, temperature 0, `verbose_json`, segment + word times;
  no contextual/reference prompt. [API parameters](https://console.groq.com/docs/speech-to-text).
- Mistral: dated `voxtral-mini-2602`, segment timestamps, diarization off, no language
  or context bias. [Timestamp compatibility](https://docs.mistral.ai/studio/audio/speech_to_text/offline_transcription).
- Deepgram: `nova-3`, Japanese, utterances and punctuation on, smart formatting and
  profanity masking off, `mip_opt_out=true`; no redaction or key terms.
  [Prerecorded API](https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded),
  [training opt-out](https://developers.deepgram.com/docs/the-deepgram-model-improvement-partnership-program).
- Gemini: exactly the earlier generic verbatim-ASR instruction and JSON schema,
  low thinking, 4,096 requested output tokens, no reference text. No added adult or
  consent premise was needed for this neutral acoustic test.

On this pilot, Gemini 3.8 is the strongest **next ASR candidate to validate**, while
Mistral offers the shortest observed request time. Deepgram's zero whole-line omissions
do not erase its partial errors; Groq's hallucinations matter despite low price.
No real-media ranking, WER/CER, adult-content acceptance or unrestricted-service claim
is supported. WhisperJAV timings remain CPU observations with different preprocessing.
Production adoption still needs independent listening, natural held-out speech and
subtitle timing validation. Nexus remains blocked on the supplied account's allowance.

The delivered results archive retains raw responses, raw SRT exports, failed attempts,
sanitized access outcomes and this report. Credentials, private account identifiers,
signed upload URLs and model weights are excluded. Original pilot files remain intact.
