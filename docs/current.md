# Current work

- **Milestone:** reduce isolated short-caption flashes in new generated versions.
  Branch `fix/short-caption-hold`, based on main
  `c3995ac4e47d95a5c672ad8f15a416952eb99417` (PR #33). Restored local base
  `0e10f48b789076b200612a8c9759df01cc5dd067` has the exact main tree
  `6886b3a24df61ff70ed181e68287780df70a5ae7`.
- **Authorization:** continued product work and review/checks followed by merge are
  owner-approved. No new cloud inference, spending or final release approval is used.

## Bounded display hold

New **ko-readable-v2** presentations hold an isolated cue shorter than 834 ms to
start + 834 ms only if that entire interval is free before the next cue/video end.
Starts, text and canonical source/translation timing stay unchanged. Nested overlapping
turns and insufficient gaps keep their original display and warnings. No cue is dropped
or merged. Existing saved v1 and supplied tracks are not reflowed; no new free reflow
action or subtitle editing UI is added. New generation/saved-source translation still
has its existing model/API cost, so do not rerun a film solely to change its layout.

[Offline comparison](evidence/short_caption_hold.json) applied the product layout to
the 153 previously translated Qwen units, with zero model/API calls:

- All **214 display cues** and their text/start/unit mapping remain present.
- **12 short cues** reach 834 ms without new overlap. Short-duration findings fall
  **46 → 34**, reading-speed findings **12 → 11**, flagged cues **50 → 40**.
- Canonical cues and original raw evidence bytes remain unchanged. The remaining
  shortest cue is still 80 ms; this policy does not resolve crowded dialogue.

Local Linux/Python 3.12.14 checks: **56 tests pass, 6.949 s, no skips** using
`python -m unittest tests.test_subtitle_layout tests.test_caption_view tests.test_subtitles -q`.
They exercise boundaries/overlaps/fallback flags and actual FFmpeg/SQLite/ASGI lifespans
with synthetic model results. Interrupted translation resumes without redoing ASR or
rewriting its saved prefix. Stored v1/supplied tracks, new v2 output, caption selection,
+500 ms offset and position 2.25 survive two application lifespans unchanged.
This is not a real browser or network HTTP playback test. Fresh independent review and
the current PR's Ubuntu/Windows integration checks are recorded on that PR before merge.

## Preserved execution evidence

[Saved-source Gemini translation](evidence/qwen_saved_translation.json), PR #33:
153/153 Qwen units, 20 successful actual requests, 277.089 seconds, no ASR/alignment
or source fallback. Independent replay matched every request/response contract, source
interval and saved output. That was a product-function trial, not a whole application
job or automatic paid-request resume test. PR #33 passed
[CI 34545421407](https://github.com/seoji2005/media-server/actions/runs/34545421407):
261 Python tests per OS (one Windows-only skip on Ubuntu), nine DOM PASS suites and
synthetic Chrome startup/playback/restart.

[Continuous speech](evidence/qwen_continuous_dialogue.json), PR #32:
605.350 seconds, 22 actual Qwen spans. SIGKILL recovery reused six saved spans and
computed sixteen; full saved replay loaded no models. Completed-span CPU speech time
was 1,472.961 seconds, with 94.262 seconds (6.399%) in model loading. This does not
include failed attempts or establish uninterrupted wall time/target GPU performance.
Separate provided-caption ASGI/SQLite evidence translated 239 units with 30 actual
requests, zero ASR, preserved originals/two tracks/choice/sync/position and no paid
calls on reimport/restart.

The public raw archive `media-server-qwen-605s-2026-09-10.zip` preserves original inputs,
outputs, failed attempts and approved results in `qwen-text-approved/`. The additional
offline display comparison uses `short-caption-hold/`; it does not overwrite those
source or v1 outputs. Model weights and credentials are excluded.

## Remaining product gates

- Short-cue display correction does not repair retained ASR omissions near 424 seconds
  or translation findings: unsupported strengthening (unit 7), register drift
  (24–40, 57–59), mixed source/translation uncertainty (72–73) and ambiguous sense
  (124). These are selected AI text findings, not a listening-verified error rate.
  Use new material and controls for subsequent quality changes; preserve this recording
  as regression evidence. Do not remove acknowledgements or rewrite original timings
  merely to eliminate warning counts.
- Caption choice/Off/sync, provided-caption receiving, saved-source translation,
  exact-item paused entry, bounded PCM storage, scene search and opt-in local
  recommendations are integrated. Fetch remains separately owned; do not modify its
  adapter here or infer extension-to-Server acceptance from these checks.
- Natural long-video/multilingual content completeness, comfortable screen timing,
  Windows 11 / RTX 4070 SUPER installation/VRAM/inference remain unaccepted.
- Existing local Chrome EPERM and supplied-browser ERR_BLOCKED_BY_CLIENT limits
  remain. Do not use another browser/CDP/profile/proxy or move blocked inference to CI.
  Synthetic CI does not establish saved-caption screen quality.
- Conservative enhancement needs visual comparison/adoption; search and recommendations
  need actual viewing evaluation. No final release claim.
