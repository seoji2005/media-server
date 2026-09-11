# Current work

Milestone: `fix/scene-qwen-runtime`, following merged [PR35](https://github.com/seoji2005/media-server/pull/35).
Remote base `72722b02ac56a364aa1e791c488d7820529ba824`; local base
`00b318db1adbb8f460e2422843b8e3a66fa3f880` has identical tree
`28ed1ae40218afeba64491b6fa2a7ce70f42445f`. Preserve actual remote parents.
Owner authority covers implementation, verification, independent review and merging
passing development changes; not release or target-device acceptance.

PR35 adopted Gemini 3.8 for new jobs with unchanged evaluated v5 behavior, preserved
all six old translation profiles, added explicit-language SRT/WebVTT imports and
fixed stale import completion overwriting a newer caption/audio/sync selection.
Independent review accepted; Product checks run 34573931996 passed on Ubuntu24.04
and Windows2025, including the existing synthetic browser/restart tests.

## Current change

Scene setup wrongly installed legacy Transformers4.57.1 over Qwen5.16.1. Its Encoder
also expected a tensor from get_image_features/get_text_features, while5.16.1 returns
a pooled-output object. New requirements-scene.txt matches current Qwen's core pins;
legacy requirements-models.txt remains separate for old speech-job recovery. The
Encoder normalizes the pooled tensor in either return form. Existing package-bound
identities invalidate derived scene vectors on runtime change; no originals, captions,
watch state, schema, query history or networking behavior changes.

Installed Linux CPU runtime: tiny local random model/tokenizer through production
Encoder; before-code failure reproduced and corrected test passed. Korean text/JPEG
outputs are finite unit-length vectors; simulated old tensor return matches exactly.
Shared Qwen+scene dependency dry-run resolves. This does not install/run every Qwen
dependency or validate upstream SigLIP2 quality on the new runtime. Existing scene
persistence/lifetime tests8 pass and DOM pass. See [exact evidence](scene-search.md).
Fresh independent fixed-commit review and existing model-free CI gate the merge.

## Next and retained limits

Finish this review/CI/merge and Fetch's separate exact-item adapter review. Current
Server #item/API already restores saved audio/caption/Off/sync/position; no new entry
API is needed. New natural long/multilingual ASR/translation, comfortable caption
screen timing, real Chrome extension discovery/save/navigation, Windows11/RTX setup,
VRAM and recovery, conservative enhancement and search/recommendation usefulness
remain acceptance work. No new paid translation or real-model comparison this slice.

Existing Chrome EPERM/supplied-browser ERR_BLOCKED_BY_CLIENT and Fetch extension
policy denials remain. No other browser/CDP/profile/proxy or model-inference CI
workaround. Approved synthetic model-free Ubuntu/Windows CI is separate evidence.
