# Current work

- **Milestone:** preserve completed Qwen probe spans before another expensive
  continuous-speech trial. Branch `feat/qwen-durable-checkpoints`.
- **Live base:** PR #30 merged at `48ea59076ccaae66f732433e74ffff9c08a46ed8`.
  Recovered local base `d584c7f` has the identical tree
  `bfd57c31008c94bd9cd1abd512e54338b03327fa`; publication preserves remote ancestry.
- **Authorization:** owner's continued multi-stage implementation, independent
  review and merge after successful checks; not final release approval.

## Current change

The offline [speech probe](qwen-subtitles.md#measure-local-speech-cost) now publishes
one atomic `checkpoint.json` after each new span. It binds raw parts to the input,
runtime, profile and content hash. A process killed during replacement recovers
the previous or new complete snapshot without relying on final exports. Old probe
directories remain readable with their original strict two-file verification.
Checkpoint verification/write time is separated from speech time.

Fresh independent review found that structurally malformed, hash-matching evidence
could be republished as resumable after rejection. The probe now applies the
existing product checkpoint validator before accepting saved parts. Rereview of
local `0917d8fe253c6625ed8ef004effb4abcbcdc1b1f`, tree
`d35a3c102ef198919d953aff605467b0697a27fd`, approved the fix. Remote implementation
`0f17022a7950c42e7a2a494b82885f30a7c417f4` has that exact tree.
[Executed evidence](evidence/qwen_probe_recovery.json) records process-kill tests,
rejected-evidence retry, valid-prefix retention and remaining model-call counts.
These are offline fixture checks with stubbed model calls, not new ASR quality.
Existing Windows/Ubuntu CI is the final integration gate; reconcile live PR checks.

Normal application jobs, model residency/call order, speech profile, DB and player
are unchanged. A local atomic checkpoint cannot survive removal of the whole
workspace by itself. Preserve the single raw checkpoint durably during expensive
trials, before an environment transition; never relabel its runtime identity.

## Actual speech evidence and execution limit

PR #30 passed independent review and final Windows/Ubuntu
[CI 34483515777](https://github.com/seoji2005/media-server/actions/runs/34483515777):
255 Python tests per OS (one Windows-only skip on Ubuntu), eight DOM suites and
actual synthetic Chrome startup/restart/preparation. It added optional timing only.
[Actual 35-second CPU results](evidence/qwen_speech_cost.json) retain two fresh
speech runs (83.515 and 88.591 seconds), identical parts hashes and full saved
recovery with zero model calls. Loading was about 11% in that short CPU case;
it did not justify changing model residency or claiming target-device speed.

The prior 605.350-second public dialogue attempt remains **incomplete**. Workspace
maintenance removed the runtime/raw outputs after the last observed 13 spans
through 364.500 seconds. There is no final cost, full recovery or long-input quality
acceptance. Those progress messages cannot recreate missing parts.

This milestone attempted to restore the official pinned CPU runtime. Execution
returned `network approval was cancelled before a decision was returned`; no model
weights remain in the local cache. The 605-second run was not restarted. No alternate
network route, browser or CI inference was used. Continue that trial only when the
required runtime/models and permitted execution are available. The recording was
previously studied public audio, not a new holdout. Translation remains separate.

## Reconciled product integration

- PR #28 caption choice/Off/sync settings and provided-caption receiving are merged.
  New jobs remain **Qwen3-ASR-1.7B + Qwen3-ForcedAligner-0.6B + Gemini 3.1 Flash-Lite**.
  Saved-source and foreign provided-caption translation avoid needless ASR.
- PR #29 exact-item entry merged after independent review and
  [CI 34470638573](https://github.com/seoji2005/media-server/actions/runs/34470638573).
  `#item` opens the identity-bound video paused with saved audio, watch position,
  caption/version/source/Off and offset. Rendition preparation remains explicit.
  [Saved sample HTTP evidence](evidence/item_entry_saved_playback.json) preserves
  five tracks, canonical bytes and all DB rows without inference.
- Independently owned Fetch main `8ce413012d97c0426fe448264fb4a9bfd604f87a` includes
  provided-caption handoff, transfer monitoring/stop and candidate address reconnect.
  Its adapter still opens the verified library root; exact-item adoption and foreign
  provided-caption translation end to end remain pending there. Do not edit Fetch.
- PR #27 bounded PCM storage remains integrated. Its
  [two-hour measurement](evidence/qwen_audio_memory.json) used real FFmpeg and model
  stubs: parent peak RSS 910.172 → 39.383 MiB, identical spans and verified recovery.
  This excludes model/child memory and is not two-hour natural-video quality.
- Saved-source translation, scene search, opt-in local recommendations and companion
  caption/library APIs remain integrated; do not recreate existing contracts.

## Remaining product gates

- Natural long-video/multilingual ASR, alignment, translation and subjective caption
  timing/readability; neither fixtures nor short samples establish this gate.
- Windows 11 / RTX 4070 SUPER 12 GB installation, VRAM, actual inference and recovery.
- Actual saved-caption screen review remains blocked by earlier local Chrome EPERM
  and supplied-browser ERR_BLOCKED_BY_CLIENT. Synthetic CI is not sample-quality
  review; do not retry with another browser/CDP/profile/proxy or inference in CI.
- Conservative enhancement requires visual comparison and adoption. Search and
  recommendations still need real viewing evaluation. Fetch's actual browser flow
  and exact-item adapter remain separately owned. No final release claim.
