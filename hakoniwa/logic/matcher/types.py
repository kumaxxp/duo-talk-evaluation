"""Type definitions for Semantic Matcher.

Defines DTOs for match candidates, results, and audit logging.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MatchMethod(Enum):
    """Matching method used."""

    FUZZY = "fuzzy"
    EMBEDDING = "embedding"
    EXACT = "exact"


class AdoptionStatus(Enum):
    """Status of match adoption."""

    AUTO_ADOPTED = "auto_adopted"
    SUGGESTED = "suggested"
    REJECTED = "rejected"


@dataclass(frozen=True)
class MatchCandidate:
    """A candidate match for a query.

    Attributes:
        name: The matched object name from world
        score: Similarity score (0.0 to 1.0)
        method: The matching method used
    """

    name: str
    score: float
    method: MatchMethod = MatchMethod.FUZZY

    def __post_init__(self):
        """Validate score range."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between 0.0 and 1.0, got {self.score}")


@dataclass
class MatchResult:
    """Result of a matching operation.

    Attributes:
        query: The original query string
        candidates: List of match candidates, sorted by score descending
        adopted: The adopted candidate (if any)
        status: The adoption status
        rejection_reason: Reason for rejection (if rejected)
    """

    query: str
    candidates: list[MatchCandidate]
    adopted: MatchCandidate | None = None
    status: AdoptionStatus = AdoptionStatus.SUGGESTED
    rejection_reason: str | None = None


@dataclass
class AuditLogEntry:
    """Audit log entry for a matching operation.

    All matching operations must be logged for traceability.

    Attributes:
        timestamp: When the operation occurred
        input_query: The original query
        world_objects: The set of objects in the world
        candidates: Match candidates with scores
        adopted: The adopted candidate name (if any)
        status: The adoption status
        rejection_reason: Reason for rejection (if any)
    """

    timestamp: datetime
    input_query: str
    world_objects: list[str]
    candidates: list[dict]  # [{"name": str, "score": float, "method": str}]
    adopted: str | None
    status: str
    rejection_reason: str | None = None

    @classmethod
    def from_match_result(
        cls, result: MatchResult, world_objects: set[str]
    ) -> "AuditLogEntry":
        """Create audit log entry from a match result.

        Args:
            result: The match result
            world_objects: The world objects used for matching

        Returns:
            AuditLogEntry instance
        """
        return cls(
            timestamp=datetime.now(),
            input_query=result.query,
            world_objects=sorted(world_objects),
            candidates=[
                {
                    "name": c.name,
                    "score": c.score,
                    "method": c.method.value,
                }
                for c in result.candidates
            ],
            adopted=result.adopted.name if result.adopted else None,
            status=result.status.value,
            rejection_reason=result.rejection_reason,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "input_query": self.input_query,
            "world_objects": self.world_objects,
            "candidates": self.candidates,
            "adopted": self.adopted,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
        }


# Generic nouns that should not be auto-adopted
GENERIC_NOUNS: frozenset[str] = frozenset(
    {
        "床",
        "壁",
        "天井",
        "空気",
        "部屋",
        "場所",
        "floor",
        "wall",
        "ceiling",
        "air",
        "room",
        "place",
    }
)
