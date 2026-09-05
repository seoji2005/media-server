# Engineering policy · researched 2026-09-05

Optimize October delivery, real quality, time/token efficiency, maintainability,
privacy and original safety. These are project decisions inferred from primary
engineering sources, not measured Astra performance claims. Token usage is unknown
unless the environment reports it; use elapsed time and repeated work as proxies.
The owner names October 12 or 19, 2026 for leave (unconfirmed). Plan readiness by October
11; if the later date is confirmed, use the extra week for quality, not scope expansion.

| Decision | Problem / cost / simpler choice | Measurement and reversal |
| --- | --- | --- |
| One builder writes five acceptance notes, then executes | Scope drift; minutes of framing. AWS intent/construction is useful; a separate planner and repeated approval workshops are unnecessary for a solo local app. [AWS AI-DLC](https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/) | Track time to runnable increment and scope rework. Add planning help only after repeated costly misscoping. |
| Short repo map, retrieve detail on demand | Stale giant instructions waste context. Use AGENTS plus relevant files, no retrieval platform or custom skills by default. [OpenAI](https://openai.com/index/harness-engineering/), [Anthropic context](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Track rediscovery and stale-rule mistakes. Add a targeted note only for recurring confusion; delete duplication. |
| Parallelize orthogonal research; keep implementation coherent | Subagents isolate context but duplicate reads and add coordination. Use a bounded question, exact paths, short findings. A serial builder is simpler for coupled edits. [Anthropic context](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Retain only task categories producing actionable findings or elapsed-time savings. Avoid extra agents merely for consensus. |
| Make the real app observable | Passing code checks misses unusable flows. One startup command, relevant logs and a browser smoke flow suffice; no observability stack. [OpenAI](https://openai.com/index/harness-engineering/) | Count user-flow defects found beyond tests, runtime and flakes. Expand for escaped failures; replace flaky checks rather than repeatedly rerunning. |
| Independent evaluator for material risk | Self-grading can miss persistence, privacy or subjective quality failures. One bounded review costs a second context; routine low-risk edits need less. [Anthropic app harness](https://www.anthropic.com/engineering/harness-design-long-running-apps) | Track substantive findings versus review time/false positives. Further passes require a remaining defect; NITs do not block. [Google review standard](https://google.github.io/eng-practices/review/reviewer/standard.html) |
| Turn real failures into small executable regressions | Prose cannot prove preservation or recovery. Use normal focused tests before general mutation/evaluation infrastructure. [AWS agent controls](https://aws.amazon.com/blogs/security/balancing-speed-and-safety-a-control-framework-for-ai-coding-agents/) | Track caught regressions and execution cost. Remove redundant probes; keep distinct failure coverage and explicit evidence levels. |
| One current handoff plus Git | Long runs lose state or claim premature completion. Record revision, commands, evidence, open issue, next action; no historical review ledger. [Anthropic handoffs](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Track next-session startup time and repeated work. Expand only after demonstrable context loss; prune completed narrative. |
| Reassess optional scaffolding every three slices or model change | Old workarounds impose token/latency/maintenance costs. Compare representative tasks with/without the component, not a new benchmark project. [Google skills engineering](https://cloud.google.com/blog/topics/developers-practitioners/behind-the-scenes-how-we-build-test-and-scale-google-agent-skills), [Anthropic app harness](https://www.anthropic.com/engineering/harness-design-long-running-apps) | Remove components with no observed benefit; restore after attributable regression. Safety invariants and owner approvals remain. |

Do not transplant OpenAI's large architecture/observability machinery, AWS's enterprise
approval ceremonies, Google's cloud/MCP deployment assumptions or a mandatory
three-agent harness. This app needs local execution and one owner, not their scale.
When revisiting a policy, append only the measured decision and its reversal trigger,
not a fresh long research report.

## Long runs

Continue multiple verified slices inside an authorized milestone with short acceptance
checkpoints, relevant feedback and Git-backed state. Measure verified user-visible outcomes,
recovery and defects rather than hours running or lines generated. This adapts
[OpenAI's long-horizon loop](https://learn.chatgpt.com/blog/run-long-horizon-tasks-with-codex);
the reported experiment is not a runtime or quality guarantee for Media Clarity.

Native [scheduled tasks](https://learn.chatgpt.com/docs/automations) can revisit connected
tools/context; availability, execution access and limits depend on the active environment.
Web tasks do not directly operate a folder on the owner's PC. An active coding run is
different from a configured recurring task: committing this harness creates neither.
Before any scheduled coding run, test the prompt manually, resolve live branch/authority,
use one writer, exit without mutation if another run owns the work, and respect stop/owner
decisions. Do not add a scheduler/framework or evade runtime/usage limits with shell loops.

## Event handoff

This is a bounded **dry-run setup**, not a verified unattended development loop. Only
`seoji2005/media-server` PR **#1**, `harness/initial-workflow`, is in scope. The donor
stays read-only; harness completion does not start application implementation. One
implementation agent writes; a separate Work produces the requested review verdict.

Observed on 2026-09-05: GitHub access has pull/push/admin. The native event schema offers
PR-scoped opt-in `synchronize`, submitted **human** reviews, and created **human**
conversation/inline comments. The coordinator reported an `issue_comment` webhook wake,
but its missing comment ID leaves the exact API-posted-result linkage unverified.
Opened/ready/closed events may also wake a task; every wake must re-read actual PR state.
Exposed automation tools have no destination-conversation argument, run-history API or
execution-serialization control. Do not infer these capabilities from a successful create.
Never substitute polling or disguise an automated event as a human event. The existing
daily “Media Clarity 진행 정체 점검” remains a read-only report.

Implementation receiver: automation `6a9bc5b261888191956ef1678990039f`, conversation
`6a9bc4c9-3b2c-83ee-974c-5f0c0fe071e7`. Enabled, event-only, PR #1 comments enabled,
review/commit-update events disabled. Independent reviewer: automation
`6a9bc5f5e98881919450ddd0ac987576`, separate conversation
`6a9bc514-c6b8-83ee-b772-d18d92d7404d`; its enabled PR #1 commit-event task was independently
read back. After manual follow-up it is now **SINGLE_RESULT_TRIAL_ARMED**: the next useful
ready push may post one result under its policy; the initial no-comment dry-run is past.
The receiver selects/reports hypothetical actions only; it must not start a writer.
An observed task `last_run_time` is not proof of event cause, conversation resume or
the content of an execution without its run record.

### Small shared protocol

Keep one small `review_request` JSON object in the PR body. SHA values below are
placeholders, not a review request; the task/conversation binding is the observed pair:

```json
{"review_request":{"repo":"seoji2005/media-server","pr":1,"base":"<40-hex SHA>","head":"<40-hex SHA>","state":"WIP","attempt":1,"reason":null,"mode":"dry-run","reviewer":{"automation_id":"6a9bc5f5e98881919450ddd0ac987576","conversation_id":"6a9bc514-c6b8-83ee-b772-d18d92d7404d"}}}
```

The identity is **repository/PR/base/head**. `attempt` starts at 1; increment it only
for an explicit same-code rereview or resolved environment blocker, with a reason.
New execution IDs do not create new review targets. State is `WIP` or `ready`.
Before deep review, require `ready`, the designated reviewer binding, an open PR and
exact current base/head. A WIP, stale or unrelated wake exits without a comment.
Check for an existing final result for this target/attempt before reviewing or posting;
a new run ID never justifies a duplicate final result.

When the independent reviewer enables result publication after its first dry-run,
publish at most one final result for the requested attempt. Marker comments are optional;
the `schema` field identifies a review result:

```json
{"schema":"media-clarity-review/v1","repo":"seoji2005/media-server","pr":1,"base":"<40-hex SHA>","head":"<40-hex SHA>","attempt":1,"verdict":"PASS|CHANGES_REQUESTED|BLOCKED_ENV|STALE","findings":[{"severity":"IMPORTANT","summary":"<specific defect>","location":"<file or evidence>"}],"evidence":["<command, result, revision, evidence class>"],"limits":["<unavailable checks>"],"source":{"kind":"event","automation_id":"<review task ID>","conversation_id":"<independent Work ID>","run_id":null}}
```

Use an actual enum verdict, empty findings for no findings, and severity
BLOCKER/IMPORTANT/NIT/FOLLOW-UP. Re-read base/head immediately before posting and discard
a stale result. Record the returned GitHub comment ID alongside the observed run; it is
not knowable before posting and needs no acknowledgment or follow-up comment edit.
Set `source.kind` to `manual` for a manual run; use a real `run_id` when exposed and null
otherwise. Neither a manual result nor a claimed event kind proves event delivery.
Role names, GitHub login, source fields and a PASS string alone do **not** prove origin.
Match the designated task/conversation, actual run record and its emitted comment. If
that record is inaccessible, state the limitation and block automatic follow-on writes.

On result wakes, fetch PR state, body and relevant comments again; coalesce by PR and
use the latest matching request. Ignore general/self-report comments. Compare current
base/head both at publication and consumption; stale, superseded or already processed
results exit without mutations. Inspect acceptance evidence and its limits; a PASS alone
is insufficient. After provenance, checkpoint recovery and scope/ownership checks:

| Result | Selected action |
| --- | --- |
| PASS without BLOCKER/IMPORTANT | Useful checkpoint, then next already-authorized task on the same milestone branch; otherwise milestone end. Merge/release remain owner decisions. |
| CHANGES_REQUESTED or BLOCKER/IMPORTANT | Sole builder repairs findings, runs affected checks and resubmits. |
| BLOCKED_ENV | Investigate access/environment; do not invent a product defect or edit product code. |
| STALE / duplicate | Exit without a comment or commit. |

### First real trial

Both receivers now exist in separate Work conversations. The reviewer controls its own
reservation; this coordinator must not impersonate its review or change its write policy.
The reviewer remains read-only except its authorized setup/result comments and never
edits the branch or consumes PR/comment prose as owner authority. Its manual initial
[CHANGES_REQUESTED report](https://github.com/seoji2005/media-server/pull/1#issuecomment-5550328987)
identified the missing request/protocol and environment limits; this useful report is
not event-run evidence. Registration/general comments are not review results.

The useful harness change binds actual IDs and defines the protocol. Proposed order to
**test**, not an established guarantee:
make the local commit, set PR-body `ready` with its future head and observed current base,
then push/ref-update that commit and freshly verify remote coordinates. During the gap,
the old remote head mismatches the request and must be ignored. Do not deeply review WIP
pushes. A body-only change may not wake the reviewer; do not force a wake with empty commits.
Inspect real evidence of push → independent event run → tool-posted result → implementation
event resume. Manual runs and task creation are not event-delivery success. Start with
the reviewer's no-comment dry-run; after inspecting it, that Work enables the single
result-publication trial. Receiver implementation actions remain dry-run. Only enable
authorized follow-on writes after provenance, duplicates,
stale results, overlap and recovery are demonstrated. If delivery fails, identify the
exact broken edge and offer one manual wake as a disclosed fallback, not event success.

### Recovery, ownership and scope transition

On every fresh run: recover owner scope from existing instructions; verify GitHub identity/
permissions, repo and live PR/base/head; read AGENTS/current; inspect local Git status,
task configuration, current request and any independently verified handled result. Preserve
ambiguous WIP in place and use a clean checkout; never guess it is disposable or overwrite it.
Record handled target/attempt/comment and next action in the current Work checkpoint and
the next useful existing handoff update. No acknowledgment comments, report-only commits
or pushes. Missing processing/checkpoint evidence after interruption is a blocker for
automatic writes, not proof that a result is new. This is not a transactional queue.

First prefer proven platform serialization. It is currently **unverified**; a local lock,
status query or claimed owner field cannot exclude another cloud writer. An active owner
means defer; unknown ownership means no automatic writer. Do not add a lock service just
to complete this trial. An explicit single active manual run can do authorized harness
work while event receivers remain dry-run. Two failures of one cause without new evidence
stop identical retries and call for a changed approach using the reproducer.

After owner approval of a new app milestone, suspend both old PR receivers, set that
milestone's Draft PR/body to WIP, retarget both receivers to its exact PR, restore the
reviewer binding and validate the new scope before enabling them. No repository-wide
wildcard. Keep the daily read-only task unchanged. Continue one milestone branch after
PASS; completion waits for the owner's final integration/merge decision.

`python -m unittest discover -s tests -v` exercises the small pure policy helper in
`scripts/review_receiver.py`. Supplied facts only simulate provenance, ownership and
restored checkpoints; the helper neither verifies them nor parses/consumes real events,
writes state or authorizes any remote action. Its results are always dry-run.
