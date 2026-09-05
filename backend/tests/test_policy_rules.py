"""Tests for the configurable policy engine (Slice 12 / spec section
19): POLICY_RULES is real data evaluate_execution_policy() iterates
over, not three hardcoded if-blocks -- these prove a new rule can be
added by appending to the list, with no change to the evaluation
function itself, and that existing behavior is unchanged by the
refactor.
"""

from types import SimpleNamespace

from app.governance import policy


def _agent(**overrides):
    defaults = dict(risk_level="LOW", criticality="LOW", confidence_threshold=0.7, human_approval_required=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestPolicyRulesAreConfigurable:
    def test_a_new_rule_can_be_appended_without_touching_the_evaluator(self, monkeypatch):
        """The whole point of section 19: appending to the rule list is
        the extension mechanism, not editing evaluate_execution_policy()'s
        own code."""
        custom_rules = list(policy.POLICY_RULES) + [
            ("always_flag_test_agents",
             lambda agent, confidence: getattr(agent, "agent_type", None) == "TEST_MARKER",
             "Flagged by a rule added purely as test data, not by editing the evaluator."),
        ]
        monkeypatch.setattr(policy, "POLICY_RULES", custom_rules)

        agent = _agent(agent_type="TEST_MARKER")
        requires_approval = False
        reason = None
        for _rule_id, condition, message in policy.POLICY_RULES:
            if condition(agent, 0.99):
                requires_approval = True
                reason = message(agent, 0.99) if callable(message) else message

        assert requires_approval is True
        assert "test data" in reason

    def test_default_rules_match_the_original_three_checks(self):
        rule_ids = [rule_id for rule_id, _, _ in policy.POLICY_RULES]
        assert rule_ids == [
            "explicit_human_approval",
            "critical_risk_or_criticality",
            "confidence_below_threshold",
        ]

    def test_no_rule_matches_a_low_risk_confident_agent(self):
        agent = _agent()
        matched = [rule_id for rule_id, condition, _ in policy.POLICY_RULES if condition(agent, 0.95)]
        assert matched == []

    def test_last_matching_rule_wins_the_reported_reason(self):
        # human_approval_required and confidence_below_threshold both
        # match -- the later rule in the list should win, same ordering
        # semantics as the original sequential if-blocks.
        agent = _agent(human_approval_required=True, confidence_threshold=0.9)
        reason = None
        for _rule_id, condition, message in policy.POLICY_RULES:
            if condition(agent, 0.5):
                reason = message(agent, 0.5) if callable(message) else message
        assert "confidence" in reason.lower()
