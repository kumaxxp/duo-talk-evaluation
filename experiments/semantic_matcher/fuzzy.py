"""Fuzzy string matching implementation.

Uses rapidfuzz if available, falls back to difflib otherwise.
"""

from experiments.semantic_matcher.matcher import Matcher
from experiments.semantic_matcher.types import MatchCandidate, MatchMethod

# Try to import rapidfuzz, fall back to difflib
try:
    from rapidfuzz import fuzz, process

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    import difflib

    RAPIDFUZZ_AVAILABLE = False


class FuzzyMatcher(Matcher):
    """Fuzzy string matching implementation.

    Uses edit distance / sequence matching to find similar strings.
    """

    def __init__(
        self,
        auto_adopt_threshold: float = 0.9,
        suggest_threshold: float = 0.7,
        allow_auto_adopt: bool = False,
    ):
        """Initialize fuzzy matcher.

        Args:
            auto_adopt_threshold: Score >= this will be auto-adopted (if allowed)
            suggest_threshold: Score >= this will be suggested
            allow_auto_adopt: If False, all matches are suggestions only
        """
        super().__init__(
            auto_adopt_threshold=auto_adopt_threshold,
            suggest_threshold=suggest_threshold,
            allow_auto_adopt=allow_auto_adopt,
        )

    def find_candidates(
        self, query: str, world_objects: set[str], limit: int = 5
    ) -> list[MatchCandidate]:
        """Find fuzzy match candidates.

        CRITICAL: Only returns candidates that exist in world_objects.

        Args:
            query: The query string to match
            world_objects: Set of valid object names in the world
            limit: Maximum number of candidates to return

        Returns:
            List of MatchCandidate, sorted by score descending
        """
        if not query or not world_objects:
            return []

        candidates_list = list(world_objects)

        if RAPIDFUZZ_AVAILABLE:
            return self._fuzzy_match_rapidfuzz(query, candidates_list, limit)
        else:
            return self._fuzzy_match_difflib(query, candidates_list, limit)

    def _fuzzy_match_rapidfuzz(
        self, query: str, candidates: list[str], limit: int
    ) -> list[MatchCandidate]:
        """Match using rapidfuzz library.

        Args:
            query: The query string
            candidates: List of candidate strings
            limit: Maximum results

        Returns:
            List of MatchCandidate
        """
        results = process.extract(
            query,
            candidates,
            scorer=fuzz.ratio,
            limit=limit,
        )

        return [
            MatchCandidate(
                name=name,
                score=score / 100.0,  # rapidfuzz returns 0-100
                method=MatchMethod.FUZZY,
            )
            for name, score, _ in results
            if score / 100.0 >= self.suggest_threshold
        ]

    def _fuzzy_match_difflib(
        self, query: str, candidates: list[str], limit: int
    ) -> list[MatchCandidate]:
        """Match using standard library difflib.

        Args:
            query: The query string
            candidates: List of candidate strings
            limit: Maximum results

        Returns:
            List of MatchCandidate
        """
        # Calculate similarity for each candidate
        scored = []
        for candidate in candidates:
            # SequenceMatcher ratio is between 0 and 1
            score = difflib.SequenceMatcher(None, query, candidate).ratio()
            if score >= self.suggest_threshold:
                scored.append((candidate, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            MatchCandidate(
                name=name,
                score=score,
                method=MatchMethod.FUZZY,
            )
            for name, score in scored[:limit]
        ]


def is_rapidfuzz_available() -> bool:
    """Check if rapidfuzz is available.

    Returns:
        True if rapidfuzz is installed
    """
    return RAPIDFUZZ_AVAILABLE
