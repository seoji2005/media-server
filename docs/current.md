# Current work

## Scope

Current task: **harness-only revision** for the clarified scope and long autonomous Work
runs. The previous restriction has not been replaced by an explicit app-implementation start.
No application source, server, UI, model dependency, model download or media is included.
Latest decisions: custom app preferred when quality/control justify it; no downloading,
AI video generation or NAS integration this release. Watching, preparation, analysis,
search and basic recommendation target near-finished use before October leave. The owner
names October 12 or 19, 2026 (unconfirmed): plan readiness by October 11; any extra week
is for quality and defects. Working targets: integrated candidate October 5, stabilization
October 6–11, subject to measured progress and actual target-hardware access.
Long active runs should advance several verified slices, checkpoint and resume. No native
recurring task or unattended application implementation has been started by this revision.

Remote starting point: `seoji2005/media-server` main at
`0faf1906211be12ad94870db2b1fc71e76df53c4` (initial README only).
Use `git rev-parse HEAD` / `python scripts/harness.py status` for the current revision;
do not embed a self-referential commit hash here.

## Harness acceptance

- Outcome: a new agent can recover scope, commands, evidence rules and one next action.
- Non-goals: product implementation, production runtime, model selection and release.
- Acceptance: concise source-backed policy for all four organizations; selective donor
  decisions; dependency-free check/status/run commands; unconfigured product execution
  must fail honestly; no app/private payload in the commit.
- Failures: wrong repo, stale/missing docs, invalid command shape, broken local links,
  child failure hidden as success, placeholder app success, legacy process migration.
- Verification: run check/status; exercise absent commands, invalid config and command
  exit propagation in temporary copies; inspect staged files and remote branch diff.

## Evidence

Baseline c920516: harness check and Python compilation passed on Linux/Python 3.12. Ten focused CLI
cases passed: unconfigured test/start (2), committed status, child exit-code propagation,
literal arguments without a shell, invalid command shape, broken link, missing document,
invalid JSON, malformed-URL private sentinel. Temporary copies isolated failure probes.
Independent review found one input-leak error path; safe exception handling fixes it.
Status now distinguishes configured repository from unverified remote identity.
This revision changes existing guidance only; runner/config are unchanged. Verify document
links/config and scoped diff before publishing; reuse unchanged CLI evidence. Product remains
**contract only**; no application was run. Donor evidence is separately bounded in [donor.md](donor.md).
Research sources and reversal conditions are in [engineering.md](engineering.md).
Guidance revision verification: harness check and diff check passed; independent scope/
autonomy review found no IMPORTANT or BLOCKER contradictions in the five-file delta.

Implementation handoff fields: milestone / branch / last verified revision / actual command
and result / input-model identity / WIP / blocker / next action. Keep private payloads out.
On resume inspect live Git/PR state and preserve newer work; WIP is not passing evidence.

## Single highest-value next task

When the owner starts implementation: deliver import → MediaItem → library → playback →
persisted resume, verify actual restart/browser behavior, then continue to real Korean
subtitle watching within the authorized milestone instead of stopping after every commit.
Use the acceptance/failure cases in [product.md](product.md). Register real test/start
commands only when they exist. Probe enhancement feasibility early during subtitle work.
Preserve owner final merge/release decisions. Do not wait for October 12 versus 19 to
be settled before feasible preparation; use the earlier date until the owner clarifies.
