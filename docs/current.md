# Current work

- **Milestone:** #9 merged; a different-film retrieval check and whole 12-minute real
  subtitle execution are complete. Near-black images no longer become search candidates.
  Korean dialogue naturalness is the clearest newly measured quality gap.
- **Branch / PR / HEAD:** `app/scene-quality`; resolve its live Draft PR/HEAD in
  [open PRs](https://github.com/seoji2005/media-server/pulls). Base main `bfce827` includes
  owner-approved #9. Verified code `b20fd99`, followed by evidence/docs; the new PR needs
  separate merge approval. One writer; AGENTS.md and [product contract](product.md) govern.
- **What works:** import/compatible copies, shared audio, playback/resume, real ASR/Korean
  captions and recoverable jobs, literal/visual scene search, previews and explicit-feedback
  recommendations. [New quality findings](quality-check.md), [scene setup](scene-search.md),
  [ASR/runtime](subtitles.md), [readability](subtitle-readability.md),
  [renditions/audio/UI](compatible-renditions.md).
- **Current blockers:** no Windows/RTX access or suitable local 60+ minute speech input.
  The 12-minute run finished before the planned interruption, so it supplies no new
  interruption proof; ASR interruption still repeats its stage. Action/absent-scene search
  and natural Korean dialogue remain weak. [Enhancement](enhancement-spike.md) has no
  adopted preset. Earlier long-film download/larger-encoder requests ended in cancelled
  approval; a separate public short-film download succeeded. HEVC/10-bit policy, spending
  and scope cuts require owner decisions.
- **Next action:** reuse the saved ASR and frozen dialogue cases to compare one local
  translation candidate with conversation context; check separate dialogue before adoption.
  Prioritize Windows/RTX and long-input recovery when access/input becomes available.
  Keep enhancement and semantic retrieval included; do not expand diagnostics/harness.
