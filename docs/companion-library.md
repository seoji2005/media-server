# Minimal companion library and provided-caption APIs

These additive endpoints use the existing loopback boundary and `X-Media-Token`.
They neither expose LAN access nor change existing `/api/library` responses.
Persistent server/library identity is still obtained from `/api/companion/identity`.

## Included library

`GET /api/companion/library?limit=20&cursor=...` returns `items` and `next_cursor`.
Limit is 1–100; the default is 20. Only rows currently explicitly included in
recommendations appear. Each entry contains item ID, original file ID/SHA, title,
creation time, original duration, preparation state, preference/revision, and
`timebase: original-file`, `audio_index: 0`. This is metadata, not fresh file-integrity
or playback-readiness evidence. Moment APIs retain their own validation.

Keyset order is descending `(created_at,id)`; the cursor denotes the last returned
row. Newer imports do not shift subsequent pages. This is not a frozen library
snapshot: inclusion changes apply on each request, and a fresh traversal is needed
to see newly included rows before the cursor. Inclusion is joined before title
collection in a single database query. No whole-library expansion or 200-item cap.

`POST /api/companion/library/lookup` accepts `{"ids":[...]}`, 1–20 distinct IDs,
at most 2 KiB body. Returns included `items` in requested order and `unavailable`
IDs for both missing and excluded entries, without their titles/preferences.
Recheck inclusion at later moment operations; page responses are not durable consent.

## Provided subtitles

`POST /api/companion/library/{item_id}/subtitles` receives raw UTF-8 bytes and these
required query parameters (no source URLs/cookies/credentials):

| Parameter | Meaning |
| --- | --- |
| `file_id`, `file_sha256` | Exact original associated with the item |
| `content_sha256` | SHA256 of submitted bytes, before decoding/normalization |
| `format` | `srt` or `webvtt` |
| `language` | Explicit language tag, e.g. `ko`, `ja`, `en`, `und` |
| `timebase` | Exactly `original-file`; audio index is fixed at 0 |

The response includes `id` (track ID), `item_id`, all accepted identity fields,
`audio_index: 0`, `ready`, `duplicate`, and normalization `import_notes`.
201 means newly saved; 200 means the same import was already saved. Readiness here
means usable subtitle cues, not a ready video rendition. Identical file identity,
content hash, language, format and timebase resolve to one track using a unique
database constraint and transaction, including after restart/lost responses.

Raw bytes are stored unchanged alongside normalized timed cues. Existing tracks,
watch position and originals are preserved. Changed hashes fail. Legacy SRT import
retains its existing behavior and encoding support. Imported language is visible;
foreign supplied captions can be translated with the existing retranslation action.

Limits remain **2 MiB, 20,000 cues, 4,000 characters per cue**. Fetch can produce
larger files; such imports fail explicitly. VTT supports cue IDs, minute/hour
timestamps, NOTE blocks and inert voice/class/style tags. STYLE/REGION and timestamp
remapping headers are unsupported; Fetch must submit its final original-timebase VTT.
Existing SRT normalization can sort, clip and omit unusable cues, reporting counts;
the untouched submitted bytes remain available in local storage.

Server-side implementation alone does not complete Fetch delivery or Compass browser
integration: those adapters must adopt this contract and run their own end-to-end
checks. No companion repository was changed in this slice.

## Remaining boundaries

Pocket's repository/PR contract was inaccessible during this work (GitHub 404).
Pack creation and watch/preference event synchronization remain pending verified
contracts, especially `unset` versus no new feedback and conflicting device positions.
The server does not invent that wire contract or relax its local boundary.
Use distinct local ports: server 8765; for the two companions that currently both
default to 8787, explicitly choose another supported port for one of them. No launcher
or service-discovery framework is added.
