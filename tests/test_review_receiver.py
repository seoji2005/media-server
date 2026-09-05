"""Synthetic action selection only; no live event, provenance, or locking claims."""
from dataclasses import replace
import unittest

from scripts.review_receiver import Facts, Request, Result, Source, Target, decide


class ReceiverPolicyTests(unittest.TestCase):
    def setUp(self):
        self.target = Target("seoji2005/media-server", 1, "a" * 40, "b" * 40)
        self.source = Source("reviewer-task", "independent-work", "run-1", "comment-1")
        self.request = Request(self.target, "ready", reviewer_automation="reviewer-task",
                               reviewer_conversation="independent-work")
        self.result = Result(self.target, 1, "PASS", self.source)
        self.facts = Facts(self.target, scope_authorized=True, ownership="held",
                           verified_source=self.source, evidence_sufficient=True,
                           checkpoint_recovered=True)

    def action(self, expected, request=None, result=None, facts=None):
        decision = decide(request or self.request, result or self.result, facts or self.facts)
        self.assertEqual(expected, decision.action, decision.reason)
        self.assertTrue(decision.dry_run)
        self.assertFalse(decision.remote_write_allowed)

    def test_pass_stops_at_harness_milestone_without_app_authority(self):
        self.action("MILESTONE_COMPLETE")
        self.action("CONTINUE", facts=replace(self.facts, next_task_authorized=True))

    def test_changes_and_important_findings_never_advance(self):
        self.action("FIX", result=replace(self.result, verdict="CHANGES_REQUESTED"))
        for severity in ("BLOCKER", "IMPORTANT"):
            with self.subTest(severity=severity):
                self.action("FIX", result=replace(self.result, finding_severities=(severity,)),
                            facts=replace(self.facts, next_task_authorized=True))
        self.action("MILESTONE_COMPLETE",
                    result=replace(self.result, finding_severities=("NIT", "FOLLOW-UP")))

    def test_environment_failure_does_not_request_code_edits(self):
        self.action("INVESTIGATE_ENV", result=replace(self.result, verdict="BLOCKED_ENV"),
                    facts=replace(self.facts, ownership="unknown"))

    def test_wip_closed_and_other_pr_are_ignored(self):
        self.action("IGNORE", request=replace(self.request, state="WIP"))
        self.action("IGNORE", facts=replace(self.facts, pr_open=False))
        self.action("IGNORE", request=replace(self.request, target=replace(self.target, pr=2)))

    def test_ready_before_push_and_base_drift_are_stale(self):
        for live in (replace(self.target, head="c" * 40), replace(self.target, base="c" * 40)):
            with self.subTest(live=live):
                self.action("IGNORE", facts=replace(self.facts, live=live))
        self.action("IGNORE", result=replace(self.result, target=replace(self.target, head="c" * 40)))
        self.action("IGNORE", result=replace(self.result, verdict="STALE"))

    def test_duplicate_new_run_id_does_not_create_new_target(self):
        source = replace(self.source, run="run-2", comment="comment-2")
        self.action("IGNORE", result=replace(self.result, source=source),
                    facts=replace(self.facts, verified_source=source,
                                  processed=((self.target, 1),)))

    def test_same_code_retry_requires_reason_and_new_attempt(self):
        request = replace(self.request, attempt=2)
        result = replace(self.result, attempt=2)
        facts = replace(self.facts, processed=((self.target, 1),))
        self.action("BLOCKED_ENV", request=request, result=result, facts=facts)
        request = replace(request, retry_reason="environment access restored")
        self.action("MILESTONE_COMPLETE", request=request, result=result, facts=facts)
        self.action("IGNORE", request=request, result=self.result, facts=facts)
        self.action("IGNORE", request=request, result=result,
                    facts=replace(facts, processed=((self.target, 3),)))

    def test_source_claims_alone_and_wrong_bindings_are_not_evidence(self):
        self.action("IGNORE", result=replace(self.result,
                                              source=replace(self.source, kind="manual")))
        self.action("BLOCKED_ENV", facts=replace(self.facts, verified_source=None))
        self.action("BLOCKED_ENV", result=replace(self.result, source=None))
        for field in ("automation", "conversation", "run", "comment"):
            with self.subTest(field=field):
                self.action("BLOCKED_ENV", result=replace(
                    self.result, source=replace(self.source, **{field: "different"})))
        source = replace(self.source, automation="self-report")
        self.action("BLOCKED_ENV", result=replace(self.result, source=source),
                    facts=replace(self.facts, verified_source=source))

    def test_overlapping_and_unknown_ownership_cannot_advance(self):
        self.action("DEFER", facts=replace(self.facts, ownership="active"))
        self.action("BLOCKED_ENV", facts=replace(self.facts, ownership="unknown"))

    def test_missing_owner_authorization_cannot_advance(self):
        self.action("WAIT_OWNER", facts=replace(self.facts, scope_authorized=False,
                                               next_task_authorized=True))

    def test_pass_requires_sufficient_acceptance_evidence(self):
        self.action("BLOCKED_ENV", facts=replace(self.facts, evidence_sufficient=False,
                                                next_task_authorized=True))

    def test_restart_reuses_supplied_checkpoint_without_mutating_it(self):
        facts = replace(self.facts, processed=((self.target, 1),))
        first = decide(self.request, self.result, facts)
        self.assertEqual(first, decide(self.request, self.result, facts))
        self.assertEqual(((self.target, 1),), facts.processed)
        self.action("IGNORE", facts=facts)
        # Losing state is NOT solved by the pure helper; restored run evidence is required.
        self.action("BLOCKED_ENV", facts=Facts(self.target))
        self.action("BLOCKED_ENV", facts=replace(self.facts, checkpoint_recovered=False))

    def test_malformed_requests_and_results_fail_closed(self):
        self.action("BLOCKED_ENV", request=replace(self.request, state="maybe"))
        self.action("BLOCKED_ENV", request=replace(self.request, attempt=0),
                    result=replace(self.result, attempt=0))
        self.action("BLOCKED_ENV", request=replace(self.request,
                                                   target=replace(self.target, head="short")))
        self.action("BLOCKED_ENV", result=replace(self.result, verdict="looks PASS"))
        self.action("BLOCKED_ENV", result=replace(self.result, finding_severities=("major",)))

    def test_request_result_and_live_pr_require_positive_builtin_integers(self):
        for value in (True, False, 1.0, 0.0, -1.0, 0, -1, "1", None):
            target = replace(self.target, pr=value)
            for field in ("request", "result", "live"):
                with self.subTest(field=field, value=value, type=type(value).__name__):
                    self.action(
                        "BLOCKED_ENV",
                        request=replace(self.request, target=target) if field == "request" else None,
                        result=replace(self.result, target=target) if field == "result" else None,
                        facts=replace(self.facts, live=target) if field == "live" else None,
                    )

    def test_attempts_require_positive_builtin_integers_before_comparison(self):
        for value in (True, False, 1.0, 0.0, -1.0, 0, -1, "1", None):
            for field in ("request", "result", "both"):
                with self.subTest(field=field, value=value, type=type(value).__name__):
                    self.action(
                        "BLOCKED_ENV",
                        request=replace(self.request, attempt=value) if field != "result" else None,
                        result=replace(self.result, attempt=value) if field != "request" else None,
                    )

    def test_invalid_numbers_cannot_hide_behind_stale_or_duplicate_shortcuts(self):
        for value in (True, 1.0, 0, -1):
            for facts in (replace(self.facts, live=replace(self.target, head="c" * 40)),
                          replace(self.facts, processed=((self.target, 1),))):
                with self.subTest(value=value, type=type(value).__name__, facts=facts):
                    self.action("BLOCKED_ENV", result=replace(self.result, attempt=value),
                                facts=facts)
                    self.action("BLOCKED_ENV", request=replace(self.request, attempt=value),
                                facts=facts)
                    self.action("BLOCKED_ENV", result=replace(
                        self.result, target=replace(self.target, pr=value)), facts=facts)

    def test_processed_checkpoint_numbers_are_validated_before_duplicate_scan(self):
        for value in (True, False, 1.0, 0.0, -1.0, 0, -1, "1", None):
            for record in ((replace(self.target, pr=value), 1), (self.target, value)):
                # A valid duplicate first must not conceal a malformed later entry.
                for processed in ((record,), ((self.target, 1), record)):
                    with self.subTest(record=record, processed=processed):
                        self.action("BLOCKED_ENV", facts=replace(self.facts, processed=processed))

    def test_int_subclasses_are_not_builtin_numeric_identity(self):
        class IntSubclass(int):
            pass

        value = IntSubclass(1)
        self.action("BLOCKED_ENV", result=replace(self.result, attempt=value))
        self.action("BLOCKED_ENV", facts=replace(self.facts, live=replace(self.target, pr=value)))
        self.action("BLOCKED_ENV", facts=replace(self.facts, processed=((self.target, value),)))

    def test_valid_integer_mismatches_and_unrelated_checkpoint_stay_ignored(self):
        for target in (replace(self.target, pr=2), replace(self.target, head="c" * 40)):
            with self.subTest(target=target):
                self.action("IGNORE", result=replace(self.result, target=target))
                self.action("IGNORE", facts=replace(self.facts, live=target))
                self.action("MILESTONE_COMPLETE",
                            facts=replace(self.facts, processed=((target, 3),)))
        self.action("IGNORE", result=replace(self.result, attempt=2))


if __name__ == "__main__":
    unittest.main()
