# Korean subtitle readability · 2026-09-06

New generated captions separate translation sentences from display cues. Existing
ready versions, imported SRT bytes, ASR text and translation/checkpoint units stay
unchanged. Choose **새 자막 만들기** to create a new presentation for an existing video;
this currently reruns processing, so do not regenerate a long film just to reflow text.

## Applied benchmark

The [Netflix Korean guide](https://partnerhelp.netflixstudios.com/hc/en-us/articles/216001127-Korean-Timed-Text-Style-Guide)
informs a 16-character line target, two lines and adult reading-speed target of 12 CPS.
Latin characters, spaces and punctuation use half-width accounting; combining marks
do not count twice. The [general guide](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements)
informs the 5/6-second minimum (834 ms after rounding) and seven-second maximum.
This is a local presentation profile, not Netflix delivery certification.

- Split only at whitespace/nearby sentence punctuation; never slice an unbroken name
  or number into characters. Balance two lines and avoid a one-word trailing block
  when feasible. Preserve all non-whitespace translation content.
- Allocate time proportionally within each original unit, respecting feasible duration
  bounds. Never move text outside that unit or close original gaps. Sort overlapping
  units' display cues chronologically, keeping source-unit and warning mappings.
- Count **[원문]** in fallback layout and show it on every relevant split cue. Reading
  speed, long lines, infeasible duration/count limits and overlaps remain visible QC
  findings; they do not discard content or permanently fail an otherwise valid job.
- Persist presentation/profile/QC and a small UI summary in each new track's checksum.
  Legacy rows with NULL presentation keep their original checksum and VTT. Reads do
  not recompute layout; a new layout algorithm cannot silently change an old version.

Splitting does not reduce the whole sentence's reading speed. This implementation
does not paraphrase, shorten translation, align words/shot changes, enforce a two-frame
inter-cue gap, or fully parse Korean syntax. A fast source can still be too fast to
read; its warning is a quality limit, not a claim the layout corrected it. Overlapping
speech can still show concurrent cues. Imported subtitles retain their supplied line
breaks; they are not run through generated layout.

## Verification

Local code checkpoint `9cb9882` on `app/readable-subtitles`, based directly on merged main
`4e6e447`. Linux/Python 3.12.13; no target Windows/RTX access.

- `.venv/bin/python -m unittest discover -s tests -q`: **74 passed, 13.050 s**.
  Includes real SQLite/FFmpeg, pause/resume without repeating completed ASR, source
  preservation, legacy tracks, stored display integrity, overlapping cue publication,
  Unicode/content/timing limits and SRT compatibility. All previous tests retained.
- `npm test --prefix tests/ui` and `node tests/ui/recommendations.cjs`: **DOM4 flows
  passed**; subtitle flow includes selected-version notices and Off behavior. This
  evidence is distinct from the real browser run below.
- Fresh persistence review at `95bd240` found overlapping split units could repeatedly
  fail publication and repeated blank separators could reject empty SRT blocks. Both
  fixed at `9cb9882`; bounded rereview had no remaining actionable findings. Reviewer
  independently passed 41 subtitle tests, 300 overlap/provenance probes and 48 separator
  variants. Earlier review verified actual legacy-schema migration/VTT preservation.

Actual production CLI/HTTP at `95bd240` regenerated two attributed public
[FLEURS cases](speech-quality.md) with installed large-v3/MADLAD CPU models. Japanese
10.44-second input completed in **44.34 s**, English 10.56-second input in **45.69 s**.
Both succeeded without source fallback. Each one-unit translation became two two-line
display cues: Japanese 1.490–5.080 / 5.080–8.190; English 0.690–4.347 / 4.347–8.730.
These repeat existing short samples; they do not expand the unique speech corpus.
Range bytes matched, original source hashes remained equal, and logs were zero bytes.
All **12 preexisting VTT versions** remained byte-identical after inference/store restart.
The subsequent overlap/parser fix does not change these nonoverlapping outputs.

Actual headless **Chromium 149.0.7827.0** against the production local app at `9cb9882`
decoded the public black-video/H.264/AAC speech fixtures (positive decoded-frame counts),
advanced playback time, sought into both cues, and exposed the expected native active
captions. Screenshots showed Korean glyphs and two readable lines. Captions Off/On
worked; closing/reloading/reopening restored a saved **4.25-second** position for both
items. No page errors or external page requests; server log zero bytes. This was real
browser media playback, without jsdom or mocked media/fetch. Chromium and a Korean font
were temporary QA dependencies, not new app dependencies or external font requests.

Playwright's browser CDN download first timed out/returned an incomplete archive.
A public npm Chromium package worked after extracting without unsupported archive
ownership changes; initial module-path/extraction attempts failed before browser launch.
This headless Linux check does not establish audible playback, Windows codec/driver
behavior, fullscreen/keyboard usability, real film motion or human viewing approval.

Observed remaining text quality: the English sample separates the possessive phrase
across sequential cues (ending one with “서양의”); its original translated number
spacing/wording also remains awkward. Width-based layout helps legibility but does not
complete Korean linguistic segmentation or translation quality. Do not claim OTT-level
quality from these two samples. Long films, dense dialogue, natural language changes,
target hardware and human quality remain required evidence.
