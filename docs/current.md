# Current work

Milestone: `fix/qwen-setup-system-https`, based on live Server main
`13e878a060bb6eef5e9cc75dc1eb28e6b2f2c5ce` (PR41 merged). Local restored
base `eb11e960a6a8eda7dc09f207ac90294e0a8dd93c` has the same complete tree
`0286766a32aa8c009553330176e9c57be0632299`; publish using actual remote ancestry.
Fetch main remains `0d6aa28a4a0c6944c053e3d63e150908b44b9175`. No open PR at
start. Owner implementation, network/API cost/allowed egress, independent review
and passing development-merge approvals persist; release is separate.

## Delivered and current fix

Gemini 3.8, foreign SRT/VTT translation, exact Fetch entry, shared installation pins,
bounded preparation/status recovery, titles and complete caption search are merged.
PR41 adds VP9 MP4/copied-video WebM playback with selected Opus audio when required;
its independent review, Ubuntu/Windows CI34604412473 and four native playback screens
passed. Originals, captions and viewing state are preserved. HEVC/10bit remains open.

Owner-supplied diagnosis distinguishes two setup failures. HTTPX initializes an
unneeded SOCKS ALL_PROXY even when an HTTP/HTTPS proxy is configured for HTTPS;
without socksio its default client fails locally before requests. Explicitly selecting
the existing HTTPS route constructs HTTPX/Hugging Face clients without installing
socksio. The execution tool's separate approval-cancellation error is not fixed by this.

The model preparation command gains explicit `--use-system-https-proxy`. It uses
nonempty lowercase https_proxy before HTTPS_PROXY and requires a valid HTTP/HTTPS
URL. Missing/invalid settings fail without echoing addresses or credentials; no
ALL_PROXY/direct/mirror fallback. Only this setup process changes its HF client
factory. System variables, model pins, product inference and dependencies are unchanged.
TLS/certificate environment settings stay enabled, as does the installed HF request
hook's offline guard. Missing factory/hook APIs stop; no blind package upgrade.

## Evidence and next action

- Reproduced default socksio ImportError in HTTPX0.28.1/HF1.31.0. Explicit HTTPS
  client and get_session creation passed with socket.connect/connect_ex blocked;
  zero external requests. No assertion of HTTP/authentication/download success.
- Focused tests use real HTTPX, TLS context and optional installed HF. They verify
  SOCKS-free construction, certificate environment/verification, missing-CA failure,
  proxy precedence/validation, safe CLI rejection and HF offline blocking.
  Minimal dev/CI environments skip only the optional actual-HF check; the model
  environment runs it. Preserve that skip distinction in the final PR evidence.
- Freeze, obtain independent setup/privacy review, then inspect required model-free
  Ubuntu/Windows CI before development merge. No UI changed; no new screenshot gate.
  Observe CI at most10minutes/10polls, without rerunning unchanged failures. Final
  fixed-HEAD review, test and merge results belong to the PR and verification archive.

## Execution restriction and remaining acceptance

Previous bounded pip and unchanged-HTTPS HEAD requests returned
`network approval was cancelled before a decision was returned` after roughly10s.
The tool did not establish whether user action, approval service or policy caused it.
User consent exists. A later offline audit found no reusable socksio/model assets;
those cache scans and prior successful Torch/Transformers installation logs do not
prove current network recovery. No repeat install/download/read request in this fix.

Do not retry blocked requests merely because this local initialization fix passes.
Require evidence that execution access is restored, then supervise model preparation
and new natural long-speech Qwen→aligner→Gemini3.8 with finite total/no-progress/retry
bounds. HF per-request timeouts/retries are not a whole-download deadline. Terminate
owned processes on limits or repeated approval cancellation; preserve assets and
committed spans/batches. Never use direct/alternate proxy, mirror, browser/CDP/profile
or CI inference to evade restrictions. Existing default Gemini routing is unchanged.

New natural long-caption quality, actual Fetch extension, Windows11/RTX4070SUPER,
useful enhancement and subjective search/recommendation acceptance remain incomplete.
Previously held706.24s/762.048s speech informed comparisons and is not a pristine
holdout. No new model/API calls or target-device acceptance in this setup-only fix.
