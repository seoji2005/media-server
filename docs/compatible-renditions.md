# Compatible playback renditions · 2026-09-06

## Behavior

H.264 8-bit 4:2:0 in MKV can now be watched without manual FFmpeg conversion.
H.264 stays stream-copied. AAC/MP3 is copied; AC3/EAC3, DTS, FLAC, Opus/Vorbis and
listed PCM formats use AAC 192 kbit/s stereo. New multi-audio MP4/MKV and supported
WebM get one selected audio stream: the first, matching existing ASR `0:a:0`.
This is explicit in the player. An audio selector remains future viewing work.
HEVC and unsupported depth/chroma get distinct fixed messages; no video encoding.

[FFmpeg stream selection and streamcopy](https://ffmpeg.org/ffmpeg.html#Stream-selection)
provide this behavior. Explicit `0:V:0` excludes cover art; `0:a:0?` allows silent
video. Subtitle/data/attachment/chapter streams are excluded from the derivative;
all original bytes and streams remain in the managed original. No model or new
runtime package is needed. This is local preparation, not a downloading feature.

## Storage and recovery

- Original import commits before preparation. Browser upload then calls the protected
  `POST /api/library/{item_id}/playback`; CLI import performs both phases.
- A separate rendition ID, SHA, size, duration and source SHA live in SQLite. Each
  file has its own exclusive directory. Content/Range/ETag use the selected rendition;
  source transcript, existing caption records and job input identity retain the original.
- Output is probed, hashed and fsynced; the original is reverified before publication.
  Video geometry and mapped-stream duration must match within 250 ms. MP4 stream
  durations and Matroska DURATION tags avoid comparing with a dropped longer track.
  If these are absent, strict container-duration comparison remains: unusual timing
  can still be refused safely. This is not an exhaustive packet/frame integrity test.
- Space is checked before preparation; FFmpeg output size and runtime are bounded.
  Failures remove only the invocation's uncommitted derivative directory. They retain
  the imported original and a fixed diagnostic code; clicking its card retries.
  Existing ready derivatives are not overwritten. Source/derived tampering still
  fails the existing verified-byte playback boundary.
- Import/preparation is serialized by the app's existing import lock. Other ready
  playback remains available. Startup moves unregistered copies into recovery and
  preserves registered originals and derivatives. A hard stop repeats conversion;
  this does not add checkpoints to FFmpeg. Subtitle job/attempt resume is unchanged.
- Legacy files start as unchecked and are verified/classified on first selection,
  avoiding a full-library startup probe. Existing item IDs, watch history and caption
  rows are preserved. Stored original duration stays intact; the player uses the
  rendition duration when the omitted streams made the original container longer.

## Evidence

Code checkpoints: `1bd373c` → `4923206` → `f0f03ff`, based on merged main `4a8c20a` (PR #7).
Linux/Python 3.12.13/FFmpeg 6.1.1; actual installed CPU model runtime, no Windows/GPU.

- `python -m unittest discover -s tests -q`: 95 passed (21.672 s) at `4923206`. After the final position-bound fix, ten rendition
  tests passed (6.136 s) and 25 app tests passed (4.758 s): real H.264 MKV,
  AC3 and differing/default audio tracks; decoded video/audio hashes, HTTP Range and
  ETag; no-space/timeout/validation retry; actual subprocess exit immediately before
  SQLite commit; legacy migration with retained captions/history; HEVC/10-bit refusal.
- `npm test --prefix tests/ui` and `node tests/ui/recommendations.cjs`: four DOM flows
  passed. New player coverage exercises failed preparation followed by retry. These
  use mocked media/HTTP and do not establish codec playback.
- Existing attributed Japanese FLEURS `ja_jp_0000` speech ([corpus/evidence](speech-quality.md))
  was locally muxed with synthetic moving video into 10.44 s H.264/AC3 MKV. CLI import
  plus preparation: **0.885 s**. Actual Whisper large-v3 int8 → MADLAD CPU float32
  generation: **43.422 s**, one translated sentence, two presentation cues. No source
  fallback in this case. Source bytes, exact derived Range and 15 earlier tracks survived.
  Codec conversion can affect ASR output; no claim of identical words to the AAC probe.
- Actual Chromium **149.0.7827.0**: 54 decoded frames and 49,393 decoded audio bytes;
  native Korean captions, Off/On, seeking and **4.25 s** resumed position. Browser
  upload of a separate AAC MKV triggered automatic remux and played a supplied caption
  (113 decoded frames). Screenshots inspected. Page errors/external page requests: zero.
  Server restart served byte-identical generated VTT; server logs remained zero bytes.
  A first browser connection in a separate execution session was refused; the completed
  probe launched the production server and browser in the same execution environment.
- Actual post-fix legacy dual-audio browser case: original container over 12 s with
  a longer discarded track; first-use preparation produced 10.496 s playback. Native
  captions, 105 decoded frames and 4.253 s resume passed; the existing subtitle row was
  byte-identical. Final browser test reached ended and saved 10.496 s without an error.
- Fresh review reproduced discarded-track duration and legacy audio classification
  defects, then an end-position validation mismatch; all corrected. Final bounded
  review found no remaining actionable findings and independently passed the two
  affected real-FFmpeg duration/position regressions.

These short clips exercise the real format/model/browser path, not long-film quality,
audible/headful human evaluation, Windows codec behavior or RTX 12 GB suitability.

## Long-input gate remains blocked

The planned non-repeated 60+ minute CPU ASR/translation/time/memory/recovery run did not
start. Public-domain *His Girl Friday* metadata was reachable (92 minutes, ~573 MB),
but the actual download returned **network approval was cancelled before a decision
was returned**. No permitted local 60+ minute input was present. No network control was
changed or bypassed. Short clips above do not substitute for that gate. Resume this
measurement when a permitted long input is available; target Windows/RTX remains the
first hardware gate. Enhancement, visual analysis/search and Windows polish stay in scope.
