# Time previews · 2026-09-06

**장면 찾기 → 시간별 미리보기** provides an optional visual timeline. Opening the panel
only reads saved status. Explicit generation samples roughly every ten seconds, capped
at 120 frames over the video interval. Selecting a frame seeks, starts playback and
returns the viewport to the video. The UI warns about spoilers and distinguishes time
sampling from content/semantic search. No shot detection, embeddings or model dependency.

## Persistence and limits

- Four samples per request; each JPEG commits independently. Pause/closing stops after
  the current request. A server hard stop loses only the in-flight frame; reopening and
  explicitly continuing reuses saved images. Shutdown finishes the current bounded frame.
- SQLite schema 3 adds item/source-bound preview sets and images. JPEGs fit 320×180 with
  preserved display aspect ratio; each is capped at 192 KiB. One FFmpeg extraction runs
  at a time, with one thread per decoder/encoder/filter and a 20-second frame timeout.
  No duplicate video copy or background preview worker. Existing verified source access,
  loopback/token, no-store and logging boundaries apply to the protected preview routes.
- One undecodable sample is recorded, other samples continue, and individual retry is
  available. A damaged/missing image response also offers regeneration. Disk-full or
  source-change failure preserves prior checkpoints and independent original playback.
- Original playback timestamps and compatible-copy offsets are recorded separately.
  Sampling excludes initial video gaps and longer discarded audio tails. FFmpeg's
  [absolute input seek](https://ffmpeg.org/ffmpeg.html#Main-options) and
  [scale filter](https://ffmpeg.org/ffmpeg-filters.html#scale) provide extraction.
  Sparse samples can miss short scenes; arbitrary damaged/nonstandard timelines can fail.
  Large originals still incur the existing first-access full integrity scan.

## Evidence

Local code checkpoints `43d89a1` → `ebf7e39` → viewing follow-up `330481a`, based on
published PR #8 `1f66bd8`. Linux / Python 3.12.13 / FFmpeg 6.1.1; Chromium 149.0.7827.0.

- At `ebf7e39`, `python -m unittest discover -s tests -q`: **109 passed / 32.565 s**.
  Eight preview tests cover real colored frames, scoped/hash-checked JPEG/Range responses,
  concurrent caption/playback access, single-frame retry, disk-full, actual subprocess
  exit after commit, unchanged prior images, long-audio tails and nonzero MP4/MKV timing.
  Six DOM flows passed (`npm test --prefix tests/ui`; `node tests/ui/recommendations.cjs`).
  The small viewport-return follow-up passed the preview DOM regression separately.
  At `330481a`, real keyboard/click selection returned the complete video into view at
  1440×1080 and 390×844; screenshots and native Korean captions were inspected.
- Actual production server/browser: 60 s color-changing video with supplied Korean SRT.
  Pause after four of six images → stop/restart server → finish the remaining two;
  first four complete SQLite rows unchanged. Native captions and 197 decoded frames
  remained available while a real build response was deliberately delayed. Keyboard
  navigation reached the expected 35 s yellow/25 s blue images; resume restored 25.027 s.
- An existing permitted 2 s *Tears of Steel* excerpt also produced a viewable preview
  (434 ms through the browser, short clip only). Attribution/license/source:
  [existing public-video evidence](enhancement-spike.md). Desktop/mobile layouts were
  inspected; no horizontal overflow. Earlier 20 caption rows, 12 files and 12 watch rows
  remained exact. Completed probes: zero page errors, external page requests or server
  log bytes. No model execution was needed for this feature; earlier ASR evidence stands.
- Fresh review found a retained retry callback targeting a different newly opened item.
  Fixed with an owner guard and A→B regression. Reviewer also raised a timestamp candidate:
  real Chromium confirmed offset-5 MP4 preview5 was green while playback5 was red.
  Absolute seeking fixed it (both red); MP4 and remuxed MKV frame comparisons passed.
  Bounded rereview at `ebf7e39`: no new findings; independently reran those two regressions.

Failed probes were retained locally: initial test expectations counted an AAC mux gap;
the timing fix excludes that gap. Browser QA first waited for an unseekable zero time,
then tried a completed grid's hidden build button and a non-unique image locator; these
QA errors were corrected. One Chromium launch exited SIGSEGV; the next launch worked
with the same same-origin protections. The temporary public QA schema was additively
adjusted during development; regression tests exercise clean legacy-to-schema-3 upgrades.

This is short public/synthetic, headless Linux evidence. It does not establish human
viewing quality, long-video extraction time, Windows/RTX fit, scene understanding or
enhancement quality. Those product gates remain open in [current](current.md).
