"""P0 Freeze Verification Tests.

These tests verify that P0 judgment logic has not changed.
If any of these tests fail, it means P0 logic has been modified
and requires review per P0_FREEZE_POLICY.md.

Snapshot tests for:
1. PreflightChecker.check() - preflight validation outputs
2. ActionJudge.judge() - action judgment outputs
3. StallDetector.calculate() - stall score calculation

Note: PreflightResult.give_up is both a field and classmethod, causing
name collision in dataclass. Tests check behavior via guidance_cards content.

Note: These tests require duo-talk-gm to be available (sibling repo).
They are skipped in CI environments where the repo is not present.
"""

import sys
from pathlib import Path

import pytest

# Add duo-talk-gm to path
GM_ROOT = Path(__file__).parent.parent.parent / "duo-talk-gm"
sys.path.insert(0, str(GM_ROOT / "src"))

# Check if duo_talk_gm is available (for CI skip)
try:
    from duo_talk_gm.core.action_judge import ActionJudge
    from duo_talk_gm.core.preflight import PreflightChecker
    from duo_talk_gm.core.stall_detector import StallDetector
    from duo_talk_gm.models.enums import DeniedReason, IntentType
    from duo_talk_gm.models.gm_response import ActionIntent, ParsedOutput
    from duo_talk_gm.models.world_state import WorldState

    GM_AVAILABLE = True
except ImportError:
    GM_AVAILABLE = False
    ActionJudge = None
    PreflightChecker = None
    StallDetector = None
    DeniedReason = None
    IntentType = None
    ActionIntent = None
    ParsedOutput = None
    WorldState = None

# Skip all tests in this module if duo_talk_gm is not available
pytestmark = pytest.mark.skipif(
    not GM_AVAILABLE,
    reason="duo-talk-gm not available (CI environment)"
)


def is_give_up_result(result) -> bool:
    """Check if result is a give_up result via guidance_cards content.

    Due to field/method name collision in PreflightResult, we check
    the actual behavior instead of the field directly.
    """
    return any("[GIVE_UP]" in card for card in result.guidance_cards)


class TestPreflightFreezeSnapshots:
    """Snapshot tests for PreflightChecker.check() outputs."""

    @pytest.fixture
    def kitchen_world(self):
        """Standard kitchen world state for testing."""
        return WorldState.create_kitchen_morning()

    @pytest.fixture
    def reset_preflight(self):
        """Reset preflight state before each test."""
        PreflightChecker._retry_attempts.clear()
        yield
        PreflightChecker._retry_attempts.clear()

    def test_snapshot_no_action_intents(self, kitchen_world, reset_preflight):
        """Snapshot: Empty action intents → OK."""
        parsed = ParsedOutput(
            thought="朝だなぁ",
            speech="おはよう",
            action_intents=[],
        )
        result = PreflightChecker.check(
            parsed=parsed,
            world_state=kitchen_world,
            speaker="やな",
            session_id="test_freeze",
            turn_number=0,
        )

        # Snapshot: should pass with no issues
        assert result.has_issues is False
        assert result.suggest_retry is False
        assert not is_give_up_result(result)
        assert result.guidance_cards == []

    def test_snapshot_valid_object_use(self, kitchen_world, reset_preflight):
        """Snapshot: USE coffee maker (exists at location) → OK."""
        parsed = ParsedOutput(
            thought="コーヒーを淹れよう",
            speech="*コーヒーメーカーを使う*",
            action_intents=[
                ActionIntent(intent=IntentType.USE, target="コーヒーメーカー")
            ],
        )
        result = PreflightChecker.check(
            parsed=parsed,
            world_state=kitchen_world,
            speaker="やな",
            session_id="test_freeze",
            turn_number=0,
        )

        # Snapshot: should pass (object exists at location)
        assert result.has_issues is False
        assert result.suggest_retry is False

    def test_snapshot_missing_object_first_retry(self, kitchen_world, reset_preflight):
        """Snapshot: USE yogurt (doesn't exist) → retry with guidance."""
        parsed = ParsedOutput(
            thought="ヨーグルトを食べたい",
            speech="*ヨーグルトを取る*",
            action_intents=[
                ActionIntent(intent=IntentType.GET, target="ヨーグルト")
            ],
        )
        result = PreflightChecker.check(
            parsed=parsed,
            world_state=kitchen_world,
            speaker="やな",
            session_id="test_freeze",
            turn_number=0,
        )

        # Snapshot: should suggest retry (first attempt)
        assert result.has_issues is True
        assert result.suggest_retry is True
        assert not is_give_up_result(result)
        assert result.retry_level == 1
        assert len(result.guidance_cards) > 0
        assert result.findings[0].reason == DeniedReason.MISSING_OBJECT

    def test_snapshot_missing_object_give_up_after_budget(self, kitchen_world, reset_preflight):
        """Snapshot: MISSING_OBJECT × 3 times → give_up."""
        parsed = ParsedOutput(
            thought="ヨーグルトを食べたい",
            speech="*ヨーグルトを取る*",
            action_intents=[
                ActionIntent(intent=IntentType.GET, target="ヨーグルト")
            ],
        )

        # Attempt 1
        result1 = PreflightChecker.check(
            parsed=parsed,
            world_state=kitchen_world,
            speaker="やな",
            session_id="test_freeze",
            turn_number=0,
        )
        assert result1.retry_level == 1

        # Attempt 2
        result2 = PreflightChecker.check(
            parsed=parsed,
            world_state=kitchen_world,
            speaker="やな",
            session_id="test_freeze",
            turn_number=0,
        )
        assert result2.retry_level == 2

        # Attempt 3 → give_up
        result3 = PreflightChecker.check(
            parsed=parsed,
            world_state=kitchen_world,
            speaker="やな",
            session_id="test_freeze",
            turn_number=0,
        )

        # Snapshot: should give up after budget exhausted
        assert result3.has_issues is True
        assert result3.suggest_retry is False
        assert is_give_up_result(result3)

    def test_snapshot_invalid_move(self, kitchen_world, reset_preflight):
        """Snapshot: MOVE to non-existent location → retry with guidance."""
        parsed = ParsedOutput(
            thought="外に行こう",
            speech="*外に出る*",
            action_intents=[
                ActionIntent(intent=IntentType.MOVE, target="外")
            ],
        )
        result = PreflightChecker.check(
            parsed=parsed,
            world_state=kitchen_world,
            speaker="やな",
            session_id="test_freeze",
            turn_number=0,
        )

        # Snapshot: should suggest retry for OUT_OF_SCOPE
        assert result.has_issues is True
        assert result.suggest_retry is True
        assert result.findings[0].reason == DeniedReason.OUT_OF_SCOPE


class TestActionJudgeFreezeSnapshots:
    """Snapshot tests for ActionJudge.judge() outputs."""

    @pytest.fixture
    def kitchen_world(self):
        """Standard kitchen world state for testing."""
        return WorldState.create_kitchen_morning()

    def test_snapshot_empty_intents(self, kitchen_world):
        """Snapshot: Empty intents → allowed."""
        parsed = ParsedOutput(
            thought="何もしない",
            speech="うーん",
            action_intents=[],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: P0 Safety - empty intents always allowed
        assert result.is_allowed is True
        assert result.denied_reason is None

    def test_snapshot_speech_only(self, kitchen_world):
        """Snapshot: SAY intent → allowed (speech-only)."""
        parsed = ParsedOutput(
            thought="挨拶しよう",
            speech="おはよう",
            action_intents=[
                ActionIntent(intent=IntentType.SAY, target=None)
            ],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: Speech-only always allowed
        assert result.is_allowed is True
        assert result.denied_reason is None

    def test_snapshot_valid_get(self, kitchen_world):
        """Snapshot: GET mug (exists at location) → allowed."""
        parsed = ParsedOutput(
            thought="マグカップを取ろう",
            speech="*マグカップを取る*",
            action_intents=[
                ActionIntent(intent=IntentType.GET, target="マグカップ")
            ],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: valid GET allowed
        assert result.is_allowed is True
        assert result.denied_reason is None
        assert result.resolution_method == "exact"

    def test_snapshot_missing_object_denied(self, kitchen_world):
        """Snapshot: GET yogurt (doesn't exist) → denied MISSING_OBJECT."""
        parsed = ParsedOutput(
            thought="ヨーグルトを取りたい",
            speech="*ヨーグルトを取る*",
            action_intents=[
                ActionIntent(intent=IntentType.GET, target="ヨーグルト")
            ],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: MISSING_OBJECT denied
        assert result.is_allowed is False
        assert result.denied_reason == DeniedReason.MISSING_OBJECT
        assert result.resolution_method == "none"

    def test_snapshot_wrong_location_denied(self, kitchen_world):
        """Snapshot: GET TV (in living room, not kitchen) → denied WRONG_LOCATION."""
        parsed = ParsedOutput(
            thought="テレビを取ろう",
            speech="*テレビを取る*",
            action_intents=[
                ActionIntent(intent=IntentType.GET, target="テレビ")
            ],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: WRONG_LOCATION denied (TV is in living room)
        assert result.is_allowed is False
        assert result.denied_reason == DeniedReason.WRONG_LOCATION

    def test_snapshot_derived_prop_allowed(self, kitchen_world):
        """Snapshot: EAT_DRINK coffee (alias for coffee maker) → allowed with soft correction.

        Note: コーヒー is an alias for コーヒーメーカー in default world state,
        so resolution_method is "alias" not "derived".
        """
        parsed = ParsedOutput(
            thought="コーヒーを飲もう",
            speech="*コーヒーを飲む*",
            action_intents=[
                ActionIntent(intent=IntentType.EAT_DRINK, target="コーヒー")
            ],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: GM-013 soft resolution - alias props allowed
        # コーヒー is aliased to コーヒーメーカー in prop_aliases
        assert result.is_allowed is True
        assert result.resolution_method == "alias"
        assert result.resolved_target == "コーヒーメーカー"
        assert result.soft_correction is not None

    def test_snapshot_valid_move(self, kitchen_world):
        """Snapshot: MOVE to living room (valid exit) → allowed."""
        parsed = ParsedOutput(
            thought="リビングに行こう",
            speech="*リビングに移動する*",
            action_intents=[
                ActionIntent(intent=IntentType.MOVE, target="リビング")
            ],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: valid MOVE allowed
        assert result.is_allowed is True
        assert result.denied_reason is None

    def test_snapshot_out_of_scope_move(self, kitchen_world):
        """Snapshot: MOVE to non-existent location → denied OUT_OF_SCOPE."""
        parsed = ParsedOutput(
            thought="外に行こう",
            speech="*外に出る*",
            action_intents=[
                ActionIntent(intent=IntentType.MOVE, target="外")
            ],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: OUT_OF_SCOPE denied
        assert result.is_allowed is False
        assert result.denied_reason == DeniedReason.OUT_OF_SCOPE

    def test_snapshot_not_owned_put(self, kitchen_world):
        """Snapshot: PUT item not holding → denied NOT_OWNED."""
        parsed = ParsedOutput(
            thought="マグカップを置こう",
            speech="*マグカップを置く*",
            action_intents=[
                ActionIntent(intent=IntentType.PUT, target="マグカップ")
            ],
        )
        result = ActionJudge.judge(parsed, kitchen_world, "やな")

        # Snapshot: NOT_OWNED denied (やな is not holding マグカップ)
        assert result.is_allowed is False
        assert result.denied_reason == DeniedReason.NOT_OWNED


class TestStallDetectorFreezeSnapshots:
    """Snapshot tests for StallDetector.calculate() outputs."""

    def test_snapshot_empty_history(self):
        """Snapshot: No history → score 0.0."""
        score = StallDetector.calculate(
            history=[],
            current_delta=[],
            current_speech=None,
        )

        # Snapshot: empty → 0.0
        assert score == 0.0

    def test_snapshot_active_conversation(self):
        """Snapshot: Varied conversation → low score."""
        history = [
            {"speech": "おはよう", "world_delta": []},
            {"speech": "今日の天気はいいね", "world_delta": []},
            {"speech": "コーヒーを淹れようか", "world_delta": [{"op": "replace"}]},
        ]
        score = StallDetector.calculate(
            history=history,
            current_delta=[],
            current_speech="朝ごはんは何がいい？",
        )

        # Snapshot: active conversation → low score (< 0.3)
        assert score < 0.3

    def test_snapshot_exact_repetition(self):
        """Snapshot: Exact speech repetition → high score."""
        history = [
            {"speech": "うーん", "world_delta": []},
            {"speech": "うーん", "world_delta": []},
            {"speech": "うーん", "world_delta": []},
        ]
        score = StallDetector.calculate(
            history=history,
            current_delta=[],
            current_speech="うーん",
        )

        # Snapshot: exact repetition → high score (≥ 0.7)
        # Weight: speech_repeat=0.70, and exact match = 1.0
        assert score >= 0.7

    def test_snapshot_short_responses(self):
        """Snapshot: Very short responses contribute to stall."""
        history = [
            {"speech": "うん", "world_delta": []},
            {"speech": "そう", "world_delta": []},
            {"speech": "ねー", "world_delta": []},
        ]
        score = StallDetector.calculate(
            history=history,
            current_delta=[],
            current_speech="はい",
        )

        # Snapshot: short responses → some contribution
        # short_response weight=0.10, no_delta weight=0.20
        # All 4 responses are short (< 20 chars) → short_score = 1.0
        # All deltas are empty → delta_score = 1.0
        # Expected: 0.10 * 1.0 + 0.20 * 1.0 = 0.30
        assert 0.2 <= score <= 0.4

    def test_snapshot_no_world_delta(self):
        """Snapshot: No world delta for many turns → contribution to stall."""
        history = [
            {"speech": "今日もいい天気だね", "world_delta": []},
            {"speech": "そうだね、気持ちいいね", "world_delta": []},
            {"speech": "何しようか", "world_delta": []},
            {"speech": "散歩でもしようか", "world_delta": []},
        ]
        score = StallDetector.calculate(
            history=history,
            current_delta=[],
            current_speech="いいね、行こう",
        )

        # Snapshot: no world delta → contribution from no_delta weight (0.20)
        # Should contribute but not dominate
        assert 0.1 <= score <= 0.4

    def test_snapshot_gm_injected_excluded(self):
        """Snapshot: GM-injected turns excluded from repetition detection.

        Even with gm_injected exclusion, "おはよう" still matches the first
        non-injected turn, so high repetition score is expected.
        """
        history = [
            {"speech": "おはよう", "world_delta": [], "gm_injected": False},
            {"speech": "おはよう", "world_delta": [], "gm_injected": True},  # Excluded
            {"speech": "今日もいい天気だね", "world_delta": [], "gm_injected": False},
        ]
        score = StallDetector.calculate(
            history=history,
            current_delta=[],
            current_speech="おはよう",
        )

        # Snapshot: gm_injected turns excluded, but current speech still
        # exactly matches first non-injected turn → high repetition score
        # speech_repeat weight=0.70, exact match=1.0 → 0.70+
        assert score >= 0.7

    def test_snapshot_severity_levels(self):
        """Snapshot: Severity level thresholds."""
        # Active
        assert StallDetector.get_severity(0.0) == "active"
        assert StallDetector.get_severity(0.29) == "active"

        # Warning
        assert StallDetector.get_severity(0.3) == "warning"
        assert StallDetector.get_severity(0.79) == "warning"

        # Stalled
        assert StallDetector.get_severity(0.8) == "stalled"
        assert StallDetector.get_severity(0.89) == "stalled"

        # Critical
        assert StallDetector.get_severity(0.9) == "critical"
        assert StallDetector.get_severity(1.0) == "critical"

    def test_snapshot_cooldown_trigger(self):
        """Snapshot: Cooldown prevents repeated triggers."""
        # Should trigger (score >= 0.8, turns_since >= 5)
        assert StallDetector.should_trigger(0.8, 5) is True
        assert StallDetector.should_trigger(0.9, 10) is True

        # Should not trigger (score < 0.8)
        assert StallDetector.should_trigger(0.7, 5) is False

        # Should not trigger (cooldown not met)
        assert StallDetector.should_trigger(0.8, 4) is False
        assert StallDetector.should_trigger(0.9, 0) is False


class TestFreezeConstants:
    """Verify P0 frozen constants haven't changed."""

    def test_stall_weights_frozen(self):
        """Snapshot: Stall detector weights are frozen."""
        from duo_talk_gm.core.stall_detector import WEIGHTS

        # GM-014 frozen weights
        assert WEIGHTS["speech_repeat"] == 0.70
        assert WEIGHTS["no_world_delta_run"] == 0.20
        assert WEIGHTS["short_response"] == 0.10

    def test_stall_thresholds_frozen(self):
        """Snapshot: Stall detector thresholds are frozen."""
        from duo_talk_gm.core.stall_detector import (
            THRESHOLD_WARNING,
            THRESHOLD_STALLED,
            THRESHOLD_CRITICAL,
            STALL_COOLDOWN_TURNS,
        )

        # GM-014 frozen thresholds
        assert THRESHOLD_WARNING == 0.3
        assert THRESHOLD_STALLED == 0.8
        assert THRESHOLD_CRITICAL == 0.9
        assert STALL_COOLDOWN_TURNS == 5

    def test_preflight_budget_frozen(self):
        """Snapshot: Preflight retry budget is frozen at 2."""
        # The budget is hardcoded in PreflightChecker.check()
        # This test verifies behavior indirectly
        PreflightChecker._retry_attempts.clear()

        kitchen_world = WorldState.create_kitchen_morning()
        parsed = ParsedOutput(
            thought="test",
            speech="*ヨーグルトを取る*",
            action_intents=[ActionIntent(intent=IntentType.GET, target="ヨーグルト")],
        )

        # Attempt 1, 2 → retry
        for _ in range(2):
            result = PreflightChecker.check(
                parsed, kitchen_world, "やな", "budget_test", 0
            )
            assert result.suggest_retry is True
            assert not is_give_up_result(result)

        # Attempt 3 → give_up
        result = PreflightChecker.check(
            parsed, kitchen_world, "やな", "budget_test", 0
        )
        assert is_give_up_result(result)

        PreflightChecker._retry_attempts.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
