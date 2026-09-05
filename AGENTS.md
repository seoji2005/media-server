# Media Clarity — engineering entry point

Target: `seoji2005/media-server`. Prepare relevant local videos for comfortable
**watching** in one polished personal media service.
`seoji2005/media-clarity-studio` is read-only donor/reference, never the default target.

## Read only what the task needs

1. [README](README.md): commands and working model.
2. [Current work](docs/current.md): verified state and one next task.
3. [Product](docs/product.md): October scope, safety and acceptance.
4. [Engineering](docs/engineering.md): source-backed decisions and reversal conditions.
5. [Donor audit](docs/donor.md): only when reusing relevant legacy code.

## Work through verification

- Before meaningful work briefly state: user-visible outcome, non-goals,
  acceptance cases, failure cases, verification method. Then execute through inspection.
- Prefer a custom app when measured quality/control justify its maintenance cost.
  Exclude all video downloading, AI video generation and NAS integration this release.
  Deadline: before the owner's October 2026 leave; exact start date is still unknown.
- One capable implementation agent by default. Use bounded read-only research or
  an independent evaluator when it adds quality or saves elapsed time. No routine
  planner/builder/reviewer ceremony, model polling or multiple reviewers for consensus.
- Current model capabilities are not fixed in this repo. GPT Work is primary;
  use Claude/another model only for a concrete unresolved risk or owner request.
- For UI, run actual browser flows when tools allow. For persistence, run restart
  and interrupted-write cases. Inspect generated subtitles/media directly.
- Test the changed behavior first. Broaden only for a concrete risk or required gate.
  Reuse unchanged evidence; never rerun everything just to produce a new report.
- Evidence labels: **contract only / synthetic fixture / real CPU/cloud model /
  Windows non-GPU / target RTX / human quality review**. Record command, result,
  revision and limitation. A passing harness or fixture is not a working product.
- Risky architecture, persistence, original safety, privacy, major UI and enhancement
  changes merit bounded independent evaluation. Findings: BLOCKER / IMPORTANT /
  NIT / FOLLOW-UP. BLOCKER stops; IMPORTANT needs resolution or an explicit risk
  decision before merge; NIT never gates progress. Judge on direct evidence.
- Code, routine dependency installation, tests, commits, push and Draft PRs do not
  need repeated approval. Ask for consequential product choices, spending, private
  data egress, destruction, licenses requiring acceptance and final merge/release.
- Never mutate donor branches. Preserve incomplete work before starting elsewhere.
  Never overwrite user media, corrections, other branches or ambiguous prior work.
- Keep private media, transcripts, thumbnails, search/taste history, prompts, analysis,
  paths, databases, models and credentials out of Git. No external metadata lookup,
  telemetry or remote model calls with private data without explicit egress authorization.
- Handoff in `docs/current.md`: observable result, exact evidence, unresolved issue,
  next action. Keep history in Git, not accumulating TASK/REVIEW/status ledgers.
- Every three product slices or coding-model change, reassess harness overhead using
  defects found, rework and time/tokens where available. Remove ineffective optional
  scaffolding; preserve product safety and owner decisions.

## Long Work runs

- Once milestone implementation is authorized, continue across small slices:
  select → implement → run/inspect → repair → checkpoint → next eligible slice.
  A test pass, commit or single finished slice is not an automatic stopping point.
- Keep one implementation owner and one coherent milestone branch. Commit useful
  checkpoints and push/update Draft PRs at reviewable boundaries; label WIP honestly.
- Independent evaluation addresses concrete risk, not every checkpoint. Reuse unchanged
  evidence. A blocked dependency need not stop other authorized work; repeated failure
  without new evidence calls for a saved reproducer and focused second opinion.
- Preserve all owner-only decisions. Before interruption, update docs/current.md with
  branch/revision, actual evidence, incomplete work, blocker and next action. Resume from
  live Git/PR state without overwriting newer work or repeating unchanged investigation.
- Runtime/usage limits remain. This repo cannot guarantee unlimited execution or wake
  itself. Recurring reruns need a separately configured native task, the same authority,
  and one writer; do not use perpetual shell loops to evade platform limits.
