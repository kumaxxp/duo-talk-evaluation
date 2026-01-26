"""Semantic Matcher - Object name matching for MISSING_OBJECT reduction.

This module provides fuzzy string matching to resolve name mismatches
between GM responses and scenario definitions.

IMPORTANT: This is an experimental module. Do not import into main code.

Principle: World is Truth - No World Expansion
- Only match against existing world objects
- Never create or suggest non-existent objects
"""

from experiments.semantic_matcher.types import (
    MatchCandidate,
    MatchResult,
    AuditLogEntry,
)
from experiments.semantic_matcher.matcher import Matcher
from experiments.semantic_matcher.fuzzy import FuzzyMatcher

__all__ = [
    "MatchCandidate",
    "MatchResult",
    "AuditLogEntry",
    "Matcher",
    "FuzzyMatcher",
]
