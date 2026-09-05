# Engineering decisions · 2026-09-05

Only decisions affecting work belong here. Operating rules are in [AGENTS](../AGENTS.md);
scope is in [product](product.md). Reuse research; revisit changed assumptions.

| Decision / source | Problem, cost and simplest choice | Measure / reversal |
| --- | --- | --- |
| Short entry point; detail on demand. [OpenAI](https://openai.com/index/harness-engineering/), [Anthropic context](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Repeated/stale instructions waste context. Maintain one small map, no retrieval platform. | Track rediscovery and rule conflicts; add a targeted note only after recurring confusion. |
| One owner writes brief acceptance notes and builds. [AWS AI-DLC](https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/) | Scope mistakes cost rework; separate planning workshops cost handoffs. Five notes suffice. | Time to verified behavior and scope rework; add planning help after costly misses. |
| Real execution plus risk-based fresh review. [OpenAI](https://openai.com/index/harness-engineering/), [Google review standard](https://google.github.io/eng-practices/review/reviewer/standard.html) | Tests miss user-flow bugs; extra reviewers duplicate context. One bounded reviewer for material risk; browser/output inspection where applicable. | Substantive defects found versus time/false positives; extra passes require an unresolved risk, never NITs. |
| One handoff and Git checkpoints. [Anthropic long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Sessions lose state. Existing Git plus current.md avoids a queue/lock/provenance service. | Recovery time and duplicate work; extend only for observed loss. Keep runtime/owner boundaries. |
| Reconsider scaffolding at milestone/model changes. [Google skills](https://cloud.google.com/blog/topics/developers-practitioners/behind-the-scenes-how-we-build-test-and-scale-google-agent-skills) | Old workarounds become overhead. Inspect representative work, not a new benchmark program. | Defects, rework, time and actual usage; remove ineffective optional parts, retain safety. |

## Token-efficiency decision

The owner supplied [Coding Apple’s video](https://www.youtube.com/watch?v=2-3F7y5AKJw).
Video title/metadata were accessible; caption endpoints returned empty data, so no
full-transcript review or timestamp-specific claim is made. We checked the tool
authors’ primary documentation instead:

- [Ponytail](https://github.com/DietrichGebert/ponytail): adapt reuse/YAGNI and native
  features. Do not copy a skill pack or optimize for one-liners.
- [RTK](https://github.com/rtk-ai/rtk): adapt compact tool output with built-in
  `rg`, targeted Git output and `unittest -q`. Preserve exit codes, skips and failure
  details. No extra binary, global hook or hosted-client configuration assumption.
- [Caveman](https://github.com/juliusbrussee/caveman): use brief readable reports;
  retain exact requirements/errors. No forced telegraphic speech or prompt proxy.

Output compression is not whole-session savings. A
[JetBrains paired trial](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/)
found no cost benefit in its high-effort RTK setting and higher cost at low effort;
that result is specific to its setup, not Astra. Only trial an add-on if verbose
output remains a measured bottleneck and compare total time/usage, defects and rereads.
Remove it if setup/repair cost or lost evidence outweighs benefit. No new dependency now.

## Keep the playback failure knowledge

Managed playback validates imported SHA and then checks aligned blocks on the same
open descriptor. Size equality alone missed mutations. Restart, eviction or changed
identity/metadata require full verification; changed bytes must not be served with a
stale ETag. Initial full scans can delay long-video playback. Library availability is
not a full integrity certificate. Existing application tests cover these failures.

On Windows, creation time is not change time: cache validation uses native
[FILE_BASIC_INFO.ChangeTime](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_basic_info)
and fails closed if unavailable. Native Windows and browser interrupted-stream behavior
remain unverified. Keep this application safety logic and its regressions even though
the obsolete cross-Work receiver and its protocol-only tests are removed.
