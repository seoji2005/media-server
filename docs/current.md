# Current work

Milestone: `feat/vp9-playback-compat`, based on live Server main
`8a82077ec2c2f73c6e478d1f3d6f72299a3d69ae` (PR40 merged). Restored local base
`d3d4b2b1dc6cabb7e708e884f13fc592a4bad195` has complete tree
`0827cbab1260f08459d9886cdb1c5f604c7ba3a6`; publish using actual remote ancestry.
Fetch main stays `0d6aa28a4a0c6944c053e3d63e150908b44b9175`; no open PR in either
repository at start. Owner implementation, bounded checks, independent review and
passing development merge approvals persist; release is separate.

## Delivered and current change

Gemini 3.8, foreign SRT/VTT translation, shared model installation pins, exact Fetch
item entry, bounded preparation/status recovery, local titles and complete caption
search paging are merged. PR40 passed independent review, both OS CI34597508759
and desktop/mobile visuals. Model/extension execution restrictions are unchanged.

The next unblocked slice addresses playback compatibility. A real VP9/AAC MP4 failed
on base d3d4b2b with unsupported_codec even though Fetch can save such files. VP9 MP4
now prepares WebM with copied video. VP8/VP9 with supported non-WebM audio converts
the selected voice to Opus 192 kbit/s CBR stereo; compatible Opus/Vorbis is copied.
Silent VP9 remux stays silent. Source bytes/all tracks remain intact. New audio_webm
uses existing per-audio rendition publication, reuse, limits and error handling.
FFmpeg libopus is needed; no Python/model/network/schema change. HEVC/10bit support,
video transcoding and enhancement adoption are still open.

## Evidence and next action

- Linux CPU real four-second VP9 fixtures: six new tests passed in 5.281 s, including
  copied packet/decoded-frame identity, audio selection, captions/position/Range,
  disk/timeout/tamper failures and actual process death before commit.
- Existing rendition tests: 10 passed / 7.302 s; audio tests: 6 passed / 5.240 s.
  A separate fresh process reused the committed audio_webm without conversion and
  verified original bytes. Focused audio/item-entry DOM uses mocked HTTP/media.
- Chrome integration adds actual VP9 import + companion caption + item-entry:
  opening never prepares automatically; the explicit button prepares WebM, native
  caption/video decode, seek/save and paused reopen are checked. Source preservation
  and desktop/mobile screenshots are mandatory. It does not run the Fetch extension.
- Freeze source, obtain fresh independent original/recovery review, inspect final
  Linux/Windows CI and four new screenshots, then merge under continued approval.
  Observe CI for at most 10 minutes/10 polls, each job capped at 10 minutes. Do not
  rerun unchanged failures without new evidence. Final results belong to that PR.
- Synthetic short video is not long-film performance, audible/subjective quality,
  HDR/HEVC support or target Windows 11/RTX4070SUPER acceptance.

For GitHub screenshots, export a file reference, use official materialization and
verify ZIP SHA-256. Prior direct URLs failed403 twice; do not repeat them or change
proxy/credentials/browser/profile/CDP or run CI inference to bypass restrictions.

## Blocked acceptance and roadmap

Fresh natural long-speech Qwen→aligner→Gemini 3.8 is stopped: no Qwen weights and
socksio installation hit cancelled network approval twice. Read-only cache inspection
found no new assets; no repeat installation/download/new ASR/alignment/Gemini calls.
The preserved `test/bounded-long-speech@f038f85` handoff keeps the failed attempt.
Previously held 706.24 s/762.048 s recordings informed translation comparisons and
are not pristine holdouts.

When an allowed environment has pinned assets/dependencies, run a new long speech
input through the actual product with elapsed/no-progress/retry limits and saved
span/batch reuse. Actual Fetch discovery/save/item playback, extension-only reception,
Windows 11/RTX setup/VRAM/long playback, useful enhancement and subjective search/
recommendation quality remain open. No enhancement preset is adopted.

Terminate owned processes at limits/repeated same-cause failures, preserve originals
and diagnostics, then stop that blocked task. Local Chrome EPERM, supplied browser
ERR_BLOCKED_BY_CLIENT and extension-management denials remain unchanged.
