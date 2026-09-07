# Translation API comparison — 2026-09-07

**Selected: Gemini 3.1 Flash-Lite for new explicitly requested Gemini translations.**
The measured quality is close to 3.8 Flash, with about 43% lower token cost and no
established general speed difference. Local MADLAD stays available and remains the
initial UI selection. Neither Gemini variant is sufficient to promise uninterrupted
translation of every sensitive video.

The owner requested a choice based on Korean subtitle quality, elapsed time, cost,
and refusal of legitimate sensitive dialogue. [Measured outputs and assessment](evidence/translation_api_comparison.json)
use the existing frozen 80-case fixture, not a new holdout: 56 public-film ASR units,
12 authored ordinary cases and 12 authored sensitive cases; 68 English and 12 Japanese.

| Actual API | Valid units | Blocked sensitive cases | Same current 40 film units | Estimated token cost, all 80 |
|---|---:|---:|---:|---:|
| Gemini 3.8 Flash | 79/80 | 1/12 | 90.153 s | $0.01313850 |
| Gemini 3.1 Flash-Lite | 79/80 | 1/12 | 82.320 s | $0.00753075 |
| Gemini 2.5 Flash-Lite | 0/16 attempted | Not measured | Unavailable | Unknown; no usage returned |

Time includes the Work environment's system HTTPS route and response parsing. The
40-unit comparison uses five matched eight-unit batches from this session. Median film
batch latency over all seven batches was 16.621 s / 16.998 s respectively; this small
sample does not establish a general speed winner. All 80 attempts took 360.765 s /
372.096 s because the 12 sensitive inputs were deliberately requested one at a time.
That protocol exposes individual refusals and is not a full-film throughput benchmark.
The 3.8 total reuses 16 earlier outputs/time samples, one with a 1,024-token cap; new
calls use 4,096. No repeated full-film passes or ASR were run.

Both APIs blocked the same non-graphic report of sexual assault (`auth_17`) with
`PROHIBITED_CONTENT`. Other sensitive dialogue received responses, but wording can still
be softened. Neither model is shown to be less censoring; 12 examples do not establish
a general refusal rate for private videos or graphic material. Default provider safety
settings were retained, with no retry, prompt evasion or automatic fallback.

The cheaper 2.5 Lite appeared in the authenticated model list but returned HTTP 404 /
`NOT_FOUND` for two generation requests. Comparison stopped after those two errors;
the other 64 cases were not attempted. Its two unknown-cost reservations total
$0.05314030; these are conservative holds, not observed invoice charges. Historical
unknown-cost reservations from the previous experiment remain preserved separately.

Three independent AI assessors review per-case randomized A/B/C outputs without
provider identities, comparing meaning first and natural Korean second. The local
MADLAD baseline reuses its native-tokenizer-restored outputs. Model assessment is not
human review, statistical significance or a guarantee of translation quality. Source
ASR ambiguity remains: inventing a minute from “We're only one” is still an error,
even if the resulting Korean reads naturally.

| AI assessment | Meaning points | Naturalness points | Major meaning errors | Missing output |
|---|---:|---:|---:|---:|
| Gemini 3.8 Flash | 149/158 | 155/158 | 2 | 1 |
| Gemini 3.1 Flash-Lite | 150/158 | 154/158 | 1 | 1 |
| MADLAD, saved local baseline | 120/160 | 136/160 | 11 | 0 |

Scores are 0–2 per available output; refusal is reported separately. The one-point
differences between Gemini models are small and subjective. Both fix several local
baseline failures, such as accidental disclosure interpreted as physical slipping and
omitting “Do not shoot.” Both still make mistakes and soften some profanity. Historical
MADLAD CPU translation took 210.354 s for film + 112.267 s for authored inputs, with
different batching/context and first-load conditions; it is not an RTX speed comparison.

The app now creates Gemini jobs with `gemini-3.1-flash-lite`. Existing 3.8 configurations
retain byte-identical identities and route to 3.8 on resume/restart. The version switch
does not re-run saved units, silently switch an old job, or enable automatic cloud egress.

## Other direct-provider candidates

Official standard synchronous prices checked on 2026-09-07, USD per million tokens:

| Candidate | Input / output | Practical fit and access |
|---|---:|---|
| [Qwen-MT-Flash](https://www.alibabacloud.com/help/en/model-studio/qwen-mt-flash) | Singapore $0.16 / $0.49; Frankfurt/Virginia $0.101 / $0.280 | Translation-focused; English/Japanese/Korean, glossary and domain controls. Separate Alibaba key required. |
| [Mistral Small 4](https://docs.mistral.ai/models/mistral-small-4-0-26-03) (`mistral-small-2603`) | $0.15 / $0.60 | System instructions, context and JSON output. Separate Mistral key required. |

Neither was called: no keys for these providers were supplied. No quality, response-time
or lower-refusal claim is inferred from pricing or generic benchmarks. Qwen-MT's
[translation API](https://www.alibabacloud.com/help/en/model-studio/machine-translation)
accepts a single user message and does not support the existing structured JSON contract,
so it needs a small dedicated adapter before a fair test. Qwen-MT-Flash is the next
translation-focused candidate to measure if an Alibaba key becomes available.

For private dialogue, confirm the selected service's data settings. Gemini's
[paid-service terms](https://ai.google.dev/gemini-api/terms) exclude product improvement
but permit limited abuse/legal retention. Alibaba's [product terms](https://www.alibabacloud.com/help/en/legal/latest/alibaba-cloud-international-website-product-terms-of-service-v-3-8-0)
require separate consent for model improvement and describe automated content checks.
Mistral's [current commercial terms](https://legal.mistral.ai/terms/commercial-terms-of-service/)
depend on product privacy choices; [API training opt-out](https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training)
is available in Admin Privacy. A paid API alone does not prove every provider excludes
training or that no logs are retained.

[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing): 3.8 Flash $0.75 / $3.75
through 2026-12-31; 3.1 Flash-Lite $0.25 / $1.50; 2.5 Flash-Lite $0.10 / $0.40.
Actual availability takes precedence over the advertised catalog.

## Integration and execution limits

The new authorization-key format contains dots. The app's validator now accepts it
while still rejecting whitespace, control characters and oversized keys. The key is
outside the repository and is never included in this report or prompts. Authenticated
model listing and real public-text inference succeeded through the configured system
HTTPS route; direct DNS failed here. The production adapter remains direct-only.

An additional real 3.1 Lite request exercised the production saved-transcript job and
output validator using two synthetic saved English cues. It succeeded in 35.347 s,
checkpointed both cues, and preserved the original media, prior subtitle and saved ASR
through a store restart. The request's token-price estimate was $0.000254. Only the
transport function was supplied with this environment's system HTTPS route; this does
not claim the unmodified direct-only worker can access Google from this restricted host.

The comparison preserves every attempted request, including a reservation before the
call. Completed and unknown-cost attempts are not automatically resent. Independent
review reproduced a concurrent-resume overwrite/double-call defect; the fixed runner
holds the application's kernel-owned lock from report read through final save. A
regression verifies that an overlapping invocation cannot call or alter accounting.
Commands were bounded to 500 seconds; no long unbounded command or private media was used.
