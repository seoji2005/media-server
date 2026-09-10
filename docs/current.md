# Current work

- **Milestone:** complete the restored 605-second Qwen speech/recovery trial and
  actual provided-caption translation. Branch `evidence/qwen-continuous-dialogue`.
- **Execution base:** PR #31 merged at `06d3537c83cc4cb171d4dd87c790af01033eccd2`.
  Recovered local `3d31d79de9d9ad3c885ae82ce35ba79437c84fdf` has its identical tree
  `f5d4d722b8eb4b33c43f821c995a2f2bbee45cbd`; publication preserves remote ancestry.
- **Authorization:** owner's continued implementation, independent review and merge
  after successful checks; latest explicit network approval restored runtime access.
  This is not final release approval. A later, narrower text-egress rejection remains
  outstanding below.

## Completed actual execution

[Numeric evidence](evidence/qwen_continuous_dialogue.json) binds the public input,
runtime, code tree and retained raw evidence hashes. The previously studied
IngCrowd two-speaker recording is not a new holdout. This new run used actual pinned
Qwen models on cloud CPU, four threads, and the unchanged product speech stage.

- **605.350 seconds, 22 contiguous spans, 153 source cues**, no unresolved spans.
  Coverage means the processing timeline is complete, not that all dialogue survived.
- SIGKILL after six committed spans left no final exports. Atomic checkpoint recovery
  reused those six unchanged and computed the remaining sixteen. Reopening all
  twenty-two saved spans produced identical parts with **zero model calls**.
- Completed-span speech time totaled **1,472.961 seconds**; model loading was
  **94.262 seconds (6.399%)**. This sum excludes restart delay, setup, checkpoint
  publication and any uncheckpointed work at termination. ASR inference dominated
  this CPU run; it does not justify a model-residency change or establish GPU speed.
- Fresh independent review recomputed hashes and phase sums, replayed saved parts
  through product validation with model/network tripwires, and approved execution
  and recovery evidence. No product code changed in this milestone.

Quality remains incomplete: overlapping reference `a216` and part of `a217` are
absent near 424 seconds. This is reference-text comparison, not independent listening.
Twenty source cues exceed seven seconds; the maximum is 28.24 seconds. Thirty
unique exact-match timing anchors had 0.040-second median and 1.010-second maximum
absolute endpoint differences; that selected subset cannot establish overall
alignment accuracy. Twenty-one boundary checks found no normalized suffix/prefix
repeat of at least four characters, which does not exclude semantic repetition.

The separate **provided-caption path** completed with actual Gemini requests:
239 Japanese reference annotations → 239 translated units, 30 requests, zero ASR
or local-model calls and no fallback. Reimport returned the existing track. SQLite
restart preserved two tracks, original media/VTT bytes, Korean VTT, source selection,
+500 ms offset and the 42-second watch position without another paid request.
Independent read-only review confirmed these bindings and canonical cue intervals.
The test used ASGI TestClient, direct job execution and a synthetic black-video
carrier with the public audio; it does not prove browser, socket playback, normal
background scheduling or Fetch end-to-end behavior. The 343 display cues include
173 review flags from overlapping/short annotations and layout limits; these are
not 173 translation errors or a readability acceptance.

## Narrow remaining execution block

A subsequent attempt to translate the **Qwen-derived** 153 source units was rejected
by automatic approval review: generic network approval was not considered explicit
authorization to send potentially private transcript text to Google Gemini.
The actual source is the hash-verified public recording above. Local output remains
incomplete with zero saved request/response records and translated units; no matching
live process remained. This is not provider-side proof of zero receipt. No retry or
alternate route was attempted after rejection. Obtain explicit approval naming this
public-text payload and Google Gemini destination before continuing that step.
Do not conflate it with the already completed provided-caption translation.

The earlier interrupted 605-second trial remains incomplete historical evidence in
[speech cost](evidence/qwen_speech_cost.json); missing raw parts were not reconstructed
or relabeled. This restored run has a new recorded runtime identity. Its public raw
inputs, checkpoints, responses and test database are retained outside Git in
`media-server-qwen-605s-2026-09-10.zip`, without model weights or credentials.

## Reconciled integration

- PR #31 durable probe checkpoints passed independent review and
  [CI 34486584884](https://github.com/seoji2005/media-server/actions/runs/34486584884):
  261 Python tests per OS (one Windows-only skip on Ubuntu), nine DOM PASS suites
  and actual synthetic Chrome startup/restart. The DOM footer's “eight” is stale.
- PR #28 caption choice/Off/sync and provided-caption receiving are merged. New
  jobs remain Qwen3-ASR-1.7B + Qwen3-ForcedAligner-0.6B + Gemini 3.1 Flash-Lite.
  Existing saved-source/provided-caption translation avoids unnecessary ASR.
- PR #29 exact-item entry preserves identity-bound viewing settings and opens
  paused; rendition preparation remains explicit. Its existing
  [saved sample evidence](evidence/item_entry_saved_playback.json) remains valid.
- Separately owned Fetch main last observed at
  `8ce413012d97c0426fe448264fb4a9bfd604f87a` includes caption handoff, transfer
  monitoring/stop and candidate address reconnect. Exact-item adapter adoption
  and actual foreign-caption flow through Fetch remain separately owned; do not edit.
- PR #27 bounded PCM storage, scene search, opt-in local recommendations and
  companion caption/library APIs remain integrated; do not recreate their contracts.

## Next product gates

- After the narrow approval, translate saved Qwen text without repeating speech;
  inspect retained omission/long-cue evidence before selecting a bounded change.
  Do not tune prompts repeatedly on this previously studied recording.
- Natural long-video/multilingual content completeness and subjective timing,
  translation and readability remain unaccepted. Cloud CPU is not Windows 11 /
  RTX 4070 SUPER installation, VRAM, inference or recovery evidence.
- Actual saved-caption screen review retains the earlier local Chrome EPERM and
  supplied-browser ERR_BLOCKED_BY_CLIENT limits. Do not retry through another
  browser/CDP/profile/proxy or move blocked inference into CI.
- Conservative enhancement needs visual comparison and adoption. Search and
  recommendations need actual viewing evaluation. No final release claim.
