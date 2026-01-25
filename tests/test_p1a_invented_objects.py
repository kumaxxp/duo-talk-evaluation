"""Tests for P1a: Invented Object Analysis.

Tests:
1. extract_available_from_guidance: extracts OBJECTS_HERE, HOLDING, EXITS from guidance cards
2. check_invented_objects: identifies targets NOT in available lists
3. Partial matching: "冷蔵庫" matches "冷蔵庫の中"
4. normalize_text: handles full-width/half-width, punctuation, etc.
5. check_invented_objects_detailed: returns detailed reasons
"""

import pytest
import sys
from pathlib import Path

# Add experiments to path
sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))

from gm_2x2_runner import (
    extract_available_from_guidance,
    check_invented_objects,
    check_invented_objects_detailed,
    normalize_text,
)


class TestExtractAvailableFromGuidance:
    """Test extract_available_from_guidance function."""

    def test_extracts_objects_here(self):
        """Should extract OBJECTS_HERE from guidance cards."""
        guidance_cards = [
            """<<<SYSTEM_SIGNAL>>>
[ERROR_CODE] MISSING_OBJECT
[BLOCKED_TARGET] ヨーグルト

[ALTERNATIVES]
OBJECTS_HERE: コーヒーメーカー, マグカップ, 砂糖, トースター
HOLDING: (none)
EXITS: リビング
<<<END_SIGNAL>>>"""
        ]
        result = extract_available_from_guidance(guidance_cards)
        assert "コーヒーメーカー" in result["objects_here"]
        assert "マグカップ" in result["objects_here"]
        assert "砂糖" in result["objects_here"]
        assert "トースター" in result["objects_here"]

    def test_extracts_holding(self):
        """Should extract HOLDING items."""
        guidance_cards = [
            """OBJECTS_HERE: (none)
HOLDING: マグカップ, スプーン
EXITS: キッチン"""
        ]
        result = extract_available_from_guidance(guidance_cards)
        assert "マグカップ" in result["holding"]
        assert "スプーン" in result["holding"]

    def test_extracts_exits(self):
        """Should extract EXITS."""
        guidance_cards = [
            """OBJECTS_HERE: コーヒーメーカー
HOLDING: (none)
EXITS: リビング, 庭"""
        ]
        result = extract_available_from_guidance(guidance_cards)
        assert "リビング" in result["exits"]
        assert "庭" in result["exits"]

    def test_handles_available_exits_prefix(self):
        """Should handle AVAILABLE_EXITS prefix."""
        guidance_cards = [
            """OBJECTS_HERE: (none)
HOLDING: (none)
AVAILABLE_EXITS: キッチン, 寝室"""
        ]
        result = extract_available_from_guidance(guidance_cards)
        assert "キッチン" in result["exits"]
        assert "寝室" in result["exits"]

    def test_handles_none_values(self):
        """Should handle (none) values correctly."""
        guidance_cards = [
            """OBJECTS_HERE: (none)
HOLDING: (none)
EXITS: (none)"""
        ]
        result = extract_available_from_guidance(guidance_cards)
        assert result["objects_here"] == []
        assert result["holding"] == []
        assert result["exits"] == []

    def test_handles_plus_more_suffix(self):
        """Should strip (+N more) suffix from items."""
        guidance_cards = [
            """OBJECTS_HERE: コーヒーメーカー, マグカップ (+3 more)
HOLDING: (none)
EXITS: リビング"""
        ]
        result = extract_available_from_guidance(guidance_cards)
        assert "コーヒーメーカー" in result["objects_here"]
        assert "マグカップ" in result["objects_here"]
        # Should not have the (+3 more) part
        for item in result["objects_here"]:
            assert "(+3 more)" not in item

    def test_handles_empty_guidance_cards(self):
        """Should return empty lists for empty guidance cards."""
        result = extract_available_from_guidance([])
        assert result["objects_here"] == []
        assert result["holding"] == []
        assert result["exits"] == []

    def test_handles_none_guidance_cards(self):
        """Should return empty lists for None input."""
        result = extract_available_from_guidance(None)
        assert result["objects_here"] == []
        assert result["holding"] == []
        assert result["exits"] == []


class TestCheckInventedObjects:
    """Test check_invented_objects function."""

    def test_identifies_invented_objects(self):
        """Should identify objects NOT in available lists."""
        marker_targets = ["ヨーグルト", "フルーツ"]
        available = {
            "objects_here": ["コーヒーメーカー", "マグカップ", "砂糖"],
            "holding": [],
            "exits": ["リビング"],
        }
        invented = check_invented_objects(marker_targets, available)
        assert "ヨーグルト" in invented
        assert "フルーツ" in invented

    def test_does_not_flag_available_objects(self):
        """Should NOT flag objects that ARE in available lists."""
        marker_targets = ["マグカップ", "砂糖"]
        available = {
            "objects_here": ["コーヒーメーカー", "マグカップ", "砂糖"],
            "holding": [],
            "exits": ["リビング"],
        }
        invented = check_invented_objects(marker_targets, available)
        assert "マグカップ" not in invented
        assert "砂糖" not in invented
        assert invented == []

    def test_partial_matching(self):
        """Should use partial matching for flexibility."""
        marker_targets = ["冷蔵庫"]
        available = {
            "objects_here": ["冷蔵庫の中", "コーヒーメーカー"],
            "holding": [],
            "exits": [],
        }
        invented = check_invented_objects(marker_targets, available)
        # "冷蔵庫" should match "冷蔵庫の中"
        assert "冷蔵庫" not in invented

    def test_partial_matching_reverse(self):
        """Should match when available item is substring of target."""
        marker_targets = ["冷蔵庫の中"]
        available = {
            "objects_here": ["冷蔵庫", "コーヒーメーカー"],
            "holding": [],
            "exits": [],
        }
        invented = check_invented_objects(marker_targets, available)
        # "冷蔵庫の中" contains "冷蔵庫"
        assert "冷蔵庫の中" not in invented

    def test_checks_holding_list(self):
        """Should check HOLDING list as well."""
        marker_targets = ["マグカップ"]
        available = {
            "objects_here": [],
            "holding": ["マグカップ"],
            "exits": [],
        }
        invented = check_invented_objects(marker_targets, available)
        assert "マグカップ" not in invented

    def test_checks_exits_list(self):
        """Should check EXITS list for location targets."""
        marker_targets = ["リビング"]
        available = {
            "objects_here": [],
            "holding": [],
            "exits": ["リビング", "キッチン"],
        }
        invented = check_invented_objects(marker_targets, available)
        assert "リビング" not in invented

    def test_empty_marker_targets(self):
        """Should return empty list for empty marker targets."""
        available = {
            "objects_here": ["コーヒーメーカー"],
            "holding": [],
            "exits": ["リビング"],
        }
        invented = check_invented_objects([], available)
        assert invented == []

    def test_no_duplicates(self):
        """Should not return duplicate invented objects."""
        marker_targets = ["ヨーグルト", "ヨーグルト"]
        available = {
            "objects_here": ["コーヒーメーカー"],
            "holding": [],
            "exits": [],
        }
        invented = check_invented_objects(marker_targets, available)
        assert invented.count("ヨーグルト") == 1


class TestRealWorldScenarios:
    """Test with real-world examples from Gate-3 failures."""

    def test_coffee_trap_turn4_invented(self):
        """Test with coffee_trap Turn 4 where LLM invented ヨーグルト and フルーツ."""
        # Raw speech: "*冷蔵庫を開けてヨーグルトとフルーツを取り出す*"
        # This was blocked because ヨーグルト and フルーツ don't exist
        guidance_cards = [
            """<<<SYSTEM_SIGNAL>>>
[ERROR_CODE] MISSING_OBJECT
[BLOCKED_TARGET] ヨーグルト

[ALTERNATIVES]
OBJECTS_HERE: コーヒーメーカー, マグカップ, 砂糖, ミルク, トースター, 冷蔵庫
HOLDING: (none)
EXITS: リビング

[ALLOWED_ACTION_PATTERNS]
- USE(object) - use an object from OBJECTS_HERE
- TAKE(object) - take an object from OBJECTS_HERE
- SAY() - just speak without physical action

[CONSTRAINT]
ONLY use objects/locations from OBJECTS_HERE, HOLDING, or EXITS
DO NOT create, imagine, or reference items not in these lists
<<<END_SIGNAL>>>"""
        ]

        available = extract_available_from_guidance(guidance_cards)
        assert "コーヒーメーカー" in available["objects_here"]
        assert "マグカップ" in available["objects_here"]
        assert "砂糖" in available["objects_here"]

        # Check invented objects
        marker_targets = ["冷蔵庫", "ヨーグルト", "フルーツ"]
        invented = check_invented_objects(marker_targets, available)

        # 冷蔵庫 should NOT be invented (it's in OBJECTS_HERE)
        assert "冷蔵庫" not in invented
        # ヨーグルト and フルーツ should be invented (not in any list)
        assert "ヨーグルト" in invented
        assert "フルーツ" in invented

    def test_retry_with_valid_objects(self):
        """Test when retry uses valid objects from available list."""
        # After retry, LLM uses *マグカップを手に取り、砂糖を少し入れる*
        guidance_cards = [
            """OBJECTS_HERE: コーヒーメーカー, マグカップ, 砂糖, ミルク
HOLDING: (none)
EXITS: リビング"""
        ]

        available = extract_available_from_guidance(guidance_cards)
        marker_targets = ["マグカップ", "砂糖"]
        invented = check_invented_objects(marker_targets, available)

        # Both should be valid (in OBJECTS_HERE)
        assert invented == []


class TestNormalizeText:
    """Test normalize_text function."""

    def test_empty_string(self):
        """Should return empty string for empty input."""
        assert normalize_text("") == ""

    def test_none_input(self):
        """Should return empty string for None input."""
        assert normalize_text(None) == ""

    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        assert normalize_text("  コーヒー  ") == "コーヒー"

    def test_removes_japanese_punctuation(self):
        """Should remove Japanese punctuation."""
        assert normalize_text("コーヒー、メーカー。") == "コーヒーメーカー"

    def test_removes_brackets(self):
        """Should remove Japanese brackets."""
        assert normalize_text("「コーヒー」") == "コーヒー"
        assert normalize_text("『コーヒー』") == "コーヒー"

    def test_nfkc_normalization(self):
        """Should apply NFKC normalization (full-width to half-width)."""
        # Full-width letters → half-width
        assert normalize_text("ＡＢＣ") == "abc"
        # Full-width numbers → half-width
        assert normalize_text("１２３") == "123"

    def test_lowercase(self):
        """Should convert to lowercase."""
        assert normalize_text("Coffee") == "coffee"
        assert normalize_text("COFFEE") == "coffee"

    def test_removes_middle_dot(self):
        """Should remove middle dot (・)."""
        assert normalize_text("コーヒー・メーカー") == "コーヒーメーカー"

    def test_removes_full_width_space(self):
        """Should remove full-width space (　)."""
        assert normalize_text("コーヒー　メーカー") == "コーヒーメーカー"


class TestCheckInventedObjectsDetailed:
    """Test check_invented_objects_detailed function."""

    def test_returns_invented_result(self):
        """Should return InventedResult with all fields."""
        marker_targets = ["ヨーグルト"]
        available = {
            "objects_here": ["コーヒーメーカー"],
            "holding": [],
            "exits": ["リビング"],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        assert "ヨーグルト" in result.invented
        assert "ヨーグルト" in result.reasons
        assert result.reasons["ヨーグルト"] == "no_match_in_available"
        assert result.available_empty is False

    def test_available_empty_flag(self):
        """Should set available_empty when all lists are empty."""
        marker_targets = ["ヨーグルト"]
        available = {
            "objects_here": [],
            "holding": [],
            "exits": [],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        assert result.available_empty is True
        assert result.reasons["ヨーグルト"] == "available_lists_empty"

    def test_available_empty_false_when_no_markers(self):
        """Should set available_empty=False when marker_targets is empty but lists have items."""
        marker_targets = []
        available = {
            "objects_here": ["コーヒーメーカー", "マグカップ"],
            "holding": [],
            "exits": ["リビング"],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        # available_empty should be False because lists have items
        assert result.available_empty is False
        assert result.invented == []

    def test_available_empty_true_when_no_markers_and_no_items(self):
        """Should set available_empty=True when marker_targets is empty AND lists are empty."""
        marker_targets = []
        available = {
            "objects_here": [],
            "holding": [],
            "exits": [],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        assert result.available_empty is True
        assert result.invented == []

    def test_exact_match_reason(self):
        """Should set exact_match reason for exact matches."""
        marker_targets = ["コーヒーメーカー"]
        available = {
            "objects_here": ["コーヒーメーカー"],
            "holding": [],
            "exits": [],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        assert result.invented == []
        assert result.reasons["コーヒーメーカー"] == "exact_match"

    def test_partial_match_reason(self):
        """Should set partial_match reason for substring matches."""
        marker_targets = ["冷蔵庫"]
        available = {
            "objects_here": ["冷蔵庫の中"],
            "holding": [],
            "exits": [],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        assert result.invented == []
        assert "partial_match:" in result.reasons["冷蔵庫"]

    def test_too_short_target_skipped(self):
        """Should skip targets that are too short (1 char)."""
        marker_targets = ["を", "に"]  # Particles
        available = {
            "objects_here": ["コーヒーメーカー"],
            "holding": [],
            "exits": [],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        assert result.invented == []
        assert result.reasons.get("を") == "target_too_short"
        assert result.reasons.get("に") == "target_too_short"

    def test_normalization_matching(self):
        """Should match after normalization."""
        marker_targets = ["ｺｰﾋｰﾒｰｶｰ"]  # Half-width katakana
        available = {
            "objects_here": ["コーヒーメーカー"],  # Full-width katakana
            "holding": [],
            "exits": [],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        # Should match after NFKC normalization
        assert result.invented == []

    def test_milk_not_in_available(self):
        """牛乳がavailableにない時はinventedになる。"""
        marker_targets = ["牛乳"]
        available = {
            "objects_here": ["コーヒーメーカー", "マグカップ"],
            "holding": [],
            "exits": ["リビング"],
        }
        result = check_invented_objects_detailed(marker_targets, available)

        assert "牛乳" in result.invented
        assert result.reasons["牛乳"] == "no_match_in_available"


class TestInventedObjectsWithNormalization:
    """Test invented objects detection with normalization edge cases."""

    def test_case_insensitive_match(self):
        """Should match case-insensitively."""
        marker_targets = ["Coffee"]
        available = {
            "objects_here": ["coffee"],
            "holding": [],
            "exits": [],
        }
        invented = check_invented_objects(marker_targets, available)
        assert invented == []

    def test_full_width_half_width_match(self):
        """Should match full-width and half-width numbers."""
        marker_targets = ["部屋１"]  # Full-width 1
        available = {
            "objects_here": [],
            "holding": [],
            "exits": ["部屋1"],  # Half-width 1
        }
        invented = check_invented_objects(marker_targets, available)
        assert invented == []

    def test_punctuation_stripped_match(self):
        """Should match when only difference is punctuation."""
        marker_targets = ["コーヒー、メーカー"]
        available = {
            "objects_here": ["コーヒーメーカー"],
            "holding": [],
            "exits": [],
        }
        invented = check_invented_objects(marker_targets, available)
        assert invented == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
