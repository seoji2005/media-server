# Local scene retrieval evaluation · 2026-09-06

A real inference checkpoint, **not yet app-integrated search or model adoption**.
PR #8 is merged into main `f0b0010`; its saved previews supply a useful input size.
This experiment tests whether an image/text encoder can rank the frame the viewer
means. Existing playback, captions, jobs, database and recommendations are unchanged.

## Candidate and sample

[Google SigLIP 2 Base/16-224](https://huggingface.co/google/siglip2-base-patch16-224),
declared source revision `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`, Apache-2.0,
ungated. Retrieved the official files at that pinned URL; weights are 1,500,800,904 bytes.
The [official usage documentation](https://huggingface.co/docs/transformers/model_doc/siglip2)
specifies lowercasing and length-64 padding. Installed Transformers 4.57.1 uses the older
Gemma tokenizer, so the probe explicitly lowercases. Inputs over 64 tokens are refused.
The saved slow image processor is fixed, with the app's 320×180 preview size as input.
No remote code, ONNX runtime, hosted inference or new application dependency.

Public *Tears of Steel* — **(CC) Blender Foundation | mango.blender.org**, [CC BY 3.0
attribution](https://media.xiph.org/tearsofsteel/README.txt), [1080p WebM source](https://media.xiph.org/tearsofsteel/tears_of_steel_1080p.webm).
Downloaded 571,346,576 bytes for this permitted developer experiment. Sampling at
5, 25, …, 705 seconds produced **36 JPEGs**, including black/title/credit distractors.
The film mixes live action and CG. This was sparse frame retrieval, not long-video ASR.

[Fixed sample/query manifest](../tests/fixtures/scene_retrieval.json): 20 Korean positive
queries paired with manually written English controls, plus eight absent queries per
language. Relevance was judged from the contact sheets before full-set inference.
Absent means absent from these sampled frames, not proven absent from the whole film.
This is one-film development data, not a held-out or general-quality benchmark.

## Actual results

| Query path | Hit in first result | Hit within first three |
| --- | ---: | ---: |
| Direct Korean | 16/20 | 19/20 |
| Manually written English control | 20/20 | 20/20 |
| Korean → existing local MADLAD → English | 17/20 | 19/20 |

Initial three-frame sanity: 9/9 positive queries; it was too easy to establish quality.
On the full sample, Korean missed the eye device, scarf, sparks and credits at rank 1;
credits ranked 16. Wrong person/place combinations still ranked plausible but incorrect
frames. Positive and absent-query top scores overlap: Korean 0.092–0.159 versus
0.033–0.094; English 0.088–0.201 versus 0.023–0.117. Similarity is **not confidence**,
and a reliable no-match threshold has not been established. No detection-accuracy claim.

Query translation used the already-installed MADLAD400-3B, CPU float32, beam 4,
batch 4, max 128 generated tokens, `<2en>`. Twenty-eight queries took **79.27 s** of
translation plus 0.81 s model loading, peaking at **11,362 MiB process RSS**. It changed
“two people” to “two men” and “scarf” to “necktie.” One translated-query miss may be a
broad/incomplete gold label (`manface_ko`, f485 versus f325/f405); the frozen 17/20 score
is preserved and that case is not treated as clear translation failure. [Observed query
translations](../tests/fixtures/scene_query_translations.json) are retained unedited. The English
control is an authored reference, not an achievable automatic-translation result.

**Decision:** do not add query translation by default. Native Korean has enough signal
for a next, explicitly approximate shortlist with evidence images/timestamps; it does
not justify automatic scene tags, factual assertions or confidence percentages. Evaluate
an upper-size native encoder before final quality adoption. Its metadata request returned
**network approval was cancelled before a decision was returned**; no alternate download
or network-control change was attempted, and no result for that candidate is claimed.

## Reproduce and evidence limits

Use the existing separate model environment: Python 3.12.13, Torch 2.8.0+cpu,
Transformers 4.57.1, Pillow 12.3.0, FFmpeg 6.1.1. No package upgrade was needed.
Keep the model, permitted input, manifest/images and output outside the checkout.
Prepare each manifest frame with absolute input seeking, a single video frame and the
same aspect-preserving 320×180 scale and JPEG quality 4 used by `previews.py`.
Copy the committed manifest beside its `frames/f025.jpg` etc.; then run:

```sh
python scripts/probe_scene_retrieval.py --model /path/to/local/siglip2-base \
  --revision 75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2 \
  --manifest /path/to/probe/manifest.json --output /path/to/new-result
python -m unittest discover -s tests -p test_scene_probe.py -q
```

`--device cuda` measures allocated peak tensor memory separately; no CUDA run occurred.
CLI output contains aggregate counts/fixed errors; reports omit query text and input
paths and require a new external directory. Exact frame/manifest hashes accompany ranks.
The report explicitly marks revision as **declared, not verified**. Small configuration/
tokenizer files are hashed; weight identity uses size/mtime/device/inode, with before/
after change checks. This is not cryptographic proof of unchanged large-weight bytes.
Local-only loading, disabled remote code/telemetry and a Python audit hook prevented
intercepted connections; zero intercepted attempts is not an OS-level packet audit.

Local checkpoints `42e5bc7` → `dbf64a8`: five focused tests passed (0.062 s); actual model
rerun retained 16/20 and 19/20. The original full-sample CPU run encoded 36 images in
5.624 s and 56 texts in 2.965 s, with 0.665 s model loading and 1,208 MiB peak RSS.
These are short batches with warm file caches, not end-to-end interactive latency.
Fresh review verified hashes/ranking and found misleading revision provenance; the
explicit fields/local input descriptions fixed it. Limited rereview: no remaining
findings, with the translated-label ambiguity above retained. No app regression rerun
was needed because application code is unchanged; previous [109-test/browser evidence](previews.md)
remains applicable. Windows/RTX, held-out retrieval, long-film ASR and enhancement remain open.
