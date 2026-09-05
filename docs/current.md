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
`harness/initial-workflow`, R2 starting head `2fdf65296ef3370babe024e7dff9b6d97abf40cb`.
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
commit-event task and separate conversation binding have also been read back. After the
owner's manual follow-up, it is **SINGLE_RESULT_TRIAL_ARMED**: the next useful ready
push may publish one final result under its policy. Comments/reviews remain disabled
for that reviewer task; the coordinator remains no-write dry-run.

R2 in manual [comment #5550545835](https://github.com/seoji2005/media-server/pull/1#issuecomment-5550545835)
reproduced on that starting head: `result.attempt=True/1.0` or request `target.pr=True`
selected `MILESTONE_COMPLETE`; malformed attempts could also escape as stale/duplicate.
The repair validates positive builtin integers before any identity/attempt comparison,
including request/result/live PR and processed-checkpoint PR/attempt fields.

Local changed-behavior evidence: the expanded `python -m unittest discover -s tests -v`
first failed against the unchanged starting code (19 test methods, 86 failures
and 2 errors), then passed **19 tests** after repair. Coverage includes bool/float,
nonpositive values, numeric impostors, stale/duplicate shortcuts and malformed later
checkpoint entries; valid PASS/FIX, retries and unrelated/stale/duplicate results remain.
`python scripts/harness.py check` and `git diff --check` pass. Evidence class: **synthetic
fixture / contract only**; no actual event consumer or automatic writer was added.
Use the current Git revision for this repair's checkpoint; the starting head identifies
the failing baseline, not the fixed code.

Prior setup evidence retained: the PR-body ready-before-ref sequence was observed for
`2fdf652`; recovery verified its 11 remote blobs and tree
`0a03dfc16a89fcbcd13b3fef6a6e3d229fbabe49` in a clean directory. Shell Git lacks
credentials; use the GitHub app for remote access. This proves source snapshot/tool
recovery, not complete commit ancestry or a scheduled execution's environment. Older
ambiguous local WIP remains untouched.

The R2 result was posted once as `source.kind=manual`, `run_id=null`; it is not an event
review. The coordinator reported an actual `issue_comment` webhook wake, but its event
lacked a comment ID. Exact comment-to-run linkage, independent event review provenance,
shared writer serialization and durable scheduled-run/checkpoint recovery remain
unverified. No full round trip is established and no automatic follow-on writer is enabled.
Product evidence remains **contract only**; no real model, Windows, target RTX or human
quality review has run. Reuse prior unchanged harness CLI evidence in Git history.

## One next action

If this R2 repair is not yet published, set PR-body `ready` to its exact future head/current
base and attempt 1 (new code target), then update the branch and verify remote coordinates.
Otherwise inspect the live matching head and the independent Work's armed synchronize
run and any single result it posts;
follow [the trial](engineering.md#first-real-trial), never repush merely to wake a task.
Keep the coordinator no-write dry-run while provenance/ownership are unknown. Record
the actually observed edge and missing evidence; manual execution is not event success.

Keep one concise Work checkpoint: milestone / branch / last verified revision / command
and result / handled target-attempt-comment / WIP / blocker / next action. Refresh this
handoff only alongside useful work. Missing state blocks writes; no report-only commits,
acknowledgment comments or empty wake-up pushes. Harness PASS ends this milestone; the
first import → library → playback → persisted-resume app task still needs owner approval.
