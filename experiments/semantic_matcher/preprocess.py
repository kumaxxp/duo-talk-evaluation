"""Query preprocessor for Semantic Matcher.

Expands and normalizes queries to improve matching recall
while maintaining safety (no FP increase).

Key patterns handled:
- 「XのY」: Split into X and Y as separate candidates
- Long action descriptions: Extract potential object names
- Quote/punctuation normalization
"""

import re
from typing import Tuple


# Maximum query length for direct matching
MAX_QUERY_LENGTH = 20

# Patterns to remove from queries
REMOVE_PATTERNS = [
    r"[\s　]+",  # Whitespace (including full-width)
    r"[「」『』\"\'()]",  # Quotes and parentheses
    r"[。、,.]$",  # Trailing punctuation
]

# Action/movement particles to split on
ACTION_PARTICLES = ["に", "へ", "を", "で", "から", "まで"]

# Suffixes that indicate long-form variations
NORMALIZE_SUFFIXES = [
    ("ソファー", "ソファ"),
    ("テーブル", "テーブル"),  # Already normalized
]


def normalize_query(query: str) -> str:
    """Normalize a query string.

    - Strip whitespace
    - Remove quotes and parentheses
    - Remove trailing punctuation

    Args:
        query: Raw query string

    Returns:
        Normalized query string
    """
    result = query.strip()

    # Remove quotes and parentheses
    result = re.sub(r"[「」『』\"\'()（）]", "", result)

    # Remove trailing punctuation
    result = re.sub(r"[。、,.！？!?]+$", "", result)

    # Normalize whitespace
    result = re.sub(r"[\s　]+", "", result)

    return result


def extract_x_no_y_pattern(query: str) -> Tuple[str, str] | None:
    """Extract 「XのY」pattern from query.

    Args:
        query: Query string

    Returns:
        Tuple of (X, Y) if pattern found, None otherwise
    """
    # Look for first occurrence of の
    match = re.match(r"^(.+?)の(.+)$", query)

    if match:
        x_part = match.group(1).strip()
        y_part = match.group(2).strip()

        # Validate both parts are non-empty
        if x_part and y_part:
            return (x_part, y_part)

    return None


def extract_action_object(query: str) -> list[str]:
    """Extract potential object names from action descriptions.

    Handles patterns like:
    - 「冷蔵庫へ向かい」→ 冷蔵庫
    - 「ソファーに座る」→ ソファー/ソファ

    Args:
        query: Query string

    Returns:
        List of potential object names
    """
    candidates = []

    # Split on action particles
    for particle in ACTION_PARTICLES:
        if particle in query:
            parts = query.split(particle)
            if parts[0]:
                # Take the part before the particle
                obj = normalize_query(parts[0])
                if obj and len(obj) <= MAX_QUERY_LENGTH:
                    candidates.append(obj)
            break  # Only use first split

    return candidates


def normalize_variant(query: str) -> str:
    """Normalize variant spellings.

    Args:
        query: Query string

    Returns:
        Normalized variant
    """
    result = query

    for variant, normalized in NORMALIZE_SUFFIXES:
        if result.endswith(variant[:-1]) and variant != normalized:
            # Only normalize if it's a known variant
            pass  # Keep as-is for now, let fuzzy matching handle

    return result


def expand_queries(
    query: str,
    world_objects: set[str] | None = None,
) -> list[str]:
    """Expand a query into multiple candidate queries.

    Expansion rules:
    1. Normalize the original query
    2. Extract 「XのY」pattern → add X and Y
    3. Extract object from action descriptions
    4. Filter by world_objects if provided

    Args:
        query: Original query string
        world_objects: Optional set of valid world objects for filtering

    Returns:
        List of expanded query candidates, ordered by priority
    """
    if not query or not query.strip():
        return []

    candidates = []
    seen = set()

    def add_candidate(c: str) -> None:
        """Add candidate if valid and not seen."""
        c = normalize_query(c)
        if c and c not in seen:
            # Apply world_objects filter if provided
            if world_objects is None or c in world_objects:
                candidates.append(c)
                seen.add(c)

    # Step 1: Try 「XのY」pattern
    x_no_y = extract_x_no_y_pattern(query)
    if x_no_y:
        x_part, y_part = x_no_y

        # X is usually the container/location, prioritize it
        add_candidate(x_part)

        # Y might be the actual object or a description
        # Only add if it's reasonably short
        if len(y_part) <= MAX_QUERY_LENGTH:
            add_candidate(y_part)

        # Also try recursively on Y (for 「Xの〜の〜」)
        nested = extract_x_no_y_pattern(y_part)
        if nested:
            add_candidate(nested[0])

    # Step 2: Try action particle extraction
    action_objs = extract_action_object(query)
    for obj in action_objs:
        add_candidate(obj)

    # Step 3: Add normalized original if short enough
    normalized = normalize_query(query)
    if len(normalized) <= MAX_QUERY_LENGTH:
        add_candidate(normalized)

    # Step 4: Try variant normalization
    for c in list(candidates):
        variant = normalize_variant(c)
        if variant != c:
            add_candidate(variant)

    return candidates


def expand_with_priority(
    query: str,
    world_objects: set[str],
) -> list[tuple[str, str]]:
    """Expand query and return with priority labels.

    Args:
        query: Original query
        world_objects: Valid world objects

    Returns:
        List of (candidate, source) tuples
    """
    results = []
    seen = set()

    def add(c: str, source: str) -> None:
        c = normalize_query(c)
        if c and c not in seen and c in world_objects:
            results.append((c, source))
            seen.add(c)

    # Try patterns in priority order
    x_no_y = extract_x_no_y_pattern(query)
    if x_no_y:
        add(x_no_y[0], "x_no_y:x")
        if len(x_no_y[1]) <= MAX_QUERY_LENGTH:
            add(x_no_y[1], "x_no_y:y")

    action_objs = extract_action_object(query)
    for obj in action_objs:
        add(obj, "action_particle")

    normalized = normalize_query(query)
    if len(normalized) <= MAX_QUERY_LENGTH:
        add(normalized, "normalized")

    return results
