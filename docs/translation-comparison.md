# Local translation versus Gemini Flash

Owner requested a decision based on **time, Korean quality and censorship**, with an
API key and a $1 budget supplied on 2026-09-06. This is a developer comparison of permitted public text;
it does not authorize sending the private library or change the app's offline default.
**Current decision: retain local translation pending complete comparison. API access
recovered in the [post-payment diagnosis](#post-payment-diagnosis); 16/80 units completed,
with Japanese and sensitive probes still untested.**
The [native-tokenizer repair](#native-tokenizer-repair--2026-09-07) fixes a confirmed
local character defect; it does not change that engine-selection decision.

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

This section records the initial failures, before the later recovery below.

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

The owner then supplied a replacement credential and requested one attempt. Model
metadata returned 200 and token counting succeeded (433 tokens), but the previously
failed 8-unit generation returned 503 again after 16.455 s. No additional translation
completed. This is not an invalid-key response; the cause of the 503 is unconfirmed.
The temporary credential copy was removed, and no further call fits the retained
maximum-output reserve within the original $1 approval.

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

Success response usage priced at **$0.00164250**; four unmetered 503 responses retain
**$0.99018075** in conservative reservations. Total accounted **$0.99182325** is below
$1; **$0.00817675** remains under the existing approval. Reservations are **not a bill**;
actual invoice charges were not inspected. Count-only 404 attempts did not generate.

Fresh review found two execution-script bugs: malformed response containers could
skip recording the failed call, and JSON-escaped keys could bypass redaction. Fixed
and independently rechecked at `a4afd8c`; model/rate routing checked at `0cd885e`. Six stub
tests passed; adding the catalog-confirmed 3.7 rate entry was an author-checked data edit.
Tests/review do not validate Google availability or billing. Credential scanning passed;
the temporary key copy was removed after execution. No key or private library input
was committed, and the app remains offline by default.

## Post-payment diagnosis

The owner reported a KRW 16,000 payment and asked for the cause. Two requests using the
replacement credential then returned **200 / STOP**: plain `Reply only OK.` in **12.408 s**,
and the previously failed `tos_08..15` translation in **13.201 s**. All eight IDs and
nonempty translations validated. [Evidence](evidence/translation_gemini_diagnosis.json).
No automatic retry or private input was used; the temporary credential copy was removed.

**Established:** access currently works, including the same failed public dialogue,
context and JSON schema. The translation output cap changed from 4096 to 1024, so this
was not an exact controlled replay. There is no evidence that a rejected credential,
unsupported Korean output or content filtering explains the earlier 503s.
**Unresolved:** billing activation versus a transient provider recovery. The earlier
runner discarded the error bodies, and no billing console or invoice was accessed.
Do not claim that payment caused the recovery merely because it preceded it.

[Google's error guide](https://ai.google.dev/gemini-api/docs/api-errors) distinguishes
503 service unavailability from billing prerequisites, authentication and quota errors.
[Billing documentation](https://ai.google.dev/gemini-api/docs/billing) says keys inherit
their project's billing account, Prepay needs a positive balance, and tier updates
usually reflect within 10 minutes after successful payment. The owner's account status
must be checked in AI Studio to distinguish payment confirmation from credit activation.
The public status page did not expose usable incident data in this environment.

The experiment now retains only fixed error categories and allowlisted API status values
from a bounded 16 KiB error body. Provider messages, headers, account IDs and credentials
are still discarded. Fresh review of `c04761c` found that error-stream cleanup could
skip the failed-call report; fixed and rechecked at `59b00c3`. **9 focused tests passed**,
including malformed/private bodies and cleanup failure. This changes only the developer
experiment; the app's local adapter and privacy boundary are unchanged.

The two diagnostic requests used explicit output caps 128/1024, reserving those caps
plus input margin under the remaining approval. Previous full-model reservations were
not released. Added successful usage priced at **$0.00136275**; all successful responses
now total **$0.00300525**. With old unknown-charge reserves, accounted total is
**$0.99318600**, leaving **$0.00681400** under the original $1 approval. These are token-price
calculations and conservative reservations, **not invoice charges**. Reporting roughly
$0.99 as a budget blocker hid how small the observed usage was; do not imply it required
the owner's subsequent payment. No further payment is justified by these measurements.

Next: retain local pending the incomplete comparison; use the saved 16 cloud outputs and
80 local baselines. Before more calls, reconcile old reservations against the documented
request limits or billing usage. Do not reset the $1 cap because the owner funded an account,
rerun completed ASR, or silently make private media use cloud translation.

## Native tokenizer repair · 2026-09-07

At code `13f8a6d` (base `cfb340a`), local MADLAD now uses its native SentencePiece
encoder and decoder. The pinned fast tokenizer has no byte-fallback decoder and
also converts some rare input characters to UNK. Native decoding alone is insufficient:
fast input encoding treats literal `<0xEC><0xB0><0xBC>` as byte IDs; switching both
sides preserves that literal spelling. No text replacement rule is involved.

[Recorded controls, generated outputs and limits](evidence/translation_native_tokenizer.json):

- Restored the same `fa184c675da0b5c9e1c8694fccd4e12e2d422094` public weights;
  all **11,761,587,872 bytes** matched their published SHA256 before inference.
  Initial download hit disk exhaustion; partial data survived, sequential continuation
  was interrupted, and one bounded parallel-range continuation finished and verified.
- The [production tokenizer check](../scripts/check_translation_tokenizer.py) retained
  identical prefixed input IDs for all **80** existing cases. Four controls preserved
  rare Hangul, a rare Han character, emoji and literal byte-token spelling, with no UNK.
  An independent fast-tokenizer negative control made that check fail with exit 1.
- Actually generated **36** outputs: the 12 known film development sentences plus all
  24 authored probes. Each generated token sequence was decoded by both tokenizers;
  **35 outputs were identical**. `auth_09` changed from
  `RAM이 충분해요. GPU 메모리가 가득 <0xEC><0xB0><0xBC>어요.` to
  `RAM이 충분해요. GPU 메모리가 가득 찼어요.` The observed three byte IDs decode to `찼`.
- A fresh process then loaded the modified production adapter and regenerated
  `auth_09` and the unchanged `auth_10` control; both matched the expected native output,
  without warnings. This checks actual native generation, beyond decoding saved IDs.

Commands were `python -m unittest discover -s tests -q`, the tokenizer check above,
`OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 timeout 540 python measure_madlad_decoder.py`,
and the analogous bounded `verify_native_generation.py` probe. The last two were
session-local measurement scripts. The 36-case probe called baseline `translate_chunk`
with existing fixture text, captured IDs at `decode`, and decoded those same IDs through
native T5. The second probe called the changed `translate_chunk`/`LocalModels` adapter
in a fresh process. Neither loaded ASR or touched the user's database/media.

Linux CPU, Torch 2.8 float32, beam four, batch two, four threads: **167.009 s** for the
36-case probe and **17.688 s** for the fresh two-case check, including weight loading
but excluding import startup/cleanup. Both exited 0 with zero Python socket attempts;
this is not an OS network trace or an RTX benchmark. Full Python validation passed
**150 tests** in 43.339 s (one Windows-only skip). `pip check` passed. Existing Torch
and fast-tokenizer deprecation/performance warnings were retained in the probe logs.

The new pipeline/package identity rejects an older partial translation before
inference. Independent fixed-code review verified that saved batches, completed
captions, original transcripts and original media remained identical after restart.
Setup now requires `spiece.model` and explicit protobuf; reinstall model requirements
if missing. Existing ready captions remain available; the repair applies to new jobs.

These are previously observed development inputs, not a held-out quality benchmark.
For example, `tos_52` still mistranslates “ad-lib” as advertising, and awkward wording,
idiom/register errors and omissions remain. The repair makes no general Korean quality,
provider-censorship or Windows 11/RTX/CUDA claim. The local engine remains the default.

## Bounded decoding comparison · 2026-09-07

[Full inputs/outputs and timing](evidence/retranslation.json) retain three actual
sentence-split probes and two fixed decoding candidates on eight previously observed
failure/control inputs. Same native MADLAD revision, Linux CPU float32, four threads;
no ASR rerun or network attempt. No candidate was adopted.

Splitting `auth_08/09/21` at their explicit Japanese sentence marks restored the
shooting prohibition in `auth_21`, but `あと十分で着くよ。` became “충분히 멀리 떨어져 있다.”
instead of arriving in ten minutes. More output did not establish correct coverage.
Beam eight also restored `auth_21`, retained the `auth_08` omission and left the idiom
errors; `Jae` changed spelling. Length penalty 1.3 restored `auth_21` but rendered
`auth_08` as “충분히 빨리 갈 수 있을 거야”, still losing the ten-minute meaning. The current
beam-four/length-one behavior remains unchanged.

The bounded commands were `timeout 120 python probe_sentence_translation.py`
(**22.539 s**, three paired sentence calls) and `timeout 300 python
probe_translation_search.py` (**51.296 s** beam-eight, **40.156 s** length-1.3), with
`OMP_NUM_THREADS=4 MKL_NUM_THREADS=4`. All exited 0. Scripts were session-local; the
search probe changed only `generate` kwargs over the unchanged production adapter and
fixed eight fixture IDs. Weights loaded in the split run and first search candidate,
then stayed loaded for the second. These are not equal-work speed benchmarks or a
held-out Korean quality evaluation.

## Reusing saved ASR · 2026-09-07

At local reviewed code `6d27d9a`, a selected generated version can be translated again
without decoding audio, loading VAD/ASR or overwriting earlier versions. A new job copies
its verified transcript bytes/hash and audio index, and freezes the translation-only
configuration before queueing. Missing-config guards remain intact. Normal existing
jobs retain exactly the previous pipeline identity; ASR-only changes do not invalidate
retranslation. Changed MT setup requires a new attempt from the same selected source.

Actual `probe_retranslation_api_final.py` ran the production CLI/server and worker
against synthetic four-second H.264/AAC media with two saved authored fixture sentences.
Only translation weights were present; ASR dependency imports and external Python
socket connections were blocked. The real MADLAD job succeeded in **16.289 s**, with
zero such attempts, zero ASR spans and a zero-byte server log. A store restart preserved
the selected old job, original transcript/VTT, Korean VTT and original media. This is
actual translation and API integration, not a new ASR-quality or browser-playback run.
The earlier pre-review execution also succeeded in 16.070 s; the final run verified
binding after separating the translation profile from the ASR profile.

Linux Python validation: **156 tests**, 42.571 s, exit 0 (one Windows-only skip).
Subtitle DOM checks passed; five focused post-review regressions passed in 0.849 s.
Fresh independent review verified v5→v6 migration/rollback, old-row preservation,
source/input/ASR-counter tamper rejection, no-ASR pause/recovery/resume, restart rollback
and exact compatibility of normal model identity. Its MT-profile and browser-test
findings were fixed and rereviewed without remaining findings. Real browser behavior
is gated by the PR's Linux/Windows CI. Target Windows 11/RTX remains unavailable.

## Contextual Qwen comparison · 2026-09-07

**Keep MADLAD as the app default; Qwen3-4B-Instruct-2507 is not adopted.** The fixed
Qwen candidate completed all 80 existing inputs, but still corrupts clock time,
misreads an offer to carry something, and produces awkward Korean. Restoring one
previously omitted command is useful evidence, not enough to establish a replacement.
MADLAD's existing meaning errors remain unresolved.

The [saved evidence](evidence/translation_qwen_candidate.json) contains all actual
candidate outputs, the exact saved baseline outputs, runtime/hash records and per-case
ratings. One fresh AI rater assessed four fixed packets with engine labels randomized
per case. It preferred MADLAD on 29 cases, Qwen on 17, and tied 34. Cases with a major
meaning error were 13 for MADLAD and 9 for Qwen; on the 56 film rows alone they were
6 and 7. Fewer major errors on this sample did not establish better overall subtitles.
Preferences also consider natural Korean, and a tie may mean both versions are flawed.
These are qualitative judgments on previously seen development cases, not a human
panel, calibrated quality score or adoption approval. Ambiguous ASR fragments,
repeated utterances and the lack of audiovisual context limit the judgments.

[Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) is an
Apache-2.0, non-thinking Qwen3 model supported by the existing Transformers 4.57.1.
Revision `cdbee75f17c01a7cc42f958dc650907174af0554` was downloaded in 106.56 s;
all three weight shards and the tokenizer matched their published SHA256 hashes.
Other downloaded file hashes are retained as well. No production dependency or model
selection changed. Qwen3.5 requires a newer runtime and remains untested here.
HY-MT1.5 was excluded before download because its
[own license](https://huggingface.co/tencent/HY-MT1.5-1.8B/raw/main/License.txt)
excludes South Korea from its permitted territory.

The [offline probe](../scripts/probe_qwen_translation.py) reads only the fixed public
fixture, verifies model weights, disables remote code and blocks Python socket connects.
It reuses the frozen Gemini prompt and adjacent context, one target per request, without
existing Korean output or evaluator notes. This compares subtitle systems: MADLAD's
saved baseline has no adjacent context. Its 36 previously native-decoded outputs replace
the corresponding older outputs; the other 44 saved film outputs are reused.
These are all observed development inputs, not a new holdout.

The model's sampling defaults were fixed before inference: temperature 0.7, top-p 0.8,
top-k 20, min-p 0, one seed per fixture ID, batch 1. The experimental output cap is
256 tokens. There was no per-case prompt tuning, output repair or regeneration to
improve wording. Structured output validation passed for **80/80**, with EOS
termination, nonempty matching IDs and zero Python network attempts. That verifies the
response structure, not semantic quality or OS-wide network isolation.

| Linux CPU BF16 run | Cases | Generation sum | Complete run |
| --- | ---: | ---: | ---: |
| Authored ordinary/sensitive | 24 | 380.810 s | 396.925 s |
| Film first half | 28 | 436.150 s | 445.243 s |
| Film second half | 28 | 358.785 s | 368.150 s |

Each run used four Torch/OMP/MKL threads. Two groups overlapped on the shared eight-core
cloud CPU; their sums are not sequential full-film latency or an equal-work MADLAD speed
comparison. Complete-run time includes hash verification, runtime import and model load.
Peak process RSS was 8,169.598 MiB; this is not GPU memory or target RTX evidence.

An initial FP32 run was stopped after six saved outputs because each took 31–43 s.
Its checkpoint remains incomplete and the external exit was 130; forced termination
did not execute the script's final report update. The same six BF16 outputs were
identical, taking 83.794 s versus 213.165 s in FP32, excluding setup in both sums.
Those BF16 pairs ran before concurrent inference began. The remaining BF16 cases are
the candidate evaluation; the incomplete FP32 pass is not counted as extra coverage.

| Probe | Candidate observation |
| --- | --- |
| `auth_06`, polite workplace request | Restores the apologetic request more faithfully |
| `auth_08`, 5:15 and arrival in ten minutes | Includes ten minutes but renders the clock as `오시십분 십오분` |
| `auth_11`, offer to carry something | Renders it as `가자고 해?`, changing the action |
| `auth_21`, do not shoot the doctor | Restores the prohibition and doctor identity |

The 12 authored sensitive examples produced translations without an explicit prose
refusal. Profanity remained weakened and some meaning errors persisted; this does not
establish censorship or performance on graphic material. No private input, API key,
cloud inference, new ASR run or target Windows/RTX execution was used.

The probe ran at code `6ff038c`; the initial FP32 checkpoint used `4435569`.
Commands used `timeout` (480 s for authored, 540 s per film half), four OMP/MKL threads,
the existing model-runtime Python and explicit `--precision bfloat16`. The initial
pass used `float32`. Exact command form, hashes and failed preparation/stop attempts
are retained in the evidence. Fresh independent review approved the probe and
reconstructed all 80 request hashes without rerunning inference. Local `harness.py
check` and `git diff --check` passed; the PR's normal Linux/Windows product and browser
CI remains the integration gate. This experiment does not exercise Qwen in the app.

## Qwen3.5 Q6_K comparison · 2026-09-07

**Do not adopt the evaluated Qwen3.5 subtitle system; keep MADLAD and its known
limitations.** All 80 fixed inputs produced a response, but only **64/80** met the
unchanged matching-ID JSON contract. Sixteen returned code fences or another JSON
shape. All reported `finish_reason=stop`; none hit the 256-token cap. No output was
repaired or regenerated. The [evidence](evidence/translation_qwen35_candidate.json)
retains responses, invalid IDs, baseline text, ratings, pins and execution limits.

One AI reviewer assessed randomized concealed A/B labels: **MADLAD preferred 47,
Qwen3.5 12, tied 21**. Major-error cases were **11 / 27**, respectively. The reviewer
had already reviewed the runtime code and knew the candidate identity, so this was
not a fully isolated linguistic review or human panel. It judged translation content
inside wrappers; structural failures were counted separately. Ambiguous/repeated ASR
fragments, no audiovisual context and judgment-dependent severity limit these counts.
They must not be treated as interchangeable with the earlier reviewer's scores.

The candidate fixes `auth_08` to `5시 15분. 10 분 뒤에 도착해.` but returns Japanese
for the Korean targets `auth_11` (`持っていきましょうか`), `auth_21`
(`撃つな！その人は医者だ！`) and `auth_23` (`コンドームある？`). Valid JSON therefore
does not establish target-language correctness. Neither these errors nor profanity
changes establish censorship; the authored sensitive cases are fictional/non-graphic.

Only 4.8 GiB of disk space remained, so the previous weights and reports were preserved
and an isolated [Unsloth Q6_K conversion](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)
was evaluated instead of adding the full original weights. Revision
`e87f176479d0855a907a41277aca2f8ee7a09523`, file `Qwen3.5-4B-Q6_K.gguf`
(3,525,956,768 bytes), matched published SHA256
`fdedd781c9ce676ab66b018ca247ff78e8a33c98098a822c1e2d5075e7718f66`.
The weight plus README download completed in 56.821 s. The conversion names the
Apache-2.0 Qwen3.5-4B base; its exact upstream conversion-source revision was not
independently established. This is evidence about this pinned artifact.

The [probe](../scripts/probe_gguf_translation.py) uses the verified official
[llama.cpp b10835 Linux CPU release](https://github.com/ggml-org/llama.cpp/releases/tag/b10835),
commit `b74f590eafec2fafc6e0e98ee93b2e5d3efa9042`. Archive and runtime file hashes
are retained. It sends the same frozen public fixture/prompt/adjacent context as the
earlier Qwen comparison to a loopback server, with local weights, `--offline`, disabled
Web UI/proxies and an ephemeral API key. Python records zero external connection
attempts; it cannot observe native C++ syscalls. A `strace` preflight failed with
ptrace EPERM (exit 1), and was not retried or bypassed. No OS-wide egress claim is made.

The native chat template has thinking disabled. The fixed
[Qwen non-thinking settings](https://huggingface.co/Qwen/Qwen3.5-4B#instruct-or-non-thinking-mode)
are temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5 and repetition
penalty 1.0, with a 256-token experimental cap and the existing per-ID seeds.
Each run uses four CPU threads, one server slot, a 2,048-token context and no prompt
cache reuse (all reported cached-token counts are zero). MADLAD's same 36 native
replacements plus 44 saved film outputs were reused without ASR/MT execution.
Context, quantization, runtime and sampling differ: this is a subtitle-system comparison,
not an isolated architecture or quantization experiment.

| Linux CPU run | Inputs | Valid structure | Request sum | Complete run |
| --- | ---: | ---: | ---: | ---: |
| Authored ordinary/sensitive | 24 | 17 | 291.562 s | 296.522 s |
| Film first half | 28 | 24 | 351.795 s | 357.057 s |
| Film second half | 28 | 23 | 318.565 s | 323.480 s |

Two groups overlapped on the eight-core cloud CPU. These sums are not sequential
full-film latency or a fair speed ranking against MADLAD/Qwen3. Native peak RSS and
GPU VRAM were not measured. All three probes completed their inputs but exited **1**
because of response validation failures; all owned servers shut down with exit **0**.
Every invocation had a 540-second outer timeout plus startup/request/group/cleanup
limits. The complete command form and raw report hashes are retained in the evidence.

Authored execution used `99ab889`; film groups used reviewed `cfa7836`. Fresh code
review found that optimized Python could disable assertions and failed HTTP/JSON
requests could lose diagnostic bodies/case IDs. Both were fixed without changing
generation settings or repeating inference. Optimized execution was actually rejected;
isolated reviewer mocks retained HTTP 503 and malformed JSON evidence. Local syntax,
documentation-contract and whitespace checks passed; normal Linux/Windows product
and Chrome CI gates the PR. No production model/dependency changed, private input,
cloud inference, app Qwen integration or Windows 11/RTX inference was used.
