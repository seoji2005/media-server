# Current work

Milestone: `feat/subtitle-search-pages`, based on live Server main
`487c210e5f504eda67c521abdc89f0758b1a4250` (PR39 merged). Restored local base
`5df91c578b0b83f65a9c3bddc23848257dda2920` has complete tree
`210cd57e69fdb90b1f31bba7508ef7c80d7b9661`; publish using actual remote ancestry.
Fetch main stays `0d6aa28a4a0c6944c053e3d63e150908b44b9175`. Both repositories had
no open PR at start. Owner implementation, finite verification, independent review
and passing development merge approvals continue; release is separate.

## Delivered and current change

Gemini 3.8, foreign SRT/VTT import/retranslation, shared Qwen/scene installation pins,
exact Fetch item entry, bounded preview/scene preparation, local titles/Unicode library
search and bounded subtitle status recovery are merged. PR39 passed independent
review, Ubuntu/Windows CI34595475887 and desktop/mobile screenshot inspection.

Caption search showed only the first 50 matches, leaving later scenes inaccessible
for common dialogue. It also treated cue line breaks/repeated whitespace literally.
The new page controls expose every match in groups of 50, with total/range and keyboard
focus. Normalization joins whitespace inside one cue for matching only; original
caption text/timing/output is unchanged. It does not join separate cues or infer
meaning. Selecting a result returns the video into view at the adjusted native time.

Query edits invalidate old buttons immediately before debounce. Page, caption, Off,
audio and item transitions cannot use retained buttons to seek a newer view. Paging
only renders results; existing completed seeks save viewing position. Search remains
memory-only, with no new endpoint, DB schema, ranking signal, inference or egress.

## Verification and next action

- Old base reproduced the first-50 ceiling (fixture exit 1); new 115-result DOM
  navigation, last-match seek, whitespace/literal text, keyboard focus, stale query/
  page guards and existing Off/item/track cases pass. All 11 DOM scripts passed.
- Chrome verification imports an actual 115-cue VTT into the existing synthetic
  20-second video on the restart phase, shifts it +500 ms, pages to the final group
  and seeks/saves its last native cue. Existing caption output must remain identical.
  Desktop/mobile screenshots and no query/inference requests are checked.
- Run syntax/diff/docs checks, freeze the source, obtain fresh independent review
  of navigation/preservation, then inspect the fixed-HEAD Linux/Windows CI and screens
  before development merge. CI observation is capped at 10 minutes/10 polls and each
  CI job at 10 minutes; do not rerun an unchanged failure without new evidence.
- DOM is mocked HTTP/media; Chrome's short synthetic captions test navigation, not
  natural long-speech quality. No Python product or server behavior changed.

For GitHub PNGs, export artifacts as file references and use official materialization;
verify ZIP SHA-256 digests before inspecting images. Prior raw download URLs returned
403 twice. Do not repeat those requests or change credentials/proxy/browser/profile
or CI model inference to bypass actual restrictions.

## Blocked acceptance

Fresh natural long-speech Qwen→aligner→Gemini 3.8 remains stopped. The preserved
`test/bounded-long-speech@f038f85` handoff records no Qwen weights and socksio install
network approval cancellation twice. No changed access/dependency evidence this turn;
no repeat installation or model download. Existing general approval alone does not
prove execution limits changed. No new ASR, alignment or Gemini calls.

Only when an allowed environment has dependencies and pinned assets, run new speech
through the product with finite elapsed/no-progress/retry bounds and saved span/batch
reuse. The held public dialogue recordings 706.24 s/762.048 s had prior hash/time checks
but informed translation comparisons, so they are not pristine holdouts.

Natural long-caption viewing, actual Chrome Fetch discovery/save/item playback,
Windows 11/RTX4070SUPER installation/VRAM/playback and useful enhancement/subjective
search/recommendation quality remain open. No enhancement preset is adopted. Earlier
synthetic 45-minute preview/restart checks do not establish speech quality.

Terminate owned processes on bounds/repeated same-cause failures, preserve originals
and complete diagnostics, and stop that blocked task. Local Chrome EPERM, supplied
browser ERR_BLOCKED_BY_CLIENT and extension-management denials remain unchanged.
