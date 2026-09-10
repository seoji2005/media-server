# Minimal companion library and provided-caption APIs

These additive endpoints use the existing loopback boundary and `X-Media-Token`.
They neither expose LAN access nor change existing `/api/library` responses.
Persistent server/library identity is still obtained from `/api/companion/identity`.

## Open a specific imported video

`#item=` followed by URI-encoded JSON opens the existing player, paused, using the
server's current audio, watch position and caption choice/Off/offset. This general
entry is independent of recommendation inclusion and the existing `#moment` route.
The fragment is bounded to 2,048 encoded characters and removed before application
HTTP calls. It contains exactly these fields; no token, path, title, source URL,
desired position/audio/caption or automatic processing instruction is accepted.

| Field | Required value |
| --- | --- |
| `version` | Integer `1` |
| `server_id`, `library_id` | Paired server/library IDs, 32 lowercase hex characters each |
| `item_id`, `file_id` | Delivered item and original-file IDs, 32 lowercase hex characters each |
| `sha256` | Delivered original's SHA-256, 64 lowercase hex characters |

The page posts this same object to `POST /api/library/{item_id}/item-entry`, with its
own current `X-Media-Token`. The maximum body is 1,024 bytes. Success is exactly
`{version:1, server_id, library_id, item}` where `item` is the existing player item
shape. The endpoint checks original bytes using normal integrity verification and,
when available, the selected audio's rendition. IDs/hash always refer to the original;
the player's duration/preparation can refer to the rendition. The first verification
after restart can scan the complete file. Playback still verifies its own open
descriptor; entry is not a guarantee against later changes.

Wrong identity returns `item_reference_changed` (409), malformed/unsupported payload
`invalid_item_entry` (422); missing/changed media retain existing errors. A rendition
that has not been prepared returns the item with `unavailable_reason:rendition_required`.
The page displays an explicit preparation button. Only clicking it requests existing
local preparation, revalidating the entry first and again afterward. Navigation never
prepares or translates automatically. Opening, seeking and closing before Play do not
save watch history. Invalid or stale links do not replace an existing player; incoming
valid links may save the previously playing video's current position when closing it.
All existing caption, preference, source and processing rows are unchanged by entry.

The Server browser tests cover startup/restart, Off/offset, default-excluded imports,
wrong-library rejection and a real synthetic MKV → explicit MP4 preparation with a
provided Korean VTT. These are not actual Fetch extension navigation or target-device
acceptance. Fetch must adopt this versioned contract separately; root-library opening
remains its currently published behavior.

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
