"""Turn view model for GUI display.

Converts raw turn data to view model for fast triage.
"""

import re
from typing import TypedDict


class FormatBreakInfo(TypedDict, total=False):
    """Format break information."""

    triggered: bool
    type: str
    method: str
    steps: int
    error: str | None


class IssueSummary(TypedDict, total=False):
    """Issue summary for badge display."""

    error_code: str  # MISSING_OBJECT, EMPTY_THOUGHT, etc.
    blocked_target: str | None  # Target that was blocked (if any)
    badge_text: str  # Human-readable badge text


class TurnViewModel(TypedDict, total=False):
    """View model for a single turn."""

    turn: int
    speaker: str
    thought: str
    speech: str

    # Raw data for diff display
    raw_output: str
    repaired_output: str | None
    raw_speech: str
    final_speech: str

    # Status flags
    has_retry: bool
    has_format_break: bool
    has_give_up: bool

    # Format break details
    format_break_type: str
    format_break: FormatBreakInfo

    # Guidance
    guidance_cards: list[str]

    # Issue summary (for fast triage badges)
    issue_summary: IssueSummary | None


def extract_issue_summary(raw_turn: dict) -> IssueSummary | None:
    """Extract issue summary from turn for badge display.

    Parses guidance_cards and format_break info to create a human-readable
    issue summary badge.

    Args:
        raw_turn: Raw turn dictionary

    Returns:
        IssueSummary or None if no issues
    """
    # Check for GIVE_UP (highest priority)
    if raw_turn.get("give_up"):
        # Parse guidance card for error code and target
        guidance_cards = raw_turn.get("guidance_cards", [])
        for card in guidance_cards:
            # Extract [ERROR_CODE] from guidance card
            error_match = re.search(r"\[ERROR_CODE\]\s*(\w+)", card)
            target_match = re.search(r"\[BLOCKED_TARGET\]\s*(.+?)(?:\n|$)", card)

            if error_match:
                error_code = error_match.group(1)
                blocked_target = target_match.group(1).strip() if target_match else None

                # Truncate long targets
                if blocked_target and len(blocked_target) > 20:
                    blocked_target = blocked_target[:17] + "..."

                badge_text = f"{error_code}: {blocked_target}" if blocked_target else error_code
                return IssueSummary(
                    error_code=error_code,
                    blocked_target=blocked_target,
                    badge_text=badge_text,
                )

        # Fallback for GIVE_UP without parseable guidance
        return IssueSummary(
            error_code="GIVE_UP",
            blocked_target=None,
            badge_text="GIVE_UP",
        )

    # Check for format break
    if raw_turn.get("format_break_triggered"):
        fb_type = raw_turn.get("format_break_type", "FORMAT_ERROR")
        return IssueSummary(
            error_code=fb_type,
            blocked_target=None,
            badge_text=fb_type,
        )

    # Check for retry (but not give_up)
    if raw_turn.get("retry_steps", 0) > 0:
        # Parse guidance card for retry reason
        guidance_cards = raw_turn.get("guidance_cards", [])
        for card in guidance_cards:
            error_match = re.search(r"\[ERROR_CODE\]\s*(\w+)", card)
            if error_match:
                error_code = error_match.group(1)
                return IssueSummary(
                    error_code=error_code,
                    blocked_target=None,
                    badge_text=f"RETRY:{error_code}",
                )

        return IssueSummary(
            error_code="RETRY",
            blocked_target=None,
            badge_text="RETRY",
        )

    return None


def to_view_model(raw_turn: dict) -> TurnViewModel:
    """Convert raw turn data to view model.

    Args:
        raw_turn: Raw turn dictionary from turns_log.json

    Returns:
        TurnViewModel for GUI display
    """
    # Extract format break info
    format_break = FormatBreakInfo(
        triggered=raw_turn.get("format_break_triggered", False),
        type=raw_turn.get("format_break_type", "NONE"),
        method=raw_turn.get("repair_method", "NONE"),
        steps=raw_turn.get("repair_steps", 0),
        error=raw_turn.get("parser_error"),
    )

    # Extract issue summary for fast triage badges
    issue_summary = extract_issue_summary(raw_turn)

    return TurnViewModel(
        turn=raw_turn.get("turn_number", 0),
        speaker=raw_turn.get("speaker", ""),
        thought=raw_turn.get("parsed_thought", ""),
        speech=raw_turn.get("parsed_speech", ""),
        # Raw data
        raw_output=raw_turn.get("raw_output", ""),
        repaired_output=raw_turn.get("repaired_output"),
        raw_speech=raw_turn.get("raw_speech", ""),
        final_speech=raw_turn.get("final_speech", ""),
        # Status flags
        has_retry=raw_turn.get("retry_steps", 0) > 0,
        has_format_break=raw_turn.get("format_break_triggered", False),
        has_give_up=raw_turn.get("give_up", False),
        # Format break details
        format_break_type=raw_turn.get("format_break_type", "NONE"),
        format_break=format_break,
        # Guidance
        guidance_cards=raw_turn.get("guidance_cards", []),
        # Issue summary
        issue_summary=issue_summary,
    )


def to_view_models(raw_turns: list[dict]) -> list[TurnViewModel]:
    """Convert list of raw turns to view models.

    Args:
        raw_turns: List of raw turn dictionaries

    Returns:
        List of TurnViewModel
    """
    return [to_view_model(turn) for turn in raw_turns]


# =============================================================================
# Issue Priority (Phase F)
# =============================================================================

# Priority levels: lower number = higher priority
PRIORITY_CRASH = 0
PRIORITY_SCHEMA = 1
PRIORITY_FORMAT_BREAK = 2
PRIORITY_GIVE_UP = 3
PRIORITY_RETRY = 4
PRIORITY_NORMAL = 99


def get_issue_priority(turn: dict) -> int:
    """Get priority level for a turn's issues.

    Priority order (highest to lowest):
    0: Crash
    1: Schema break
    2: FormatBreak
    3: GiveUp
    4: Retry only
    99: Normal (no issues)

    Args:
        turn: Raw turn dictionary

    Returns:
        Priority level (lower = more severe)
    """
    # Crash is highest priority
    error_type = turn.get("error_type", "")
    if error_type == "CRASH":
        return PRIORITY_CRASH

    # Schema break
    if error_type == "SCHEMA_BREAK":
        return PRIORITY_SCHEMA

    # FormatBreak
    if turn.get("format_break_triggered"):
        return PRIORITY_FORMAT_BREAK

    # GiveUp
    if turn.get("give_up"):
        return PRIORITY_GIVE_UP

    # Retry only
    if turn.get("retry_steps", 0) > 0:
        return PRIORITY_RETRY

    # Normal turn (no issues)
    return PRIORITY_NORMAL


def sort_by_issue_priority(turns: list[dict]) -> list[dict]:
    """Sort turns by issue priority (most severe first).

    Only includes turns with issues (priority < 99).

    Args:
        turns: List of raw turn dictionaries

    Returns:
        Sorted list of turns with issues
    """
    issue_turns = [t for t in turns if get_issue_priority(t) < PRIORITY_NORMAL]
    return sorted(issue_turns, key=get_issue_priority)
