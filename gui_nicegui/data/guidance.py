"""Guidance card parsing.

Extracts available lists from guidance cards.
"""

import re
from typing import TypedDict


class AvailableLists(TypedDict):
    """Available items extracted from guidance card."""

    objects_here: list[str]
    holding: list[str]
    exits: list[str]


def extract_available_from_card(card: str) -> AvailableLists:
    """Extract OBJECTS_HERE, HOLDING, EXITS from a guidance card.

    Args:
        card: Guidance card text

    Returns:
        AvailableLists with extracted items
    """
    result = AvailableLists(
        objects_here=[],
        holding=[],
        exits=[],
    )

    # Pattern: "OBJECTS_HERE: item1, item2, ..."
    objects_match = re.search(r"OBJECTS_HERE:\s*(.+?)(?:\n|$)", card)
    if objects_match:
        items_str = objects_match.group(1).strip()
        if items_str and items_str != "(none)":
            result["objects_here"] = [
                item.strip() for item in items_str.split(",") if item.strip()
            ]

    # Pattern: "HOLDING: item1, item2, ..."
    holding_match = re.search(r"HOLDING:\s*(.+?)(?:\n|$)", card)
    if holding_match:
        items_str = holding_match.group(1).strip()
        if items_str and items_str != "(none)":
            result["holding"] = [
                item.strip() for item in items_str.split(",") if item.strip()
            ]

    # Pattern: "EXITS: location1, location2, ..."
    exits_match = re.search(r"EXITS:\s*(.+?)(?:\n|$)", card)
    if exits_match:
        items_str = exits_match.group(1).strip()
        if items_str and items_str != "(none)":
            result["exits"] = [
                item.strip() for item in items_str.split(",") if item.strip()
            ]

    return result
