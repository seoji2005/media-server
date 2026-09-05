"""Pure dry-run policy probe, NOT a GitHub receiver or evidence verifier.

All facts are supplied by a caller. Fixture provenance/ownership values do not prove
real run identity or cross-cloud serialization. Every decision forbids remote writes.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Target:
    repository: str
    pr: int
    base: str
    head: str


@dataclass(frozen=True)
class Source:
    automation: str
    conversation: str
    run: str
    comment: str  # Observed GitHub comment ID, not a self-asserted body field.
    kind: str = "event"


@dataclass(frozen=True)
class Request:
    target: Target
    state: str = "WIP"
    attempt: int = 1
    retry_reason: str = ""
    reviewer_automation: str = ""
    reviewer_conversation: str = ""


@dataclass(frozen=True)
class Result:
    target: Target
    attempt: int
    verdict: str
    source: Source | None = None
    finding_severities: tuple[str, ...] = ()


@dataclass(frozen=True)
class Facts:
    live: Target
    pr_open: bool = True
    # From existing owner instructions, never PR/comment assertions.
    scope_authorized: bool = False
    next_task_authorized: bool = False
    ownership: str = "unknown"  # "held" only with shared execution evidence.
    evidence_sufficient: bool = False  # Acceptance evidence and limits were inspected.
    checkpoint_recovered: bool = False  # Known initial state or restored handled results.
    # Exact source independently matched to a platform run and its posted comment.
    verified_source: Source | None = None
    processed: tuple[tuple[Target, int], ...] = ()


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    dry_run: bool = True
    remote_write_allowed: bool = False


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def decide(request: Request, result: Result, facts: Facts) -> Decision:
    """Select one hypothetical action; never persist, dispatch, or consume a result."""
    target = request.target
    # Python makes bool/float equal to int; validate before target/duplicate shortcuts.
    if not all(_positive_int(value) for value in (
        target.pr, result.target.pr, facts.live.pr, request.attempt, result.attempt,
    )) or any(not _positive_int(t.pr) or not _positive_int(attempt)
              for t, attempt in facts.processed):
        return Decision("BLOCKED_ENV", "PR and attempt must be positive builtin integers")
    if target.repository != "seoji2005/media-server" or target.pr != 1:
        return Decision("IGNORE", "outside configured PR #1")
    if not facts.pr_open or request.state == "WIP":
        return Decision("IGNORE", "closed PR or unrequested WIP")
    if request.state != "ready" or not all(
        re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (target.base, target.head)
    ):
        return Decision("BLOCKED_ENV", "invalid review request")
    if target != facts.live or result.target != target:
        return Decision("IGNORE", "stale or unrelated base/head")
    if result.attempt != request.attempt:
        return Decision("IGNORE", "superseded or unrequested attempt")
    if any(t == target and attempt >= result.attempt for t, attempt in facts.processed):
        return Decision("IGNORE", "already processed or out of order")
    if request.attempt > 1 and not request.retry_reason.strip():
        return Decision("BLOCKED_ENV", "same-code retry needs an explicit reason")
    if result.verdict == "STALE":
        return Decision("IGNORE", "reviewer reported stale target")
    source = result.source
    if source and source.kind == "manual":
        return Decision("IGNORE", "manual report is not an event result")
    if not source or not all((source.automation, source.conversation, source.run,
                              source.comment)) or (
        source.kind != "event"
        or
        source.automation != request.reviewer_automation
        or source.conversation != request.reviewer_conversation
        or source != facts.verified_source
    ):
        return Decision("BLOCKED_ENV", "review source lacks matching platform evidence")
    if result.verdict not in {"PASS", "CHANGES_REQUESTED", "BLOCKED_ENV"} or any(
        severity not in {"BLOCKER", "IMPORTANT", "NIT", "FOLLOW-UP"}
        for severity in result.finding_severities
    ):
        return Decision("BLOCKED_ENV", "invalid result verdict or finding severity")
    if result.verdict == "BLOCKED_ENV":
        return Decision("INVESTIGATE_ENV", "resolve environment without product edits")
    if not facts.checkpoint_recovered:
        return Decision("BLOCKED_ENV", "handled-result checkpoint is unavailable")
    if facts.ownership == "active":
        return Decision("DEFER", "another execution owns implementation")
    if facts.ownership != "held":
        return Decision("BLOCKED_ENV", "shared execution ownership is unverified")
    if not facts.scope_authorized:
        return Decision("WAIT_OWNER", "no existing authorization for this scope")
    if result.verdict == "CHANGES_REQUESTED" or any(
        severity in {"BLOCKER", "IMPORTANT"} for severity in result.finding_severities
    ):
        return Decision("FIX", "repair findings and rerun affected checks")
    if not facts.evidence_sufficient:
        return Decision("BLOCKED_ENV", "PASS lacks sufficient acceptance evidence")
    if facts.next_task_authorized:
        return Decision("CONTINUE", "checkpoint and select next authorized task")
    return Decision("MILESTONE_COMPLETE", "no next authorized task; owner controls merge")
