# Current work

- **Milestone:** selected Gemini 3.8 translation and language-aware manual captions.
  Branch `feat/selected-translation-and-captions`, based on main
  `4503550c3c59019c6b46da62d639ccaf305f0258` (PR #34).
  Local restored base `339ba3b592fd93a627c1e3a1aec52aaccb585ffe` has the exact same
  tree `11101fa3c913c728de593b3552c47ccc0b692a47`; remote publication preserves actual
  main ancestry, not the local recovery ancestry.
- **Authorization:** the owner approved the audit's next work and carried approval
  for implementation, checks, independent review and merging passing development
  changes. This is not final release approval. No new paid inference is needed here.

## Behavior

New ASR/retranslation jobs use Gemini 3.8 Flash with the evaluated v5 prompt,
strict target IDs, bounded source/translated context and low thinking. The new
`faithful-context-v5-flash38` profile leaves all six historical config strings,
prompts and identities unchanged, including Lite v5. Resume/restart uses a saved
job's model. No silent upgrade, automatic retry or fallback. The fidelity prompt
has not been revised to allow different euphemisms; the comparison's limitation
still applies. See [selection and counterevidence](translation-api-selection.md).

Manual subtitle import accepts an explicit language and SRT/WebVTT format, using
the existing bounded parsers. Korean/SRT remain the HTTP and UI defaults; choose
Japanese, English or unknown before opening a foreign caption file. Foreign/unknown
tracks can reuse the existing saved-text translation action without audio decoding,
ASR or alignment. Importing itself triggers no cloud work. Original uploaded bytes,
previous tracks, audio selection and viewing state remain separate. Companion
caption identity/deduplication and its original-file timebase remain unchanged.

The UI names the fixed model instead of offering a one-option model selector.
Language choice, file selection, disclosure and the explicit translation action
remain visible in subtitle preparation. This is a small form change, not a new player.

## Verification

Targeted Python tests: 35 passed / 8.078 s after correcting one new test's audio-bound
expectation (an unprepared in-range audio returns 409; the out-of-range case now uses
128). Existing tests remain unchanged in their runtime rejection behavior.
The first run was 34 pass / 1 failure, preserved in the Work log.

All npm DOM entry scripts pass after isolating the new manual-import fixture's
selected track from the next pre-existing fixture. Their HTTP/media are mocked.
The new import checks preserve language/format/audio and send only the import request.
Actual FFmpeg/SQLite/ASGI lifespans confirm source bytes, old VTT, selected caption,
+500ms offset, position and language survive restart; explicit translation uses 3.8
without constructing either ASR or local translation models. Translation is synthetic.
All six pre-change profiles were independently compared byte-for-byte locally.
Full Python integration: 268 tests / 61.850 s, 267 pass and one existing
Windows-only skip on Linux. Fresh fixed-commit review and remote CI are recorded on
the PR before development merge.
Local syntax and documentation-link checks pass. No fresh real-browser acceptance.

Independent review requested removal of one stale Playwright select operation and
found a pre-existing import completion race. Both are fixed: import owns its player
and caption-view version across the POST and refresh. Targeted subtitle/caption-view
DOM checks pass, including delayed POST/GET with an audio switch or newer sync choice.
Review of the corrected fixed commit and remote CI remain required before merge.

## Next and retained limits

Finish the current fixed-commit review/CI and development merge. Then reconcile the
Qwen/scene-search installation paths and Fetch's exact item-entry adapter against the
current Server API; no new Server entry API is needed. Fetch is a separate checkout
and any modification must reconcile its live work before publication.

Natural long-video/multilingual completeness, comfortable saved-caption screen timing,
Windows 11/RTX installation/VRAM/inference and conservative enhancement adoption remain
unaccepted. Existing short-caption hold, 605s Qwen recovery and provided-caption
translation evidence remain in Git history and docs/evidence; no samples were rerun.
Search/recommendations still need real viewing evaluation. No release claim.

Existing local Chrome EPERM and supplied-browser ERR_BLOCKED_BY_CLIENT limits remain.
Do not retry through other browsers, CDP, profiles or proxies, or move blocked model
inference into CI. Approved model-free Ubuntu/Windows browser CI is separate evidence.
