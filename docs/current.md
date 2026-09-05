# Current work

## Scope

Owner's latest instruction: **create only the harness and push it to media-server**.
No application source, server, UI, model dependency, model download or media is included.
The earlier vertical-slice request is deferred by this narrower instruction.

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

Harness check and Python compilation passed on Linux/Python 3.12. Ten focused CLI
cases passed: unconfigured test/start (2), committed status, child exit-code propagation,
literal arguments without a shell, invalid command shape, broken link, missing document,
invalid JSON, malformed-URL private sentinel. Temporary copies isolated failure probes.
Independent review found one input-leak error path; safe exception handling fixes it.
Status now distinguishes configured repository from unverified remote identity.
The commit contains exactly nine harness/config/guidance files. Product evidence remains
**contract only**; no application was run. Donor evidence is separately bounded in [donor.md](donor.md).
Research sources and reversal conditions are in [engineering.md](engineering.md).

## Single highest-value next task

When the owner requests application implementation: deliver import → MediaItem →
library → playback → persisted resume, then test real process restart and browser flow.
Use the acceptance/failure cases in [product.md](product.md). Register real test/start
commands only when they exist; proceed to real ASR→Korean subtitles after the slice.
