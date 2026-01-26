"""Matcher interface for Semantic Matcher.

Defines the abstract interface that all matcher implementations must follow.
"""

from abc import ABC, abstractmethod

from hakoniwa.logic.matcher.types import (
    MatchCandidate,
    MatchResult,
    MatchMethod,
    AdoptionStatus,
    GENERIC_NOUNS,
)


class Matcher(ABC):
    """Abstract base class for semantic matchers.

    All matchers must:
    1. Only match against objects in the provided world_objects set
    2. Never return candidates that don't exist in world_objects
    3. Respect confidence thresholds
    4. Handle generic nouns appropriately

    Principle: World is Truth - No World Expansion
    """

    # Default confidence thresholds
    AUTO_ADOPT_THRESHOLD: float = 0.9
    SUGGEST_THRESHOLD: float = 0.7

    def __init__(
        self,
        auto_adopt_threshold: float = 0.9,
        suggest_threshold: float = 0.7,
        allow_auto_adopt: bool = False,
    ):
        """Initialize matcher with thresholds.

        Args:
            auto_adopt_threshold: Score >= this will be auto-adopted (if allowed)
            suggest_threshold: Score >= this will be suggested
            allow_auto_adopt: If False, all matches are suggestions only
        """
        self.auto_adopt_threshold = auto_adopt_threshold
        self.suggest_threshold = suggest_threshold
        self.allow_auto_adopt = allow_auto_adopt

    @abstractmethod
    def find_candidates(
        self, query: str, world_objects: set[str], limit: int = 5
    ) -> list[MatchCandidate]:
        """Find match candidates for a query.

        MUST only return candidates that exist in world_objects.

        Args:
            query: The query string to match
            world_objects: Set of valid object names in the world
            limit: Maximum number of candidates to return

        Returns:
            List of MatchCandidate, sorted by score descending
        """
        pass

    def match(self, query: str, world_objects: set[str]) -> MatchResult:
        """Perform matching and determine adoption status.

        Args:
            query: The query string to match
            world_objects: Set of valid object names in the world

        Returns:
            MatchResult with candidates and adoption decision
        """
        # Guard: Empty world means no match possible
        if not world_objects:
            return MatchResult(
                query=query,
                candidates=[],
                adopted=None,
                status=AdoptionStatus.REJECTED,
                rejection_reason="empty_world_objects",
            )

        # Guard: Exact match takes priority
        if query in world_objects:
            exact_match = MatchCandidate(name=query, score=1.0, method=MatchMethod.EXACT)
            return MatchResult(
                query=query,
                candidates=[exact_match],
                adopted=exact_match,
                status=AdoptionStatus.AUTO_ADOPTED,
                rejection_reason=None,
            )

        # Find fuzzy candidates
        candidates = self.find_candidates(query, world_objects)

        # No candidates found
        if not candidates:
            return MatchResult(
                query=query,
                candidates=[],
                adopted=None,
                status=AdoptionStatus.REJECTED,
                rejection_reason="no_candidates_above_threshold",
            )

        # Determine adoption for top candidate
        top_candidate = candidates[0]

        # Check if top candidate should be adopted
        adopted, status, rejection_reason = self._determine_adoption(top_candidate)

        return MatchResult(
            query=query,
            candidates=candidates,
            adopted=adopted,
            status=status,
            rejection_reason=rejection_reason,
        )

    def _determine_adoption(
        self, candidate: MatchCandidate
    ) -> tuple[MatchCandidate | None, AdoptionStatus, str | None]:
        """Determine if a candidate should be adopted.

        Args:
            candidate: The candidate to evaluate

        Returns:
            Tuple of (adopted_candidate, status, rejection_reason)
        """
        # Guard: Generic nouns are never auto-adopted
        if candidate.name in GENERIC_NOUNS:
            return (
                None,
                AdoptionStatus.SUGGESTED,
                "generic_noun_no_auto_adopt",
            )

        # Guard: Score below suggestion threshold
        if candidate.score < self.suggest_threshold:
            return (
                None,
                AdoptionStatus.REJECTED,
                "below_suggest_threshold",
            )

        # Check for auto-adoption
        if (
            self.allow_auto_adopt
            and candidate.score >= self.auto_adopt_threshold
        ):
            return (candidate, AdoptionStatus.AUTO_ADOPTED, None)

        # Default: Suggest only
        return (None, AdoptionStatus.SUGGESTED, None)

    def should_auto_adopt(self, candidate: MatchCandidate) -> bool:
        """Check if a candidate should be auto-adopted.

        Args:
            candidate: The candidate to check

        Returns:
            True if should auto-adopt, False otherwise
        """
        if not self.allow_auto_adopt:
            return False
        if candidate.name in GENERIC_NOUNS:
            return False
        return candidate.score >= self.auto_adopt_threshold
