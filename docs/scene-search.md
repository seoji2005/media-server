# Local visual candidates · 2026-09-06

Open a video → **장면 찾기 → 화면 내용으로 찾기 → 장면 검색 준비**.
Preparation reuses or creates the video's time previews, then saves their visual
vectors. **잠시 멈추기** or closing the panel stops after the current request; reopening
and preparing resumes. Enter a short description and choose a candidate image/time
to seek and play. This works without subtitles. Queries clear on leaving the video.

This is approximate search of at most 120 sampled frames from **one selected video**.
It can miss short scenes and returns nearest candidates even when the requested scene
is absent. The UI says so, shows evidence images/times, and does not display confidence
percentages or claim “no match.” Opening the panel can expose later scenes. No global
index, recommendation learning, query history, automatic tags or summaries were added.
The earlier [36-frame development evaluation](scene-retrieval.md) is separate from
this integration test; neither establishes held-out quality or October completion.

## Local model setup

Use the same Python environment that runs the app. The optional
`requirements-models.txt` supplies Torch/Transformers/SentencePiece and Pillow;
follow [the existing CPU/CUDA installation notes](subtitles.md) for the Torch wheel.
Prepare an ordinary local directory at `<data-dir>/models/scene`, without symlinks,
from the ungated [Google SigLIP2 Base/16-224 repository](https://huggingface.co/google/siglip2-base-patch16-224/tree/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2)
(declared Apache-2.0; source revision `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`).
Required files: `config.json`, `model.safetensors`, `preprocessor_config.json`,
`tokenizer.json`, `tokenizer.model`, `tokenizer_config.json`, `special_tokens_map.json`.
Weights are about 1.50 GB; setup is separate from the app, which never downloads them.
Retain the upstream license/attribution with the local model. No new license gate was
accepted or new network download attempted in this integration slice.

The existing `models/settings.json` device applies to scene inference too. Linux uses
CPU by default; Windows selects CUDA unless explicitly configured otherwise. Missing
CUDA is reported without silently changing devices. This adapter uses float32 and
four CPU threads; actual Windows/CUDA/12 GB fit has not been measured.

## Persistence and failures

Schema 4 adds only `scene_vectors`, linked to existing preview-set/frame identities.
Each four-image batch commits independently; a request handles at most 20 images.
Completed vectors survive restart. Changed frame/model/config/package/device identity
requires re-preparation; corrupt derived vectors are rebuilt, without altering images,
originals or subtitle versions. Model identity uses local path/stat/package metadata
and hashes of files ≤64 KiB, not whole-weight hashing or authenticated provenance.
Queries analyze saved images and do not rescan the video in each model child.

A bounded child loads only local safetensors, denies Python socket connections, disables
HF telemetry/network resolution and shares the existing subtitle worker lease. Queued
subtitle work waits; active work yields a retryable busy message. Each child exits after
its request to release memory; this incurs model/import latency on every query. A
120-second timeout or server death ends the child; earlier four-image commits remain.
The selected-video POST carries the query in its body, never the URL/DB/logs. Existing
loopback/token/CSP/no-store boundaries and preview image integrity checks still apply.
These controls are not an OS-level packet audit. Watching stays independent of inference.

## Actual evidence and limits

At `04cc5be` on Linux/Python 3.12.13, real Torch 2.8.0+cpu/Transformers 4.57.1 inference
used the already permitted **12m14s Tears of Steel** sample and existing SigLIP weights.
The app extracted **74** preview frames. The server was actually killed after **4**
vectors committed (~4.09 s from the first request); the model child released its lease.
Restart/browser preparation finished 74/74, preserving those four rows byte-for-byte.
Completing the remaining analysis took **29.13 s including the playback check/held
response**; this is not pure inference throughput. No ASR was run on this movie.

Chromium **149.0.7827.0**, Linux headless, real decoded WebM playback:
- Korean “다리 위에 서 있는 두 사람” returned the matching bridge/couple image first.
  Actual UI query latency: **4.376 s**, then **3.890 s after server restart**.
- Keyboard selection sought **34.724 s**; reopening restored the completed seek.
  Real video advanced during preparation; no media error occurred.
- At final code `029f9e0`, the 74-vector index was reused without rebuilding. Desktop
  1440×1080 and mobile 390×844 were inspected; the five candidates have no nested
  scroll cutoff. Candidate selection scrolls the video into view.
- A sampled-absent snowy-mountain query still returned five unrelated candidates,
  including black frames. The approximation warning remains essential. This does not
  establish a usable absence threshold or general retrieval accuracy.
- Page errors/external page requests **0**, server log **0 bytes**. All **21** prior
  subtitle-track rows, **15** file rows and **15** item/history rows remained unchanged.
  Both query strings were absent from the SQLite dump. Model/browser QA used public
  content only; no new private media transfer or target-hardware claim.

`python -m unittest discover -s tests -q`: **120 passed / 39.136 s** before the bounded
cleanup fix. After it, `-p test_scenes.py`: **7 passed / 4.614 s**, plus the scene DOM
script; the earlier six UI scripts also passed. DOM tests mock HTTP/media and are
separate from Chromium evidence. A fresh reviewer reproduced a broken-pipe cleanup
bug retaining the subtitle lock; the nested-finally fix and real early-child-exit
regression resolved it. At fixed `029f9e0`, independent reproduction confirmed lock
release and no additional actionable findings in that delta. Final changes after this
code revision are documentation only. Windows/RTX, held-out content, long-ASR recovery
and an acceptable enhancement preset remain open.
