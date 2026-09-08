# Cloud ASR and translation — 2026-09-08

**Decision:** use Gemini 3.1 Flash-Lite as the UI's initial translation selection.
Keep local Whisper ASR and selectable MADLAD. For a later permitted audio comparison,
prioritize Groq Whisper large-v3 and Mistral Voxtral Mini Transcribe V2; Scribe v2 is
the quality challenger. Mistral Small 4 is the next translation API candidate.
No new ASR API adapter or private audio upload is part of this change.

## ASR shortlist

Official standard API prices below are USD per **audio hour**, checked September 8;
tax, storage, transfer and discounts are excluded. The existing local Whisper has no
per-request API charge. A cloud API can save GPU time/setup, but cannot undercut a zero
API fee; power and target RTX processing time have not been measured here.

| Service/model | USD/hour | Fit and limits |
|---|---:|---|
| [Groq Whisper large-v3](https://console.groq.com/docs/speech-to-text) | $0.111 | Same Whisper family as the local baseline; multilingual, word/segment timestamps. Vendor reports 189× real time; not measured here and excludes our upload/integration overhead. No presumed quality upgrade over local large-v3. |
| [Groq Whisper large-v3-turbo](https://console.groq.com/docs/speech-to-text) | $0.040 | Cheapest shortlist entry; vendor reports 216× real time, with worse WER than full large-v3 in its comparison. Speed option if errors are acceptable. |
| [Voxtral Mini Transcribe V2](https://docs.mistral.ai/models/voxtral-mini-transcribe-26-02) (`voxtral-mini-2602`) | $0.180 | $0.003/min; English/Japanese/Korean among 13 languages, word timestamps and diarization, up to three hours per request. Promising independent architecture to compare against Whisper. |
| [ElevenLabs Scribe v2](https://elevenlabs.io/pricing/api) | $0.220 | Current API page price; older $0.40/hour FAQ figures were not used. 90+ languages, including Japanese, with word/character timestamps and diarization. |
| [Deepgram Nova-3 prerecorded](https://deepgram.com/pricing) | $0.258 monolingual / $0.312 multilingual | $0.0043/$0.0052 per minute. Japanese/Korean supported; multilingual mode includes English/Japanese. Model-improvement opt-out may change the quoted rate; premium not verified. |

Voxtral's vendor benchmarks report strong WER and speed, but are not this project's
recordings or an independent test. Its [speech API](https://docs.mistral.ai/studio/audio/speech_to_text)
typically transcribes one speaker during overlap; context bias outside English is
experimental. Scribe's [model announcement](https://elevenlabs.io/blog/introducing-scribe-v2)
and [API](https://elevenlabs.io/docs/api-reference/speech-to-text/convert) establish
features, not better results on our media. Deepgram's
[language table](https://developers.deepgram.com/docs/models-languages-overview)
must be checked when choosing a language/model pair.

## What “uncensored” can actually mean

Profanity masking, softened translations, provider refusals and permitted service use
are separate questions. No shortlisted hosted API is established here as accepting
every adult/sensitive source. Turning a text filter off does not override provider terms.

- Deepgram documents [`profanity_filter=false`](https://developers.deepgram.com/docs/profanity-filter)
  as the default. This preserves profanity at that filter stage; it is not an unrestricted-use promise.
- Groq has no documented STT profanity-mask setting in the inspected speech API.
  Its [AI policy](https://console.groq.com/docs/legal/ai-policy) still applies.
- Scribe's API defaults to verbatim behavior (`no_verbatim=false`); optional entity
  redaction is distinct from profanity. Its [use policy](https://elevenlabs.io/use-policy)
  still applies. No blanket adult-content permission was established.
- Mistral's [usage policy](https://legal.mistral.ai/terms/usage-policy/) does not contain
  the blanket restriction on all consensual adult text found in Alibaba's terms in
  this review. That is a reading of the policy, **not** measured refusal behavior or
  a guarantee; its restrictions on exploitation, illegal material and evasion remain.

Privacy settings also affect the practical shortlist. Groq documents self-service
[zero data retention, including STT](https://console.groq.com/docs/your-data), and
[no training without opt-in](https://console.groq.com/docs/legal/services-agreement).
Scribe defaults `enable_logging=true`; disabling logging requires Enterprise access,
while [training opt-out](https://elevenlabs.io/privacy-policy) is a separate account setting.
Deepgram's [terms](https://deepgram.com/terms) permit model improvement by default;
its [request API](https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded)
offers `mip_opt_out=true`, with possible pricing changes. Mistral's
[training choice](https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training)
and [abuse retention](https://legal.mistral.ai/terms/privacy-policy/) must be considered
separately; paying alone does not establish zero retention.

## Translation choice and measured quality

The [frozen 80-case comparison](translation-api-selection.md) favored Gemini over
the native-tokenizer-restored MADLAD baseline. It reused 56 public film-ASR units and
24 authored English/Japanese cases, with randomized provider labels and three independent
AI assessments. It was not human adjudication or a fresh holdout.

| Model | Valid outputs | Meaning score | Natural Korean score | Major errors |
|---|---:|---:|---:|---:|
| Gemini 3.1 Flash-Lite | 79/80 | 150/158 | 154/158 | 1 |
| Gemini 3.8 Flash | 79/80 | 149/158 | 155/158 | 2 |
| Local MADLAD | 80/80 | 120/160 | 136/160 | 11 |

Gemini scores exclude its blocked case, so denominators differ. Both Gemini models
blocked the same non-graphic assault report (one of 12 sensitive cases). For 3.1 Lite,
the accumulated 80-case API attempt time was 372.096 seconds and estimated token cost
$0.00753075. The corresponding 3.8 cost was $0.01313850; 3.1 cost about 43% less.
Matched timing evidence did not establish a general speed winner. MADLAD's historical
CPU run had different batching/cold-start conditions, so it is not a target RTX comparison.

Current standard synchronous prices, USD per million input/output tokens:

| API | Input / output | Decision |
|---|---:|---|
| [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/pricing) | $0.25 / $1.50 | Adopted UI default based on measured quality; still subject to refusals. |
| [Mistral Small 4](https://docs.mistral.ai/models/mistral-small-4-0-26-03) (`mistral-small-2603`) | $0.15 / $0.60 | Cheaper, English/Japanese/Korean and structured output; next candidate to measure. No key or measured quality/latency/refusal result here. |
| [Qwen-MT-Flash](https://www.alibabacloud.com/help/en/model-studio/qwen-mt-flash) | Singapore $0.16 / $0.49; Virginia/Frankfurt $0.101 / $0.28 | Low-cost general translation candidate, but not recommended for the requested adult-content freedom. Its dedicated API also lacks our existing structured-output contract. |

Alibaba's [Model Studio product terms §4.48.1(b)](https://www.alibabacloud.com/help/en/legal/latest/alibaba-cloud-international-website-product-terms-of-service-v-3-8-0)
incorporate the [Membership Agreement §3.2(e)(ii)](https://www.alibabacloud.com/help/en/legal/latest/alibaba-cloud-international-website-membership-agreement),
which restricts pornography/sexually explicit submissions. This September 8 finding
changes the previous next-candidate ordering; low token price does not resolve that mismatch.

## Prompt and defaults

New Gemini jobs use `faithful-context-v2`, whose exact text and SHA-256 live in
[`gemini.py`](../media_clarity/gemini.py). It explains that this is translation of
existing recorded dialogue, asks for meaning/register/intensity without euphemisms,
omissions or commentary, and prohibits invented age, consent or fictional context.
If the source actually supplies adult/consent context, preserve it; never append a
blanket “all adults and consensual” assertion. This is fidelity context, not a bypass.

Google documents that additional filters default to OFF for Gemini 2.5/3, while
[core protections are not adjustable](https://ai.google.dev/gemini-api/docs/safety-settings).
No `safetySettings` override was added. The [use policy](https://policies.google.com/terms/generative-ai/use-policy)
still applies, including its context-dependent exceptions; an adult/consent label is
not universal permission and does not guarantee a `PROHIBITED_CONTENT` response disappears.

The UI initially selects Gemini and labels the action with its name; text egress,
key readiness and API charges remain visible. Merely opening a video makes no request.
Missing keys fail before egress. Local is still selectable. API callers omitting the
provider retain the historical local behavior. Old `saved-context-v1` jobs keep their
exact model **and old prompt** during resume/restart, preserving checkpoints and identity.

### Real public-text spot check

The new prompt returned **9/9** valid Korean outputs in two generation calls, totaling
29.395 seconds and an estimated **$0.00077150**, plus two token-count calls. No request
was retried. [Public requests, responses, usage and observations](evidence/gemini_prompt_v2_spotcheck.json)
include eight ordinary/sensitive English/Japanese cases and the previously blocked
`auth_17` non-graphic assault report, which translated faithfully this time.
There was no contemporaneous old-prompt control or repeated trial: this does **not**
prove the prompt caused the changed refusal or establish a general low-refusal rate.
Author inspection still found softened extra profanity in `auth_12` and a lost
accidental-disclosure nuance in `auth_02`. Valid JSON and no refusal are not perfect quality.

This permitted public-text experiment used the existing configured system HTTPS route.
It does not validate production's unchanged direct-only network transport. The original
80-case quality scores above remain evidence for the old prompt, not a full v2 benchmark.

ASR service quality, latency and refusals remain unmeasured here. A future comparison
needs permitted identical audio, timestamps/error scoring, request-to-result time
including upload, actual billed usage and separate sensitive-speech checks. This host
has no ASR weights, little free disk, and no target Windows/RTX access. Existing public
translation measurements do not substitute for that audio test.

## Change verification

On this Linux CPU work host, Python 3.12 `-m unittest discover -s tests -q` passed
191 tests in 49.859 seconds, with one platform skip. Seven DOM suites passed through
direct local Node execution. The initial `npm test --prefix tests/ui` invocation was
interrupted by cancelled network approval; it has no completed result. The direct
Node run needed no package/network operation. Documentation-link and diff checks passed.
Local Chrome's existing socket EPERM limit was not retried. Linux/Windows CI must pass
the complete harness, including actual browser first-launch/restart, before merge.

Regressions cover the Gemini UI default, visible cloud disclosure, no job merely on
video open, explicit local selection, missing-key behavior, new prompt identity, and
historical 3.1/3.8 store recovery with their original request prompts. Synthetic recovery
checks do not establish real ASR quality or target GPU performance.
