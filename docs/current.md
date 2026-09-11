# Current work

- **Milestone:** complete actual Gemini translation of the 153 saved Qwen units from
  the public 605-second dialogue. Branch `evidence/qwen-saved-text-translation`.
- **Execution base:** main `e14f762ec912a7cf0a2e15fe22aa85909c11840c` (PR #32).
  Restored local `7cf758ac1780d5f0b3cb2a70eda6d2e0131c29ce` has its exact tree
  `6bf0ba2adba1a96b7ca584367ae554f301a31876`. Product code and prompts are unchanged.
- **Authorization:** the owner explicitly approved sending these 153 public Qwen
  text units to Google Gemini after the prior automatic-review rejection. Existing
  review/checks followed by merge approval persists; no final release approval.

## Actual saved-source translation

[Translation evidence](evidence/qwen_saved_translation.json) records the fixed source,
code, approved destination, actual response hashes and layout checks. The run crossed
midnight UTC on September 10–11 and completed in **277.089 seconds**:

- **153/153 units, 20 successful actual Gemini requests**, no request failure,
  source fallback, ASR or alignment call. No local speech runtime was reinstalled.
- Every canonical source interval and the original speech checkpoint bytes remained
  unchanged. All saved response counts/order/IDs and resulting texts were revalidated.
- Product layout generated **214 display cues** representing all 153 source units.
  Recomputed layout and VTT match saved output. The longest display is 6.886 seconds,
  but the shortest is 0.080 seconds. **50 cues require review**: 46 short-duration,
  12 reading-speed and 2 layout-limit flags (codes can overlap).
- Raw responses report 37,054 total tokens: 21,137 prompt, 3,407 candidate and 12,510
  thinking tokens. This is recorded provider usage, not a price estimate.

Execution completeness is not final caption quality. The prior reference-based
ASR omissions near 424 seconds remain. Product display subdivision uses proportional
allocation inside each unchanged source interval; it is not new word alignment.
Fresh independent review accepted execution/evidence after replaying all 20 saved
responses with network/speech tripwires and matching request hashes, outputs and VTTs.
Selected textual findings remain (zero-based source indices): unit 7 adds an unsupported
superlative; ranges 24–40 and 57–59 drift toward polite Korean. Units 72–73 turn uncertain
source into explicit meat references during a tea discussion, so attribution is mixed.
Unit 124 has an ambiguous sense choice. These are selected AI textual findings, not
a listening-verified error rate. Source 117 already contains its problematic duration;
do not attribute that duration to new Gemini invention.

The one-off helper called unchanged product source-unit, Gemini translation and
layout functions; this is not a complete application job, database integration,
Fetch flow or browser playback test. It checkpoints started requests, returned
responses and successful batches, but does not implement or test automatic resume.
A helper setup error occurred before any request; its failed record was preserved,
and only the helper's speech tripwire target was corrected.

## Preserved earlier results

[Continuous speech evidence](evidence/qwen_continuous_dialogue.json) remains intact:
605.350 seconds, 22 actual Qwen spans, SIGKILL recovery reusing six saved spans and
computing sixteen, then full saved replay with zero model calls. Completed-span
CPU speech time was 1,472.961 seconds, including 94.262 seconds (6.399%) loading.
The earlier lost/interrupted run was not relabeled as complete.

The separate provided-caption ASGI/SQLite trial translated 239 reference units with
30 actual requests and zero ASR calls. Reimport/restart preserved source/media bytes,
two tracks, source selection, +500 ms offset, position 42 and Korean VTT without
another paid request. This remains distinct from the new Qwen-text function trial.

The public raw archive `media-server-qwen-605s-2026-09-10.zip` preserves both stages,
the earlier rejection and failed attempts, original inputs and outputs. The new
approved result is in `qwen-text-approved/`; prior files were not overwritten.
Model weights and credentials are excluded. Workspace maintenance removed the old
scratch copy; the saved archive supplied the original speech without rerunning it.

## Integrated product and remaining gates

- PR #32 passed independent review and
  [CI 34493997333](https://github.com/seoji2005/media-server/actions/runs/34493997333):
  261 Python tests per OS, one Windows-only skip on Ubuntu, nine DOM PASS suites
  and actual synthetic Chrome playback/startup/restart. Its product code is the
  unchanged execution baseline here; current PR checks are reported on the PR.
- Caption choice/Off/sync, provided-caption receiving, saved-source translation,
  exact-item paused entry, bounded PCM storage, scene search and opt-in local
  recommendations remain integrated. Do not recreate existing contracts.
- Fetch remains separately owned. This Work does not change its adapter or claim
  actual extension-to-Server playback acceptance from these tests.
- Next quality work should address the retained short-cue and translation findings
  with new material and controls, rather than repeatedly tuning this same recording.
  Do not silently delete short acknowledgements, reconstruct omitted speech or
  rewrite original timings merely to remove flags.
- Natural long-video/multilingual content completeness and subjective reading/timing
  remain unaccepted. Windows 11 / RTX 4070 SUPER installation, VRAM and inference
  still need target-device evidence.
- Existing local Chrome EPERM and supplied-browser ERR_BLOCKED_BY_CLIENT limits
  remain. Do not retry through another browser/CDP/profile/proxy or move blocked
  inference to CI. Synthetic CI does not establish saved-caption screen quality.
- Conservative enhancement needs visual comparison/adoption; search and
  recommendations need actual viewing evaluation. No final release claim.
