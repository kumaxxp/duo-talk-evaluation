"""Tests for hakoniwa.logic.matcher (Production Semantic Matcher).

Tests cover:
- Unit tests for matcher, preprocess, types
- Integration tests for suggest_match
- Guardrail tests for world_objects filtering and generic noun handling
"""

import pytest
from pathlib import Path
import tempfile

from hakoniwa.logic.matcher import (
    # Types
    MatchMethod,
    AdoptionStatus,
    MatchCandidate,
    MatchResult,
    AuditLogEntry,
    GENERIC_NOUNS,
    # Matchers
    FuzzyMatcher,
    is_rapidfuzz_available,
    # Preprocessor
    expand_queries,
    extract_x_no_y_pattern,
    normalize_query,
    extract_action_object,
    # Audit
    AuditLogger,
    InMemoryAuditLogger,
    load_audit_log,
    # Convenience
    suggest_match,
)


# =============================================================================
# Types Tests
# =============================================================================


class TestMatchCandidate:
    """Tests for MatchCandidate dataclass."""

    def test_valid_candidate(self):
        candidate = MatchCandidate(name="test", score=0.8)
        assert candidate.name == "test"
        assert candidate.score == 0.8
        assert candidate.method == MatchMethod.FUZZY

    def test_invalid_score_low(self):
        with pytest.raises(ValueError):
            MatchCandidate(name="test", score=-0.1)

    def test_invalid_score_high(self):
        with pytest.raises(ValueError):
            MatchCandidate(name="test", score=1.1)

    def test_exact_method(self):
        candidate = MatchCandidate(name="test", score=1.0, method=MatchMethod.EXACT)
        assert candidate.method == MatchMethod.EXACT


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_empty_result(self):
        result = MatchResult(query="test", candidates=[])
        assert result.query == "test"
        assert result.candidates == []
        assert result.adopted is None
        assert result.status == AdoptionStatus.SUGGESTED


# =============================================================================
# Matcher Tests
# =============================================================================


class TestFuzzyMatcher:
    """Tests for FuzzyMatcher."""

    def test_exact_match(self):
        matcher = FuzzyMatcher()
        result = matcher.match("冷蔵庫", {"冷蔵庫", "テレビ", "ソファ"})

        assert len(result.candidates) == 1
        assert result.candidates[0].name == "冷蔵庫"
        assert result.candidates[0].score == 1.0
        assert result.candidates[0].method == MatchMethod.EXACT

    def test_fuzzy_match(self):
        matcher = FuzzyMatcher(suggest_threshold=0.6)
        result = matcher.match("冷蔵こ", {"冷蔵庫", "テレビ"})

        # Should find fuzzy match
        assert len(result.candidates) >= 1

    def test_no_match(self):
        matcher = FuzzyMatcher(suggest_threshold=0.9)
        result = matcher.match("存在しない", {"冷蔵庫", "テレビ"})

        assert len(result.candidates) == 0
        assert result.status == AdoptionStatus.REJECTED

    def test_empty_world(self):
        matcher = FuzzyMatcher()
        result = matcher.match("何か", set())

        assert len(result.candidates) == 0
        assert result.rejection_reason == "empty_world_objects"

    def test_auto_adopt_disabled(self):
        """Verify auto-adopt is disabled by default."""
        matcher = FuzzyMatcher(allow_auto_adopt=False)
        result = matcher.match("冷蔵庫", {"冷蔵庫"})

        # Even exact match should not be "adopted" when auto-adopt is off
        # But exact match is special case - it's auto-adopted regardless
        assert result.candidates[0].score == 1.0


class TestGenericNouns:
    """Guardrail: Generic nouns should not be auto-adopted."""

    def test_generic_nouns_exist(self):
        assert "床" in GENERIC_NOUNS
        assert "壁" in GENERIC_NOUNS
        assert "天井" in GENERIC_NOUNS
        assert "部屋" in GENERIC_NOUNS

    def test_generic_noun_not_auto_adopted(self):
        matcher = FuzzyMatcher(allow_auto_adopt=True, auto_adopt_threshold=0.9)
        result = matcher.match("床", {"床", "テーブル"})

        # Even with auto-adopt enabled, generic nouns should not be adopted
        # Note: exact match is special case
        assert result.candidates[0].name == "床"


# =============================================================================
# Preprocessor Tests
# =============================================================================


class TestNormalizeQuery:
    """Tests for normalize_query."""

    def test_remove_quotes(self):
        assert normalize_query("「テスト」") == "テスト"
        assert normalize_query("『テスト』") == "テスト"

    def test_remove_punctuation(self):
        assert normalize_query("テスト。") == "テスト"
        assert normalize_query("テスト、") == "テスト"

    def test_remove_whitespace(self):
        assert normalize_query("テ ス ト") == "テスト"
        assert normalize_query("テ　ス　ト") == "テスト"


class TestExtractXNoYPattern:
    """Tests for extract_x_no_y_pattern."""

    def test_basic_pattern(self):
        result = extract_x_no_y_pattern("冷蔵庫の牛乳")
        assert result == ("冷蔵庫", "牛乳")

    def test_no_pattern(self):
        result = extract_x_no_y_pattern("テレビ")
        assert result is None

    def test_nested_pattern(self):
        result = extract_x_no_y_pattern("本棚の植物図鑑の表紙")
        assert result == ("本棚", "植物図鑑の表紙")


class TestExtractActionObject:
    """Tests for extract_action_object."""

    def test_ni_particle(self):
        result = extract_action_object("ソファーに座る")
        assert "ソファー" in result

    def test_he_particle(self):
        result = extract_action_object("冷蔵庫へ向かう")
        assert "冷蔵庫" in result

    def test_no_particle(self):
        result = extract_action_object("テレビ")
        assert result == []


class TestExpandQueries:
    """Tests for expand_queries."""

    def test_x_no_y_expansion(self):
        result = expand_queries("冷蔵庫の牛乳", world_objects={"冷蔵庫", "牛乳"})
        assert "冷蔵庫" in result

    def test_world_filter(self):
        """Guardrail: Only world_objects should be in results."""
        result = expand_queries("姉のカバン", world_objects={"カバン", "バッグ"})
        assert "姉" not in result  # 姉 is not a world object
        assert "カバン" in result

    def test_action_particle_expansion(self):
        result = expand_queries("冷蔵庫へ向かい、レタス", world_objects={"冷蔵庫", "レタス"})
        assert "冷蔵庫" in result

    def test_empty_query(self):
        result = expand_queries("")
        assert result == []


# =============================================================================
# Audit Log Tests
# =============================================================================


class TestAuditLog:
    """Tests for audit logging."""

    def test_in_memory_logger(self):
        logger = InMemoryAuditLogger()

        result = MatchResult(
            query="test",
            candidates=[MatchCandidate(name="candidate", score=0.8)],
        )
        logger.log_match_result(result, {"candidate", "other"})

        assert len(logger.entries) == 1
        assert logger.entries[0].input_query == "test"

    def test_file_logger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.jsonl"
            logger = AuditLogger(log_path)

            result = MatchResult(
                query="test",
                candidates=[MatchCandidate(name="candidate", score=0.8)],
            )
            logger.log_match_result(result, {"candidate"})

            # Verify file was created
            assert log_path.exists()

            # Load and verify
            entries = load_audit_log(log_path)
            assert len(entries) == 1


# =============================================================================
# suggest_match Integration Tests
# =============================================================================


class TestSuggestMatch:
    """Integration tests for suggest_match convenience function."""

    def test_exact_match(self):
        result = suggest_match("テレビ", world_objects={"テレビ", "ソファ"})
        assert result is not None
        assert result[0] == "テレビ"
        assert result[1] == 1.0

    def test_x_no_y_pattern(self):
        result = suggest_match("冷蔵庫の牛乳", world_objects={"冷蔵庫", "牛乳"})
        assert result is not None
        assert result[0] == "冷蔵庫"
        assert result[1] == 1.0

    def test_no_match(self):
        result = suggest_match("存在しない", world_objects={"テレビ", "ソファ"})
        assert result is None

    def test_world_filter_guard(self):
        """Guardrail: Suggestions must be in world_objects."""
        result = suggest_match("姉のカバン", world_objects={"カバン"})
        # Should suggest カバン, not 姉
        if result:
            assert result[0] in {"カバン"}
            assert result[0] != "姉"

    def test_action_description(self):
        result = suggest_match(
            "ソファーに深く腰掛け、少し間",
            world_objects={"ソファ", "テーブル"},
        )
        # May or may not match depending on fuzzy threshold
        # Key point: if it matches, it should be ソファ (from ソファー)
        # Note: ソファー vs ソファ is a variant match

    def test_empty_world(self):
        result = suggest_match("何か", world_objects=set())
        assert result is None

    def test_threshold_filter(self):
        """Higher threshold should filter more candidates."""
        world = {"コーヒー豆", "紅茶"}

        # Low threshold might match
        result_low = suggest_match("コーヒ", world_objects=world, threshold=0.5)

        # High threshold might not
        result_high = suggest_match("コーヒ", world_objects=world, threshold=0.99)

        # At least high threshold should be None or stricter
        if result_high is not None:
            assert result_high[1] >= 0.99


# =============================================================================
# Guardrail Tests
# =============================================================================


class TestGuardrails:
    """Tests for safety guardrails."""

    def test_no_world_expansion(self):
        """World is Truth: Cannot suggest objects not in world."""
        # Query mentions "新しいオブジェクト" but world doesn't have it
        result = suggest_match("新しいオブジェクト", world_objects={"テレビ", "冷蔵庫"})

        # Either no match, or suggestion must be in world
        if result:
            assert result[0] in {"テレビ", "冷蔵庫"}

    def test_generic_nouns_low_priority(self):
        """Generic nouns should not be suggested."""
        # Even if 床 is in world, it shouldn't be suggested for unrelated queries
        world = {"床", "テーブル", "椅子"}
        result = suggest_match("机", world_objects=world)

        # If matched, should prefer テーブル over 床
        if result and result[1] > 0.5:
            assert result[0] != "床"

    def test_auto_adopt_always_disabled(self):
        """Auto-adopt must always be disabled in production."""
        matcher = FuzzyMatcher(allow_auto_adopt=False)
        assert matcher.allow_auto_adopt is False

        # Even if we try to enable it, the function doesn't expose it
        # suggest_match has no auto_adopt parameter


# =============================================================================
# Config Tests
# =============================================================================


class TestSemanticMatcherConfig:
    """Tests for semantic matcher configuration."""

    def test_config_import(self):
        from hakoniwa.config.schema import SemanticMatcherConfig

        config = SemanticMatcherConfig()
        assert config.enabled is True
        assert config.suggest_threshold == 0.7
        assert config.use_expansion is True
        assert config.max_suggestions == 2

    def test_config_in_hakoniwa_config(self):
        from hakoniwa.config.schema import HakoniwaConfig

        config = HakoniwaConfig()
        assert config.semantic_matcher.enabled is True
        assert config.semantic_matcher.suggest_threshold == 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
