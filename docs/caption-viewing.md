# Caption choices and timing while watching

Caption version, source transcript or Off is remembered for each video/audio.
Without an explicit choice, reopening selects the latest matching audio caption.
The automatic-selection button clears the saved choice and offset. Missing saved
versions stay Off with a notice instead of silently selecting another version.

Earlier/later controls step by 0.5 seconds within ±10 seconds. Positive values
show captions later. Adjusting timing pins the displayed version. Selecting another
caption resets its timing. Off resets the saved offset; native Off retains its
loaded track for native On, which can restore that track's in-memory offset.
Reopening Off attaches no caption. The video position remains unchanged.

Only the VTT response shifts: native playback and caption search share the adjusted
times. Boundary cues clip to the video. Entirely outside cues and sub-millisecond
remnants rounding to zero length are omitted from that response. This global offset
cannot repair timing drift or inaccurate alignment. Canonical VTT/source responses,
media, saved caption rows, jobs, checkpoints and evidence hashes remain unchanged.

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

Status reads, generation/retranslation/job commands and caption-setting saves now
have a30-second response/body deadline. A status read waits for already-pending
caption/command requests (each independently bounded) before starting its own deadline.
Duplicate clicks while a command is pending send only one request. Pending/uncertain
command state is retained across item/audio switches in this page's memory. Ambiguous
responses block another start/resume/restart until an explicit successful status read;
known precondition rejection such as a missing Gemini key remains correctable directly.
Neither timeout nor successful reread automatically resubmits a command.

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
