# Current work

## Scope and live starting point

Current milestone: **harness and GitHub event setup/verification only**. Application
implementation still requires the owner's separate milestone approval. No server, UI,
model installation, model download or private media belongs in this change. Product
scope remains in [product.md](product.md): local preparation/watching before October
leave, no downloading/AI generation/NAS; plan readiness by October 11 for the earlier
possible leave date. The donor `seoji2005/media-clarity-studio` remains read-only.

Verified starting state: `seoji2005/media-server` main
`0faf1906211be12ad94870db2b1fc71e76df53c4`; only open PR **#1**, Draft,
`harness/initial-workflow`, starting head `48b5cfff9d9577c680f9a82b22c03b2a686e70fd`.
Re-read live state on resume; use `git rev-parse HEAD` / `python scripts/harness.py status`
for the current local revision rather than assuming these starting coordinates persist.

## Acceptance and current evidence

- Outcome: one writer and a separate independent Work can exchange an explicitly
  requested review without confusing WIP, stale results, self-reports or owner authority.
- Non-goals: application work, a scheduler/authentication/lock platform, automated merge.
- Acceptance: useful harness push; actual independent event run and result comment;
  event-driven implementation resume; safe duplicate/stale/overlap/recovery behavior.
  Task creation, manual execution and synthetic checks do not prove that chain.
- Failure cases: wrong PR/base/head, duplicate/out-of-order result, no verified source,
  missing checkpoint or shared ownership, absent app authorization, event/comment loops.
- Verification: inspect live GitHub and native task records; run the focused synthetic
  policy tests and existing harness check; publish only the scoped useful change.

Verified setup on 2026-09-05: GitHub app pull/push/admin access; Python 3.12.13, Git 2.51.1.
The implementation receiver is enabled in **dry-run**, event-only, scoped to PR #1 comments.
Receiver bindings, native-schema observations and protocol are in
[engineering.md](engineering.md#event-handoff). The daily “Media Clarity 진행 정체
점검” task is unchanged and read-only. The independent reviewer's enabled PR #1
commit-event task and separate conversation binding have also been read back. Its first
event run intentionally selects an action without publishing a result.

Local changed-behavior evidence: `python -m unittest discover -s tests -v` passes **13
tests** for action selection, including stale base/head, duplicates independent of run ID,
explicit retries, source mismatch, insufficient evidence, ownership and lost checkpoints.
`python scripts/harness.py check` and `git diff --check` pass. Evidence class: **synthetic
fixture / contract only**. Input facts are simulated; no live source verification,
cross-cloud serialization, durable queue recovery or actual event delivery is proven.

Fresh-environment probe: recovered all nine starting-revision blobs through the GitHub
app, verified blob hashes and tree `56f73e32a92e2ad8f410058325ca593b6c63924b`, and passed
harness check in an isolated fresh directory. Shell Git lacks credentials; use the app
for remote access. This proves source snapshot/tool recovery, not complete commit
ancestry or a scheduled execution's environment. Ambiguous older local WIP was preserved
untouched; the active author uses a clean recovered checkout.

The independent Work's initial manual report identified the absent review request/protocol
and environmental limits; this revision addresses the protocol, not the remaining limits.
A receiver `last_run_time` was observed after that comment, but no run detail establishes
causality or event-driven conversation resume. It is not evidence of the full chain.

Unverified: API-authored comment eligibility; push/body update event ordering; both actual
event runs and return-result publication; accessible run provenance; shared writer
serialization and scheduled-run recovery. No exposed tools currently establish the last
three. Event receivers must remain dry-run; no automatic follow-on writer is enabled.
Product evidence remains **contract only**; no real model, Windows, target RTX or human
quality review has run. Reuse prior unchanged harness CLI evidence in Git history.

## One next action

Both reservations are prepared. If this useful change is not yet published, stage PR-body
`ready` with its exact future head/current base, then publish it. Once the live request
and head match, inspect the independent Work's first synchronize dry-run; never repush
merely to wake a task. That Work currently posts no event result; it must inspect the
dry-run and enable its own single result-publication trial before the return edge can be
tested. Follow [the trial](engineering.md#first-real-trial), record the actual broken or
unobservable edge, and keep implementation dry-run while provenance/ownership are unknown.

Keep one concise Work checkpoint: milestone / branch / last verified revision / command
and result / handled target-attempt-comment / WIP / blocker / next action. Refresh this
handoff only alongside useful work. Missing state blocks writes; no report-only commits,
acknowledgment comments or empty wake-up pushes. Harness PASS ends this milestone; the
first import → library → playback → persisted-resume app task still needs owner approval.
