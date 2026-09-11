# Current work

Milestone: `feat/library-display-title`, based on live Server main
`ade60623e24b1c612b5314b7115f3bfefdbfe659` (PR37 merged). The restored local base
`b16691e92f968d41f61d4663c7a2ccb28fb6827d` has the same complete tree
`79d5dfffc48ab2c8f748ea2b401b5390e113aa6e`; publish with actual remote ancestry.
Fetch main remains `0d6aa28a4a0c6944c053e3d63e150908b44b9175`; no open PR
in either repository at start. Owner approval continues for implementation, bounded
checks, fresh independent review and merging passing development changes, not release.

## Delivered and current change

Server PR35/36 and Fetch PR22 are merged: Gemini3.8 for new jobs, foreign SRT/VTT
import and explicit saved-text translation, shared Qwen/scene runtime compatibility,
and exact verified Server item entry retaining viewing state. PR37 adds finite preview/
scene preparation waits and no-progress stops; fixed-tree review passed and CI run
34585306905 passed actual synthetic Chrome/restart checks on Ubuntu24.04 and
Windows Server2025. These steps are not pending implementation.

The player's optional **보관함 제목 바꾸기** now saves a local display title with
an atomic comparison to its last-read text. A different current title returns409;
an uncertain response retains the draft and requires rereading before another save.
Each title write/read waits at most30s, covers the response body and has no automatic
retry. The server commit may complete after a client timeout. This compares text,
not a revision counter. Switching audio retains the editor and pending title save;
reopening an item waits for its pending save before reading metadata.

Title changes update local search and opted-in recommendation inputs. Library search
normalizes full-width characters and composed/decomposed Hangul. No schema migration,
file renaming, item/hash changes, preference changes, history/caption resets or cloud
requests. Renaming does not reload the playing video. This improves manual labels;
it does not establish semantic recommendation or subjective viewing quality.

## Verification

- Linux CPU: full Python suite274tests in60.807s, exit0 (2existing skips). New5tests
  use real FFmpeg/SQLite/ASGI for title validation/auth, conflicting concurrent saves,
  rollback, restart, duplicate identity, existing companion item entry, selected caption/
  offset/position preservation and ranking after a liked seed is renamed.
- All10DOM scripts pass with mocked HTTP/media. Title cases cover literal safe text,
  Unicode search, no playback reset, conflicts, lost reply/reread, pending reopen and
  stale item isolation. Further audio-switch regression reproduced a stuck title save;
  fixed code passes title/audio cases with the pending editor rebound to the item.
- Initial fresh review at9893664 found one validation defect: a surrogate character
  in expected_title returned500. Both title strings now reject nonprintable/invalid
  Unicode before SQLite binding; focused regression cases pass. The exact title
  comparison stays unnormalized. Narrow rereview of this correction is required.
- Existing model-free CI browser test now saves a literal Unicode title while paused,
  checks unchanged media position/source/caption, normalized search and persistence
  after actual server restart. It captures desktop/mobile title forms. CI/visual
  results and fresh fixed-HEAD independent review are pending at this checkpoint;
  check the PR before claiming acceptance or merging.
- Prior45-minute160x90,1fps H.264 fixture: actual FFmpeg/SQLite/ASGI generated120
  previews and resumed104after restart at16. Position1357.25s, caption/+500ms and
  original hash stayed unchanged. This11.22s tiny-input probe is not a speed forecast
  or natural long-caption viewing evidence.

## Blocked acceptance and next work

Fresh natural long-speech Qwen→aligner→Gemini3.8 acceptance is stopped. The prior
`test/bounded-long-speech@f038f85` branch preserves the complete handoff: model
setup failed before any weight download; socksio installation hit network approval
cancellation twice. Missing socksio/weights were checked without repeating that
installation or changing route. Two already-held public dialogue recordings
(706.24s and762.048s) and reference annotations passed offline hash/time checks.
Some reference text was used in translation comparisons; these are not pristine
holdouts. No new ASR/alignment/Gemini calls. Renewed general approval alone is not
new evidence that the execution limit changed.

Finish title review, existing CI/visual checks and passing development merge. Then,
only when an allowed environment has the dependencies and pinned model assets, run
the fresh continuous-speech product path with saved span/batch reuse and finite limits.
Natural long-caption viewing, actual Chrome Fetch discovery/save/item navigation,
Windows11/RTX installation/VRAM/playback, useful enhancement and subjective search/
recommendation acceptance remain open. SwinIR and the earlier filter experiment
have no adopted enhancement preset; no new enhancement-quality claim is made.

Stop on elapsed/no-progress limits or repeated same-cause failures, terminate owned
processes and preserve originals/complete evidence. Existing browser/CDP/profile/proxy
and model-inference CI workaround prohibitions remain. Do not convert missing target
hardware or human viewing acceptance into synthetic completion claims.
