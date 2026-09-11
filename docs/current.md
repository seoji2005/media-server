# Current work

Milestone: `fix/subtitle-worker-cleanup`, based on live Server main
`2002ac029d2d957e175800883f90274fe9283ec4` (PR42 merged), tree
`ba7d8dda8f2aeb49b649a204e06f41e535448f54`. Local restored base
`d12fa62545b35155ec63304689b7aefce8f96f5e` has that exact tree; publish
with actual remote ancestry. Fetch main is `0d6aa28a4a0c6944c053e3d63e150908b44b9175`.
Existing implementation, allowed API cost/egress, independent review and passing
development-merge approvals persist. Release and target-device acceptance are separate.

## Current correction

A real paced FFmpeg reproduction showed that pausing killed only the subtitle
Python worker, leaving its decoder alive after the worker lease was released.
The worker is now a small guardian with a separate compute child. It imports no
models, so parent-EOF handling does not depend on model code releasing the GIL.
On POSIX the supervisor owns a private process group and stops it together.
On Windows a noninheritable kill-on-close Job Object contains the compute child
and descendants; the child waits for a one-byte handshake before model imports.
Failed containment never starts uncontained processing. Windows Job ownership
follows [the native lifecycle](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

Pause waits at most five seconds for the guardian; timeout leaves the operation
failed rather than marking the job paused. The original compute lease, span/batch
transactions, model identities, prompts and PCM decoding are unchanged. A completed
job remains complete if it finished just before stop. No media/credential logging,
new model/dependency, UI, translation retry or automatic restart is introduced.

## Verification and remaining work

The three focused Linux tests use real paced FFmpeg and a real compute child:
explicit pause, parent EOF, and parent EOF while compute holds the Python GIL.
They require both children to stop, the compute lease to become available,
temporary PCM to close and the original hash to remain unchanged. Initial test
instrumentation using `/proc` could not inspect this execution environment's PIDs;
the corrected test uses child PIDs, signal checks and Linux subreaping. Preserve
that failed run separately. No Windows result is claimed before its CI completes.
The combined lifecycle/subtitle/recovery/PCM run passed all 44 tests in 13.085 s
on Linux CPU, with no skips. It does not measure model or perceptual quality.

Freeze the implementation, obtain fresh independent lifecycle/privacy/recovery
review and pass required Ubuntu/Windows product CI before development merge.
CI observation is bounded to ten minutes/ten polls, without unchanged-failure reruns.

Pinned ASR and aligner assets were restored from previously saved archives and
fully hashed. A separate unchanged-main product trial now processes public
dialogue03 (762.048 s) through Qwen/aligner/Gemini 3.8. This is its first full
Qwen product attempt, but its reference text already informed translation
comparisons; it is not a pristine holdout or a completed quality claim. Bounds:
speech 45 min / no span progress 5 min; translation 10 min / no batch progress
2 min; no automatic job retry. Preserve its original, database and completed spans.
That runtime trial does not run this lifecycle correction.

Fetch's existing two real HTTP/Native/FFmpeg integration cases passed against the
exact current Server main tree: download/caption delivery, identified item entry,
saved position/caption offset, receipt recovery and Server restart. The temporary
fixture changed only the expected Server revision. Its first invocation used the
wrong working directory and failed Native startup; the corrected run passed 2/2.
This is synthetic short-media integration, not actual extension/browser playback.

Actual new long-caption perceptual quality, real Fetch extension use, useful video
enhancement, subjective search/recommendation quality and Windows 11/RTX 4070 SUPER
remain open. Existing external-download/browser restrictions are not bypassed.
