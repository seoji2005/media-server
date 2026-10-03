# Local recommendations from explicit feedback

Open a video → **감상 취향**. Choose **좋아요**, **취향 아님**, **비슷한 영상 덜 보기**
or **선호 미지정**. **이 영상을 추천에 포함** separately controls participation.
Every existing/new import starts excluded. A saved preference can stay private to
that item's viewing screen while excluded; it then affects neither candidates nor
scoring. Switching inclusion off retains the preference, source and viewing history.

The **추천** tab proposes up to 12 included videos with no explicit preference yet.
Rated videos supply feedback, so rate one and include some unrated candidates to
see related suggestions. With no useful title matches, included candidates are
offered as new discoveries. Selecting a suggestion opens the existing player with
its saved position and subtitle selection flow. No unsolicited subtitle summaries.

## What the first implementation uses

The player's **보관함 제목 바꾸기** edits the local display title (1–180 printable
characters), without renaming files or changing item identity, viewing state or
recommendation participation. Included items use the new title on the next ranking
read; the current recommendation view refreshes after a save or explicit title reread.
The library search also applies NFKC normalization, so full-width letters and decomposed
Hangul can find the same title. This provides useful labels for opaque filenames;
it adds no metadata retrieval, inferred preference or content understanding.

Title saves compare the last-read title text atomically, not a revision counter.
A different current title rejects the save with 409. A lost/failed response requires
an explicit reread before another save and keeps the draft. Each title request has
a 30-second response/body deadline, with no automatic retries. An aborted wait does
not cancel a server commit. Other windows retain their snapshot until refreshed.

Only included titles and explicit preferences are read. NFKC/case-normalized title
words exclude single characters, standalone numbers and a small common-word list.
Each matching unit contributes +1 for liked, -1 for disliked and -0.5 for
less-of-this. Divide their sum by the square root of the candidate's original word
count; aliases do not enlarge that denominator. Repeated seed units count once per
feedback type, and overlapping candidate aliases cannot multiply the credit.
Overlap is merged before counting so word ordering does not change deduplication.
A Korean compound repeated alongside its constituents cannot add another point
when a constituent already matches. This deduplication only removes redundant
credit; new spacing matches still require adjacent words separated by whitespace.
Recent import order breaks equal scores.
Every fourth available place reserves an unrelated candidate when one exists.
Missing/known-changed managed files are skipped; playback keeps its existing checks.

Korean words retain their exact form and can also match after one of
`에서/에게/으로/은/는/을/를` when at least two Hangul syllables remain. Two adjacent
Hangul words of at least two syllables each can match their joined form across
whitespace only: `우주 여행` ↔ `우주여행`. A joined match consumes the pair once;
it cannot also collect separate alias credit for those same words. Stop words are
excluded from the aliases too. Japanese mixed-script words can share complete
Kanji or Katakana runs of at least two characters: `日本の鉄道` ↔ `日本と鉄道`.
This uses no dictionary, model, arbitrary interior substring or character n-grams;
`京都` does not match `東京都`, nor `東京大学` match `北京大学` merely for `大学`.

This is still literal title matching. Proper names can resemble Korean particles;
unsegmented compounds such as `京都旅行`/`京都散歩`, other word endings, opaque
filenames, synonyms and cross-language titles can remain unmatched. It does not
establish semantic/content understanding or personalized quality. A liked
example may share an incidental word with an irrelevant video. Labels describe
the title-based reason, without exposing a seed title or caption. Human relevance
and actual browser presentation still need evaluation.

The [authored matching fixture](../tests/fixtures/title_matching.json) fixes 18
positive/control pairs and checks both directions. Exact-word baseline matched
2/16 positive directions; this extension matches 16/16, while both reject all 20
negative directions. These are implementation probes designed for these rules,
not a held-out quality score. Regression checks additionally cover alias dedup,
unchanged exact Latin matches, all three feedback signals, excluded CJK seeds and
candidates, discovery, and unchanged saved records. No recommendation index or
preference migration is added.

Watch duration, seek/resume history, subtitles, external metadata and cloud models
are not used for ranking. Unwatched never means disliked. There is no query/history
index or model download. Explicit feedback stays in the existing local SQLite data
directory and is covered by its backup and privacy rules. Recommendation responses
have the existing no-store/local-origin protections; UI state stays in memory.

## Recovery and verification

Preference and participation save together in a SQLite transaction. A failed or
lost response disables edits until **저장 상태 다시 확인** rereads the server, because
the write may already have committed. Reopening the same video waits for its pending
save before rereading/enabling controls. Each save carries the last read revision;
an outdated write receives 409 and cannot silently undo a newer exclusion, even after
a lost response or a change in another window. Existing preference rows upgrade without
erasing saved values. Switching videos invalidates older responses;
changing a preference clears cached recommendations. Returning focus refreshes the
recommendation page. Another open window may display its earlier snapshot until
refreshed; this is a single-person local app, not cross-window synchronization.

Author checks: real SQLite/HTTP/FFmpeg tests for opt-in defaults, positive/negative
ranking, discovery, excluded seeds/candidates, input/auth/error handling, failed
commit rollback, persisted position/subtitles and unavailable files. DOM checks
cover safe literal titles, existing player entry, stale requests, save failure and
retry; these use mocked media/HTTP and are not browser playback evidence.

The actual production CLI/HTTP probe imported seven generated clips, checked default
exclusion, all three feedback signals, the discovery slot and removal of an excluded
candidate/seed. After a forced server kill/restart, preferences and recommendation
responses were identical, position 1.25 s restored, VTT byte-identical, all seven
Range checks exact, source unchanged and server log zero bytes. A delayed stale HTTP
write after exclusion was rejected with 409 and the item stayed excluded. This is a
functional Linux CPU probe, not a throughput or recommendation-quality
benchmark. No private inputs or inference were used.

Implementation `34463f8`: full Python suite **61 passed** (12.593 s, exit 0); DOM4
flows passed, including the corrected reopen/stale-save case. Fresh review found the
older-write exclusion race at local `3475d13`; fixed at `a23a93d` with no remaining
actionable findings in bounded rereview. The reviewer independently ran eight
recommendation tests (3.504 s), the DOM case and two simultaneous SQLite saves sharing
one revision: exactly one succeeded and one was rejected. Published implementation
and final reviewed snapshot have complete tree `fb71e31e6467181fe6fb0a98bc1ebfeeb62c5d07`.
That review provides no browser/Windows/subjective-quality sign-off.
