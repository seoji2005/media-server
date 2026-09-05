# Engineering policy · researched 2026-09-05

Optimize October delivery, real quality, time/token efficiency, maintainability,
privacy and original safety. These are project decisions inferred from primary
engineering sources, not measured Astra performance claims. Token usage is unknown
unless the environment reports it; use elapsed time and repeated work as proxies.
The release deadline is before the owner's October leave; its exact date is still open.

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
