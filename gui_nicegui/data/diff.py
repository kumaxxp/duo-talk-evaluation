"""Text diff generation for repair comparison.

Generates simple diffs showing before/after format repair.
"""

from typing import TypedDict


class RepairDiff(TypedDict):
    """Result of comparing raw and repaired text."""

    has_changes: bool
    removed: str
    added: str
    raw: str
    repaired: str


def generate_repair_diff(raw: str, repaired: str | None) -> RepairDiff:
    """Generate a simple diff showing repair changes.

    Args:
        raw: Original raw output
        repaired: Repaired output (None if no repair was done)

    Returns:
        RepairDiff with change information
    """
    if repaired is None or raw == repaired:
        return RepairDiff(
            has_changes=False,
            removed="",
            added="",
            raw=raw,
            repaired=repaired or raw,
        )

    # Find what was removed (in raw but not in repaired)
    # Simple approach: show the difference in length
    removed_parts = []
    added_parts = []

    raw_lines = raw.split("\n")
    repaired_lines = repaired.split("\n")

    # Find lines in raw but not in repaired
    repaired_set = set(repaired_lines)
    for line in raw_lines:
        if line and line not in repaired_set:
            removed_parts.append(line)

    # Find lines in repaired but not in raw
    raw_set = set(raw_lines)
    for line in repaired_lines:
        if line and line not in raw_set:
            added_parts.append(line)

    return RepairDiff(
        has_changes=True,
        removed="\n".join(removed_parts),
        added="\n".join(added_parts),
        raw=raw,
        repaired=repaired,
    )


class SpeechDiff(TypedDict):
    """Result of comparing raw_speech and final_speech."""

    has_changes: bool
    removed: str
    added: str
    raw: str
    final: str


def generate_speech_diff(raw_speech: str, final_speech: str) -> SpeechDiff:
    """Generate diff between raw_speech and final_speech.

    Args:
        raw_speech: Original speech from LLM
        final_speech: Final speech after corrections

    Returns:
        SpeechDiff with change information
    """
    if raw_speech == final_speech:
        return SpeechDiff(
            has_changes=False,
            removed="",
            added="",
            raw=raw_speech,
            final=final_speech,
        )

    # Simple word-based diff
    raw_words = set(raw_speech.split())
    final_words = set(final_speech.split())
    removed = raw_words - final_words
    added = final_words - raw_words

    return SpeechDiff(
        has_changes=True,
        removed=" ".join(sorted(removed)) if removed else "",
        added=" ".join(sorted(added)) if added else "",
        raw=raw_speech,
        final=final_speech,
    )


class InlineDiff(TypedDict):
    """Inline diff result."""

    removed: list[str]
    added: list[str]
    unchanged: list[str]


def generate_inline_diff(old: str, new: str) -> InlineDiff:
    """Generate inline diff with markers.

    Args:
        old: Original text
        new: New text

    Returns:
        InlineDiff with removed/added/unchanged parts
    """
    old_words = old.split()
    new_words = new.split()

    old_set = set(old_words)
    new_set = set(new_words)

    removed = [w for w in old_words if w not in new_set]
    added = [w for w in new_words if w not in old_set]
    unchanged = [w for w in old_words if w in new_set]

    return InlineDiff(
        removed=removed,
        added=added,
        unchanged=unchanged,
    )
