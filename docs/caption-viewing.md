# Caption choices and timing while watching

Caption version, source transcript or Off is remembered for each video/audio.
Without an explicit choice, reopening selects the latest matching audio caption.
The automatic-selection button clears the saved choice and offset. Missing saved
versions stay Off with a notice instead of silently selecting another version.

When another Korean caption is available, **최신 한국어 자막 보기** beside the
selector uses the newest saved Korean track for the current audio. It remains
reachable while preparation is folded, including from a foreign caption, source
view, older version or Off. Arrival of a result does not change the current choice.
The explicit click uses the existing caption-setting save, resets timing to zero
like ordinary version selection, and keeps media position/play state. Pending or
unconfirmed caption saves disable it. It cannot start or repeat processing.
"Latest" means the newest available matching-language track, not a claim that a
particular job produced it. Other-audio and foreign tracks are excluded.

Imported foreign captions use **Gemini로 한국어 번역** for their first translation;
generated results retain **Gemini로 다시 번역**. A result's source is labeled
**원문 자막** because it can come from either speech recognition or a supplied file.
The source-content accuracy notice remains; no provenance is inferred from text.

Earlier/later controls step by 0.5 seconds within ±10 seconds. Positive values
show captions later. Adjusting timing pins the displayed version. Selecting another
caption resets its timing. Off resets the saved offset; native Off retains its
loaded track for native On, which can restore that track's in-memory offset.
Reopening Off attaches no caption. The video position remains unchanged.

Native Off/On selected while a caption-setting save or its recovery read is
uncertain stays separate from saved settings. Confirmation retains the current
native choice, loaded track and in-memory timing; a late read cannot turn captions
back on or discard a newer On. When the choices differ, **미저장** and an explicit
**자막 끄기 저장** or **현재 자막 설정 저장** button distinguish the current display
from the saved setting. The button makes one save using the confirmed revision;
reads never replay a write. Native changes after confirmation use the existing
explicit save. File retries retain displayed timing, and timing adjustments start
from that displayed offset. Reopening before saving still uses the saved choice.
A failed confirmation keeps the local choice and offers another read; a lost save
response also requires confirmation.

Only the VTT response shifts: native playback and caption search share the adjusted
times. Boundary cues clip to the video. Entirely outside cues and sub-millisecond
remnants rounding to zero length are omitted from that response. This global offset
cannot repair timing drift or inaccurate alignment. Canonical VTT/source responses,
media, saved caption rows, jobs, checkpoints and evidence hashes remain unchanged.

## Searching long caption tracks

Search reads only the currently selected, loaded native caption track in this page.
NFKC/case normalization and collapsing whitespace let a phrase match across a cue's
line breaks, repeated spaces or tabs. Displayed text keeps its original line breaks
and literal characters. Search also matches across two consecutive, non-overlapping
cues when their gap is at most 0.5 seconds. The boundary accepts a space or no space,
including Japanese words split by display layout; spaces inside cues are unchanged.
Longer pauses, overlapping cues and three-cue phrases are not joined. This is literal
matching, not inferred dialogue continuity, synonyms or translation.

A cross-cue result shows both original texts and seeks to the first cue's adjusted
timestamp. A query found entirely in one cue does not gain a redundant preceding
result; distinct later occurrences remain separate. The same paging, stale-button
and selected-track guards apply. No source caption, index or viewing setting is
rewritten by searching.

All matching cues are reachable in chronological pages of up to 50 buttons. The count
and displayed range stay visible; previous/next controls move keyboard focus to the
new group's first result. Paging does not seek, play or write viewing state. Selecting
a result uses that native cue's adjusted timestamp and brings the video into view;
the existing completed-seek handler saves the position. Query/page changes invalidate
old buttons immediately, including the input debounce interval. New caption/audio/item
selection resets pages, and Off hides results. No-match/empty queries hide the pager.

Cue text, normalized text, current matches and query exist only in page memory for
the selected track. There is no search endpoint, persistent index/history, model call
or recommendation input. Rendering stays bounded to 50 results; matching still scans
the selected loaded captions when the normalized query changes, not on each page.

The DOM fixture covers 115 results, last-page seeking, whitespace/literal text,
keyboard focus and stale query/page/caption/item callbacks. The Chrome integration
imports 115 short VTT cues into its synthetic 20-second video, applies +500 ms, pages
with keyboard/mobile controls and checks the last native cue's seek and server save.
It restores the existing caption output byte-for-byte. This is navigation plumbing;
neither fixture measures natural long-speech caption quality or target RTX hardware.

## Storage and API

- Transactional schema v10 adds only `caption_views` with video/audio key, selection,
  offset and revision. Existing libraries default to automatic without a write.
- `GET /api/library/{id}/subtitles?audio_index=N` adds `view` to existing status.
  `selection:null` means automatic, an empty string means Off, and a track ID
  optionally suffixed `:transcript` selects that version/source view.
- `PUT /api/library/{id}/caption-view` accepts exactly `audio_index`, `selection`,
  `offset_ms`, `revision`, with a 512-byte bound. Actual audio range, same-item/current
  input track and source availability are validated. Explicit cross-audio captions
  retain their existing warning. Offset/revision must be bounded integers;
  automatic/Off require zero offset.
- Atomic revision checks reject stale writes. Lost responses and conflicts disable
  further edits and offer a fresh read; no automatic write retry. Same-video/audio
  reopen waits for its pending save. Late responses cannot alter another player.
  Overlapping subtitle status reads discard older results.
- `GET /api/library/{id}/subtitles/{track}.vtt?offset_ms=N` composes with
  `transcript=true`, retaining normal input/artifact integrity checks. Fallback
  markers remain paired with their cues when earlier cues leave the visible range.
  No offset parameter returns canonical bytes.
- Existing loopback/origin/session boundaries apply. No inference, cloud request,
  browser storage, telemetry or credential handling is added.

## Bounded status and command recovery

Status reads, caption-file imports, generation/retranslation/job commands and caption-setting saves have a
30-second response/body deadline. A status read waits for already-pending
caption-setting/job-command requests (each independently bounded) before starting its own deadline.
Duplicate clicks while a command is pending send only one request. Pending/uncertain
command state is retained across item/audio switches in this page's memory. Ambiguous
responses block another start/resume/restart until an explicit successful status read;
known precondition rejection such as a missing Gemini key remains correctable directly.
Neither timeout nor successful reread automatically resubmits a command.

Caption imports show **자막 가져오는 중…** and share the pending/uncertain command
gate, so duplicate file events cannot send another import or start processing.
After a lost receipt, **상태 다시 확인** reads the saved caption list and tells the
viewer to choose the imported result if present. It preserves the current caption,
Off, offset and playback; it cannot reimport or start translation. A late receipt
cannot select a caption after recovery, audio/item switching or a newer file choice.
An ordinary confirmed import still selects its result. Import receipts do not delay
loading existing captions on an audio change or reopen. Known validation rejection
allows a corrected file without an ambiguous-save gate. These are in-page controls,
not cancellation of a server commit or a durable exactly-once import contract.

Polling stops on a read failure,5minutes without a higher saved ASR/translation count
or later saved ASR time, or10minutes/400reads per monitoring session. Stage/job changes
can count as progress but cannot extend the total session budget. An explicit status
refresh, new command or reopening the player starts a new monitoring session. Previously
loaded captions, Off, offset and playback stay intact during read failure/recovery;
initial-load failures can also recover. Manual pause remains available after a polling
stop. A client timeout/monitor stop does not cancel or diagnose the server worker.

The UI guards are not durable command IDs or an exactly-once server contract. A reread
shows the current server snapshot, not proof that a delayed request can no longer commit.
An explicitly requested new operation, another page or a page reload remains subject
to the existing server job/state guards and per-request Gemini billing disclosure.
No new server schema, jobs, checkpoint format or model retry policy is introduced.

## Evidence and limits

`PYTHONPATH=tests python -m unittest -q test_caption_view` covers SQLite restart,
racing writers, process death before commit, v9 migration rollback, strict API
validation, audio/track isolation, clipping, source/fallback output and unchanged
original/evidence rows. `node tests/ui/caption-view.cjs` covers pending saves across
item/audio changes, native Off/On, lost responses, conflict recovery and missing tracks.

The real browser smoke test uses only its synthetic 20-second H.264/AAC video. It
checks shifted native cue activation/search, Off across reopen and an older saved
version/offset after server restart and new generated captions. CI captures this
fixture's desktop/mobile screens. This is viewing behavior, not natural speech
quality or target RTX performance. Prior local Chrome socket EPERM and supplied
browser ERR_BLOCKED_BY_CLIENT are unchanged; real Chrome evidence comes from CI.
