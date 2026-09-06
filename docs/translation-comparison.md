# Local translation versus Gemini Flash

Owner requested a decision based on **time, Korean quality and censorship**, with an
API key and a $1 budget supplied on 2026-09-06. This is a developer comparison of permitted public text;
it does not authorize sending the private library or change the app's offline default.
**Current decision: retain local translation. Gemini adoption is blocked by incomplete
execution, despite better Korean phrasing in the one successful batch.**

## Frozen comparison

[Inputs](../tests/fixtures/translation_compare.json), frozen at `e56a004` before new
inference: 56 actual English ASR units from *Tears of Steel* (source/license in fixture),
12 authored ordinary dialogue probes, and 12 authored sensitive-content probes.
68 English / 12 Japanese. Keep the 12 known film development cases separate from the
remaining 44, which were also previously observed; neither is an independent holdout.
Authored cases cover idioms, negation, register, names, numbers, profanity, fictional
violence, non-graphic adult dialogue and health/trauma statements. They do **not** prove
performance on Japanese films, graphic sexual material or every provider restriction.

Compare existing MADLAD400 3B (`beam4`, batch2, CPU float32 here / target CUDA BF16)
with [`gemini-3.8-flash`](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash),
the stable Flash listed on 2026-09-06. Use explicit model ID and retain returned
`modelVersion`; no moving `latest` alias. Start with low thinking, structured JSON,
one candidate, 4096 output-token cap. Record any unsupported configuration, without
silently changing models or excluding that failed attempt.

[Offline request builder](../scripts/prepare_translation_compare.py) prepares 35
requests: seven 8-unit film batches repeated three times, two ordinary batches, and
12 separate sensitive cases. One sequential request at a time, no automatic retry.
The [execution script](../scripts/run_translation_compare.py) uses token counts and
reserves the entire documented 65,536-token model output limit before each billable
request, exceeding the requested 4096-token cap. Prior usage/reservations must be
deducted when explicitly continuing into a new exclusive output directory.
Record unknown-cost failures conservatively. Stop at the cap, preserving incomplete
coverage rather than reporting an unevaluated case as a pass.

The exact prompt is in the builder. Gemini receives source text plus adjacent context,
without current Korean output or evaluator notes; film context stops at gaps >2 s.
MADLAD uses its existing sentence-only adapter. This compares the proposed **subtitle
systems**, not equal-context model performance. Preserve IDs/timing and use identical
display formatting afterward. Reject duplicate/missing IDs and empty/truncated output;
record them before any fallback so source text cannot masquerade as good translation.

## Decision and limits

- **Quality first:** inspect all first-pass outputs, recording major meaning errors,
  omissions/additions, idiom/register/name errors and naturalness. Compare known film
  cases, remaining film dialogue and authored probes separately. Hide engine labels
  in the comparison sheet where possible; author judgments are not a human panel.
- **Censorship separately:** preserve `promptFeedback`, `finishReason`, available
  safety ratings and per-case coverage. Separate explicit provider blocks, prose
  refusals, unexplained softening/omissions and ordinary translation mistakes. A
  weakened word alone does not prove filtering. Retain the provider's documented
  [default safety behavior](https://ai.google.dev/gemini-api/docs/safety-settings);
  built-in restrictions remain. Do not reword blocked inputs to defeat a refusal.
- **Time/cost:** measure complete film-pass latency (three runs), request median/tail,
  tokens including thinking, failures and charged/estimated cost. Mark small-sample
  tails as descriptive. Existing local film translation was **210.354 s** on Linux CPU
  ([evidence](evidence/speech_twelve_minute.json)); no RTX speed comparison exists.
- Prefer Flash only if it materially reduces meaning/naturalness errors across the
  ordinary comparison groups without losing sensitive dialogue, and its measured
  delay/cost is acceptable. If results conflict, retain local and report the tradeoff.
  No unconditional cloud-default decision based on a few corrected examples. Private
  content still needs explicit egress approval; keep an offline path if cloud is adopted.

## Cost, privacy and current checkpoint

[Official pricing](https://ai.google.dev/gemini-api/docs/pricing), checked 2026-09-06:
standard 3.8 Flash text input $0.75 / output including thinking $3.75 per million tokens
through 2026-12-31. Request bodies total 70,809 UTF-8 bytes; output caps total 143,360
tokens. Treating request bytes as input tokens gives about **$0.59**, a rough conservative
planning estimate, not a measured bill or tokenizer guarantee. Owner-approved total experiment cap:
**$1**, enforced before calls using current pricing/counts. No search/tools/cache fees.

[API terms](https://ai.google.dev/gemini-api/terms): unpaid inputs/outputs may improve
Google products and be human-reviewed. Paid prompts/responses are not used for product
improvement, but limited abuse-prevention retention still applies. Use an owner's
properly configured developer project; review applicable use conditions before adoption.
Never claim zero retention. This experiment sends only the frozen public/authored text,
not video/audio, paths, history or private corrections. Keys must stay outside Git/logs.

The offline builder's 80 IDs, repetitions, sensitive-case isolation and payload allowlist
were checked with socket operations blocked (0 attempts). No production code changed.
[Saved local outputs](evidence/translation_local_baseline.json) retain all 80 baseline
translations. The additional 24 authored cases completed in **112.267 s**, one CPU run,
peak RSS **11,144.949 MiB**, zero Python network attempts and no adapter errors/refusal
messages. Weight loading is included in the first batch; runtime/import startup is separate.
Manual inspection found idiom errors (`auth_02/03`), omitted arrival duration (`auth_08`),
byte-token artifacts (`auth_09`), softened profanity (`auth_12`) and a missing “do not
shoot” command (`auth_21`). The last two do not by themselves establish censorship.
Do not equate no safety filter or successful generation with faithful translation.

## Actual API attempt · 2026-09-06

[Raw results, errors and accounting](evidence/translation_gemini_attempt.json):
3.8 model metadata and token counting succeeded; its first **8/80** dialogue units
translated successfully. The next generation returned HTTP **503**, and one explicit
continuation returned 503 again. The continuation deducted the entire previous
accounted amount and prioritized unique quality cases before timing repetitions.
No further 3.8 retry was made.

A separately recorded 2.5 Flash candidate (thinking budget 1024, text rates $0.30/$2.50
per million) failed token counting with **404**. ListModels still advertised it; a
minimal contents-only count also returned 404. This does not establish global model
retirement or an invalid key. Catalog-confirmed 3.7 Flash (low thinking, same verified
rates as 3.8) counted successfully but its first generation returned **503**. Stopped
at this real service blocker; no automatic retry loop or further model sweep.

| Evidence on the same first 8 English units | Local MADLAD | Gemini 3.8 Flash |
| --- | --- | --- |
| Translation elapsed | 56.523 s, CPU including first weight load | 14.689 s including network |
| Additional experiment token-count call | None | 13.764 s |
| Complete corpus | 80 baseline outputs | 8/80 outputs |
| Sensitive cloud probes | N/A | 0/12 executed; refusal rate unknown |

Gemini repaired the malformed Korean for wanting to be awesome in space and made
“I'm not freaked out by it” conversational. Dismissive “Whatever” became 마음대로 해
instead of 괜찮아. It also intensified “I'm freaked out” into 무서워 죽겠어, and the
robotics clause remains literal. These are author observations on saved ASR, not
independent human gold. No full-film speed, Japanese cloud quality, censorship rate,
RTX comparison or universal quality winner is established.

Success response usage priced at **$0.00164250**; three unmetered 503 responses retain
**$0.74275275** in conservative reservations. Total accounted **$0.74439525** is below
$1; **$0.25560475** remains under the existing approval. Reservations are **not a bill**;
actual invoice charges were not inspected. Count-only 404 attempts did not generate.

Fresh review found two execution-script bugs: malformed response containers could
skip recording the failed call, and JSON-escaped keys could bypass redaction. Fixed
and independently rechecked at `a4afd8c`; model/rate routing checked at `0cd885e`. Six stub
tests passed; adding the catalog-confirmed 3.7 rate entry was an author-checked data edit.
Tests/review do not validate Google availability or billing. Credential scanning passed;
the temporary key copy was removed after execution. No key or private library input
was committed, and the app remains offline by default.

Next: keep the local adapter; revisit the remaining frozen comparison when API service
works, respecting the remaining approved budget and retained unknown-charge reserves.
Do not rerun completed ASR or silently make private media use cloud translation.
