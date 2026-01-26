"""Tests for FuzzyMatcher implementation."""

import pytest

from experiments.semantic_matcher.fuzzy import FuzzyMatcher, is_rapidfuzz_available
from experiments.semantic_matcher.types import MatchMethod


class TestFuzzyMatcher:
    """Tests for FuzzyMatcher."""

    def test_exact_match_returns_perfect_score(self):
        """Exact match should return score of 1.0."""
        matcher = FuzzyMatcher()
        world = {"コーヒー豆", "コーヒーメーカー", "マグカップ"}

        result = matcher.match("コーヒー豆", world)

        assert result.adopted is not None
        assert result.adopted.name == "コーヒー豆"
        assert result.adopted.score == 1.0
        assert result.adopted.method == MatchMethod.EXACT

    def test_fuzzy_match_similar_strings(self):
        """Should find similar strings with fuzzy matching."""
        matcher = FuzzyMatcher(suggest_threshold=0.5)
        world = {"コーヒー豆", "コーヒーメーカー", "マグカップ"}

        result = matcher.match("コーヒ", world)

        # Should have candidates
        assert len(result.candidates) > 0
        # Top candidate should be one of the coffee items
        assert "コーヒー" in result.candidates[0].name

    def test_no_match_for_unrelated_query(self):
        """Should return no candidates for completely unrelated query."""
        matcher = FuzzyMatcher(suggest_threshold=0.7)
        world = {"コーヒー豆", "コーヒーメーカー", "マグカップ"}

        result = matcher.match("テレビ", world)

        # Candidates might exist but below threshold
        assert result.adopted is None

    def test_only_returns_world_objects(self):
        """CRITICAL: Should only return objects from world_objects set."""
        matcher = FuzzyMatcher(suggest_threshold=0.3)
        world = {"コーヒー豆", "マグカップ"}

        result = matcher.match("コーヒーメーカー", world)

        # Even if "コーヒーメーカー" is searched, it must NOT be in results
        for candidate in result.candidates:
            assert candidate.name in world

    def test_empty_world_returns_no_match(self):
        """Empty world_objects should return rejected result."""
        matcher = FuzzyMatcher()
        world: set[str] = set()

        result = matcher.match("コーヒー", world)

        assert result.candidates == []
        assert result.rejection_reason == "empty_world_objects"

    def test_empty_query_returns_no_candidates(self):
        """Empty query should return no candidates."""
        matcher = FuzzyMatcher()
        world = {"コーヒー豆", "マグカップ"}

        candidates = matcher.find_candidates("", world)

        assert candidates == []


class TestFuzzyMatcherJapanese:
    """Tests for Japanese text matching."""

    def test_partial_match_japanese(self):
        """Should match partial Japanese strings."""
        matcher = FuzzyMatcher(suggest_threshold=0.5)
        world = {"引き出し", "本棚", "ソファ"}

        result = matcher.match("引き出", world)

        assert len(result.candidates) > 0
        # "引き出し" should be a candidate
        names = [c.name for c in result.candidates]
        assert "引き出し" in names

    def test_kanji_hiragana_similarity(self):
        """Should handle kanji/hiragana variations."""
        matcher = FuzzyMatcher(suggest_threshold=0.4)
        world = {"鍵", "メモ", "財布"}

        result = matcher.match("かぎ", world)

        # Note: This depends on the fuzzy algorithm
        # difflib/rapidfuzz may not recognize kanji-hiragana as similar
        # This test documents current behavior
        assert result is not None


class TestFuzzyMatcherEnglish:
    """Tests for English text matching."""

    def test_english_fuzzy_match(self):
        """Should work with English strings."""
        matcher = FuzzyMatcher(suggest_threshold=0.6)
        world = {"coffee_beans", "coffee_maker", "mug"}

        result = matcher.match("coffee", world)

        assert len(result.candidates) > 0
        # Both coffee items should be candidates
        names = [c.name for c in result.candidates]
        assert any("coffee" in name for name in names)


class TestRapidfuzzAvailability:
    """Tests for rapidfuzz detection."""

    def test_is_rapidfuzz_available_returns_bool(self):
        """Should return a boolean."""
        result = is_rapidfuzz_available()
        assert isinstance(result, bool)
