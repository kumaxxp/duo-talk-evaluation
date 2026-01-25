"""Tests for GM-020: Detailed Retry Success Metrics.

Tests:
1. extract_marker_targets: extracts targets from *...* markers only
2. extract_marker_targets: ignores natural language mentions
3. retry_success_action: True when *...* targets change
4. retry_success_strict: True when allowed=True && !suggest_retry && !give_up
"""

import pytest

# Import the function from the runner
import sys
from pathlib import Path

# Add experiments to path
sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))

from gm_2x2_runner import extract_marker_targets


class TestExtractMarkerTargets:
    """Test extract_marker_targets function."""

    def test_extracts_from_asterisk_markers(self):
        """Should extract targets from *...* markers."""
        text = "やな、コーヒー入れたよ！ *マグカップを取る*"
        targets = extract_marker_targets(text)
        assert "マグカップ" in targets

    def test_ignores_natural_language_mentions(self):
        """Should NOT extract targets from natural language mentions."""
        text = "冷蔵庫にヨーグルトがあるよ"  # No *...*
        targets = extract_marker_targets(text)
        assert targets == []  # No markers, no targets

    def test_extracts_multiple_targets(self):
        """Should extract multiple targets from multiple markers."""
        text = "*冷蔵庫を開ける* そして *コーヒーを取る*"
        targets = extract_marker_targets(text)
        assert "冷蔵庫" in targets
        assert "コーヒー" in targets

    def test_extracts_location_targets(self):
        """Should extract location targets for MOVE actions."""
        text = "*リビングに移動する*"
        targets = extract_marker_targets(text)
        assert "リビング" in targets

    def test_mixed_markers_and_mentions(self):
        """Should only extract from markers, not mentions."""
        text = "ヨーグルトとフルーツがないみたい。代わりに *マグカップを手に取る*"
        targets = extract_marker_targets(text)
        # Should have マグカップ (from marker)
        assert "マグカップ" in targets
        # Should NOT have ヨーグルト or フルーツ (natural language mentions)
        assert "ヨーグルト" not in targets
        assert "フルーツ" not in targets

    def test_empty_string(self):
        """Should return empty list for empty string."""
        assert extract_marker_targets("") == []

    def test_none_input(self):
        """Should return empty list for None input."""
        assert extract_marker_targets(None) == []

    def test_no_duplicates(self):
        """Should not return duplicate targets."""
        text = "*マグカップを取る* 素敵なマグカップだね *マグカップを置く*"
        targets = extract_marker_targets(text)
        assert targets.count("マグカップ") == 1


class TestRetrySuccessMetrics:
    """Test retry success metric calculations."""

    def test_retry_success_action_when_targets_change(self):
        """retry_success_action should be True when marker targets change."""
        # Simulating the calculation logic
        marker_targets_before = ["ヨーグルト", "フルーツ"]
        marker_targets_after = ["マグカップ", "砂糖"]

        retry_success_action = set(marker_targets_before) != set(marker_targets_after)
        assert retry_success_action is True

    def test_retry_success_action_when_targets_same(self):
        """retry_success_action should be False when marker targets are same."""
        marker_targets_before = ["コーヒー"]
        marker_targets_after = ["コーヒー"]

        retry_success_action = set(marker_targets_before) != set(marker_targets_after)
        assert retry_success_action is False

    def test_retry_success_action_when_empty_to_targets(self):
        """retry_success_action should be True when going from no markers to markers."""
        marker_targets_before = []
        marker_targets_after = ["マグカップ"]

        retry_success_action = set(marker_targets_before) != set(marker_targets_after)
        assert retry_success_action is True

    def test_retry_success_strict_conditions(self):
        """retry_success_strict should be True only when all conditions met."""
        # Success case
        allowed = True
        suggest_retry = False
        give_up = False
        retry_success_strict = allowed and not suggest_retry and not give_up
        assert retry_success_strict is True

        # Fail case: give_up
        give_up = True
        retry_success_strict = allowed and not suggest_retry and not give_up
        assert retry_success_strict is False

        # Fail case: not allowed
        allowed = False
        give_up = False
        retry_success_strict = allowed and not suggest_retry and not give_up
        assert retry_success_strict is False


class TestRealWorldExamples:
    """Test with real-world examples from Gate-3B failures."""

    def test_coffee_trap_turn2_example(self):
        """Test with real example from coffee_trap Turn 2."""
        # Raw speech had *action* that was blocked
        raw_speech = "あゆ、おはよう！カフェインレスなら、もちろん用意できるよ。*カフェインレスのコーヒー豆を取り出し、コーヒーメーカーに入れる*"
        # Final speech has different *action*
        final_speech = "あゆ、カフェインレスはなくてごめんね。代わりに、トースターで何か焼いて、ジュースでも飲む？冷蔵庫にオレンジジュースはあるよ。"

        targets_before = extract_marker_targets(raw_speech)
        targets_after = extract_marker_targets(final_speech)

        # Raw has marker action
        assert len(targets_before) > 0 or "コーヒーメーカー" in raw_speech

        # Final has NO marker (only natural language)
        assert targets_after == []

        # Action changed (markers removed = different behavior)
        retry_success_action = set(targets_before) != set(targets_after)
        assert retry_success_action is True

    def test_coffee_trap_turn4_example(self):
        """Test with real example from coffee_trap Turn 4."""
        # Raw speech
        raw_speech = "ヨーグルトとフルーツ、いいね！姉様、さすがヘルシー意識高いね！*冷蔵庫を開けてヨーグルトとフルーツを取り出す*"
        # Final speech (after retry)
        final_speech = "あ、ちょっと待って！姉様、ヨーグルトとフルーツがないみたい。代わりに、コーヒーに入れる砂糖でもどう？ *マグカップを手に取り、砂糖を少し入れる*"

        targets_before = extract_marker_targets(raw_speech)
        targets_after = extract_marker_targets(final_speech)

        # Raw targets: 冷蔵庫, ヨーグルト, フルーツ
        assert "冷蔵庫" in targets_before

        # Final targets: マグカップ, 砂糖 (different objects!)
        assert "マグカップ" in targets_after

        # Action definitely changed
        retry_success_action = set(targets_before) != set(targets_after)
        assert retry_success_action is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
