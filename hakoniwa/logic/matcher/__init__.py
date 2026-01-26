"""Semantic Matcher for MISSING_OBJECT resolution.

Provides fuzzy string matching to suggest correct object names
when LLM references objects that don't exist in the world.

Key Features:
- Fuzzy matching (rapidfuzz/difflib fallback)
- Query expansion (XのY pattern, action particle extraction)
- world_objects filtering (No World Expansion principle)
- Auto-adopt DISABLED by default (suggestion only)
- Full audit logging

Usage:
    from hakoniwa.logic.matcher import FuzzyMatcher, suggest_match

    # Quick suggestion
    suggestion = suggest_match("冷蔵庫の牛乳", world_objects={"冷蔵庫", "牛乳"})
    if suggestion:
        target, score = suggestion
        print(f"Did you mean: {target}? (score: {score:.2f})")

    # Full control
    matcher = FuzzyMatcher(suggest_threshold=0.7, allow_auto_adopt=False)
    result = matcher.match("テレビのリモコン", world_objects)

Guardrails:
- Auto-adopt is ALWAYS disabled (allow_auto_adopt=False enforced)
- Only suggests objects that exist in world_objects
- Generic nouns (床, 壁, etc.) are never auto-adopted
"""

from hakoniwa.logic.matcher.types import (
    MatchMethod,
    AdoptionStatus,
    MatchCandidate,
    MatchResult,
    AuditLogEntry,
    GENERIC_NOUNS,
)
from hakoniwa.logic.matcher.matcher import Matcher
from hakoniwa.logic.matcher.fuzzy import FuzzyMatcher, is_rapidfuzz_available
from hakoniwa.logic.matcher.preprocess import (
    expand_queries,
    extract_x_no_y_pattern,
    normalize_query,
    extract_action_object,
)
from hakoniwa.logic.matcher.audit_log import (
    AuditLogger,
    InMemoryAuditLogger,
    load_audit_log,
)


def suggest_match(
    query: str,
    world_objects: set[str],
    threshold: float = 0.7,
    use_expansion: bool = True,
) -> tuple[str, float] | None:
    """Suggest a matching object for a query (convenience function).

    This is the recommended entry point for MISSING_OBJECT resolution.
    Auto-adopt is ALWAYS disabled; this function only returns suggestions.

    Args:
        query: The query string (e.g., "冷蔵庫の牛乳")
        world_objects: Set of valid object names in the world
        threshold: Minimum similarity score (default: 0.7)
        use_expansion: Whether to use query expansion (default: True)

    Returns:
        Tuple of (suggested_name, score) if match found, None otherwise

    Example:
        >>> suggest_match("テレビのリモコン", {"テレビ", "ソファ"})
        ("テレビ", 1.0)

        >>> suggest_match("存在しない", {"テレビ", "ソファ"})
        None
    """
    matcher = FuzzyMatcher(
        suggest_threshold=threshold,
        allow_auto_adopt=False,  # CRITICAL: Never auto-adopt
    )

    # Optionally expand queries
    queries_to_try = [query]
    if use_expansion:
        expanded = expand_queries(query, world_objects=world_objects)
        if expanded:
            queries_to_try = expanded

    best_match = None
    best_score = 0.0

    for q in queries_to_try:
        result = matcher.match(q, world_objects)
        if result.candidates:
            top = result.candidates[0]
            if top.score > best_score and top.score >= threshold:
                best_match = top.name
                best_score = top.score

    if best_match:
        return (best_match, best_score)
    return None


__all__ = [
    # Types
    "MatchMethod",
    "AdoptionStatus",
    "MatchCandidate",
    "MatchResult",
    "AuditLogEntry",
    "GENERIC_NOUNS",
    # Matchers
    "Matcher",
    "FuzzyMatcher",
    "is_rapidfuzz_available",
    # Preprocessor
    "expand_queries",
    "extract_x_no_y_pattern",
    "normalize_query",
    "extract_action_object",
    # Audit
    "AuditLogger",
    "InMemoryAuditLogger",
    "load_audit_log",
    # Convenience
    "suggest_match",
]
