# Local translation versus Gemini Flash

Owner requested a decision based on **time, Korean quality and censorship**, with an
API key available if needed. This is a developer comparison of permitted public text;
it does not authorize sending the private library or change the app's offline default.
**Gemini has not run. No winner has been selected.**

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
Before execution, confirm key/project access and an owner-approved spending cap;
use token counts and reserve the maximum output cost before each billable request.
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
planning estimate, not a measured bill or tokenizer guarantee. Proposed experiment cap:
**$1**, enforced before calls using current pricing/counts. No search/tools/cache fees.

[API terms](https://ai.google.dev/gemini-api/terms): unpaid inputs/outputs may improve
Google products and be human-reviewed. Paid prompts/responses are not used for product
improvement, but limited abuse-prevention retention still applies. Use an owner's
properly configured developer project; review applicable use conditions before adoption.
Never claim zero retention. This experiment sends only the frozen public/authored text,
not video/audio, paths, history or private corrections. Keys must stay outside Git/logs.

No `GEMINI_API_KEY` or `GOOGLE_API_KEY` was available. No external inference was called.
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

Next: obtain the Gemini key and $1 spending approval, run the frozen requests, validate
coverage and inspect paired outputs. No API integration or model replacement until this
comparison has actual results. Existing ASR and app tests need no repeat for this
fixture/offline-builder-only checkpoint.
