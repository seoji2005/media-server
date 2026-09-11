# Current work

Milestone: `test/bounded-long-speech`, stopped during model setup.
Latest live main `34b7984415b496bd8da3143acf9ad6aeee2825fe` (PR35/36 merged)
matches local base `9cb4ec696a468a32278fbed67ed3cf02ef4af419`, tree
`3cf41ed0cb679c110ec24e3e1e2f827d7187163d`. No open Server PR at start.
Fetch PR22 is merged at `0d6aa28a4a0c6944c053e3d63e150908b44b9175`.

## Owner stop instruction

Stop work that hangs or loops. Before a long command, set a finite elapsed bound,
meaningful progress observation and a retry cap. Bound CI polling as well. Stop owned
processes at the bound, preserve originals and complete checkpoints, report the stop;
do not continue through alternate routes or silently treat a partial run as complete.
This instruction is now in AGENTS.md. Prior implementation/review/development-merge
permissions persist, but do not require retrying a blocked task or approve release.

## What ran

The existing Linux CPU environment had Torch/Transformers but no Qwen model weights,
librosa, nagisa or soynlp. Current requirements-qwen.txt installed successfully with
an external120s bound, pip15s network timeout and zero pip network retries.

The intended next acceptance sample is an already-held, public Japanese dialogue
recording, 706.24s or762.048s, with reference annotations. No new audio download,
transcription, alignment, translation or quality judgment was made in this slice.

Product model preparation was wrapped with a180s elapsed bound and90s without asset
progress, TERM then bounded KILL cleanup, no automatic model retry. The first attempt
exited1 in2s, before downloading assets: Hugging Face's configured SOCKS route needs
httpx's optional socksio dependency, which is absent in this environment.

One bounded dependency repair was attempted (45s outer bound,10s pip network timeout,
zero pip network retries). The execution tool returned: network approval was cancelled
before a decision was returned. The saved pip log also records proxy connection timeout
during dependency resolution. The task was stopped; the second model download was
never started. Read-only cleanup confirmed no owned pip process remained.

The owner then explicitly renewed network approval. One targeted socksio1.0.0
installation was attempted with the same45s/10s/zero-retry bounds, avoiding HTTP-client
version changes. The tool again returned network approval cancelled before decision.
The same execution-limit cause repeated; stop instruction applied, no further retry
or alternative route. User authorization exists; execution approval handling/network
availability is the unresolved boundary, not a missing blanket user permission.

Model bytes0; actual ASR/alignment/translation calls0. No new product-code change or
model-quality result. Setup failure and raw logs remain outside Git; source media and
existing results were not overwritten. Only this handoff and the stop instruction
are checkpointed. Do not mark this as completed long-video acceptance.

## Resume conditions and remaining work

Resolve the missing proxy dependency and network execution limit before any further
setup. Do not repeat the same failed installation or switch route without new evidence.
Then use a fresh bounded output directory and current product Qwen/Gemini3.8 path for
new continuous speech, preserve per-span evidence, and distinguish observed ASR/alignment/
translation quality from fixture recovery. Declare stall/elapsed limits before starting.

PR35/36 and Fetch22 already delivered Gemini3.8 adoption, foreign SRT/VTT import,
corrected scene runtime and exact Server item entry. Their prior independent review,
Ubuntu/Windows CI and Native/Server evidence remain valid; no reruns were performed.
Actual Chrome extension flow, natural long-caption viewing, Windows11/RTX setup/VRAM,
conservative enhancement and useful search/recommendations remain unaccepted.
Existing browser/profile/CDP/proxy and model-inference CI workaround prohibitions remain.
