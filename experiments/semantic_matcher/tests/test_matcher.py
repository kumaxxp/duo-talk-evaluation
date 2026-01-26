"""Tests for Matcher interface."""

import pytest

from experiments.semantic_matcher.matcher import Matcher
from experiments.semantic_matcher.fuzzy import FuzzyMatcher
from experiments.semantic_matcher.types import (
    MatchCandidate,
    MatchResult,
    AdoptionStatus,
    MatchMethod,
)


class TestMatcherInterface:
    """Tests for Matcher abstract interface."""

    def test_matcher_is_abstract(self):
        """Cannot instantiate Matcher directly."""
        with pytest.raises(TypeError):
            Matcher()  # type: ignore

    def test_fuzzy_matcher_is_matcher(self):
        """FuzzyMatcher should be a Matcher subclass."""
        matcher = FuzzyMatcher()
        assert isinstance(matcher, Matcher)


class TestMatcherThresholds:
    """Tests for matcher threshold configuration."""

    def test_default_thresholds(self):
        """Default thresholds should be reasonable."""
        matcher = FuzzyMatcher()

        assert matcher.auto_adopt_threshold == 0.9
        assert matcher.suggest_threshold == 0.7
        assert not matcher.allow_auto_adopt

    def test_custom_thresholds(self):
        """Should accept custom thresholds."""
        matcher = FuzzyMatcher(
            auto_adopt_threshold=0.95,
            suggest_threshold=0.6,
            allow_auto_adopt=True,
        )

        assert matcher.auto_adopt_threshold == 0.95
        assert matcher.suggest_threshold == 0.6
        assert matcher.allow_auto_adopt


class TestMatchResultStructure:
    """Tests for MatchResult structure."""

    def test_match_result_has_query(self):
        """MatchResult should contain original query."""
        matcher = FuzzyMatcher()
        world = {"A", "B", "C"}

        result = matcher.match("X", world)

        assert result.query == "X"

    def test_match_result_has_candidates_list(self):
        """MatchResult should contain candidates list."""
        matcher = FuzzyMatcher()
        world = {"A", "B", "C"}

        result = matcher.match("A", world)

        assert isinstance(result.candidates, list)

    def test_match_result_has_status(self):
        """MatchResult should have status."""
        matcher = FuzzyMatcher()
        world = {"A", "B", "C"}

        result = matcher.match("X", world)

        assert result.status in AdoptionStatus


class TestMatchCandidateValidation:
    """Tests for MatchCandidate validation."""

    def test_score_must_be_in_range(self):
        """Score must be between 0 and 1."""
        # Valid scores
        MatchCandidate(name="test", score=0.0)
        MatchCandidate(name="test", score=0.5)
        MatchCandidate(name="test", score=1.0)

        # Invalid scores
        with pytest.raises(ValueError):
            MatchCandidate(name="test", score=-0.1)

        with pytest.raises(ValueError):
            MatchCandidate(name="test", score=1.1)

    def test_candidate_is_immutable(self):
        """MatchCandidate should be immutable (frozen dataclass)."""
        candidate = MatchCandidate(name="test", score=0.5)

        with pytest.raises(AttributeError):
            candidate.name = "modified"  # type: ignore


class TestExactMatchHandling:
    """Tests for exact match special handling."""

    def test_exact_match_returns_score_one(self):
        """Exact match should return score of 1.0."""
        matcher = FuzzyMatcher()
        world = {"target", "other"}

        result = matcher.match("target", world)

        assert result.adopted is not None
        assert result.adopted.score == 1.0

    def test_exact_match_uses_exact_method(self):
        """Exact match should use EXACT method."""
        matcher = FuzzyMatcher()
        world = {"target"}

        result = matcher.match("target", world)

        assert result.adopted is not None
        assert result.adopted.method == MatchMethod.EXACT

    def test_exact_match_always_adopted(self):
        """Exact match should always be adopted."""
        matcher = FuzzyMatcher(allow_auto_adopt=False)
        world = {"target"}

        result = matcher.match("target", world)

        assert result.status == AdoptionStatus.AUTO_ADOPTED


class TestSortingBehavior:
    """Tests for candidate sorting."""

    def test_candidates_sorted_by_score_descending(self):
        """Candidates should be sorted by score, highest first."""
        matcher = FuzzyMatcher(suggest_threshold=0.3)
        world = {"aaa", "aaab", "aaabc"}

        result = matcher.match("aaa", world)

        scores = [c.score for c in result.candidates]
        assert scores == sorted(scores, reverse=True)
