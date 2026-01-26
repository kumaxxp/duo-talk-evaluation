"""Timeline component for turn visualization.

Displays turn progression as a horizontal timeline with issue indicators.
"""

from dataclasses import dataclass
from typing import Callable

from nicegui import ui


@dataclass
class TimelineItem:
    """Single item in the timeline."""

    turn_number: int
    speaker: str
    has_issue: bool = False
    issue_type: str = ""  # "retry", "format_break", "give_up"
    is_selected: bool = False


def get_item_color(item: TimelineItem) -> str:
    """Get background color for timeline item based on issue type."""
    if item.issue_type == "give_up":
        return "bg-red-500"
    elif item.issue_type == "format_break":
        return "bg-orange-500"
    elif item.issue_type == "retry":
        return "bg-yellow-500"
    elif item.has_issue:
        return "bg-amber-400"
    return "bg-green-500"


def get_speaker_icon(speaker: str) -> str:
    """Get icon/emoji for speaker."""
    if speaker == "やな":
        return "👧"
    elif speaker == "あゆ":
        return "👩"
    return "👤"


def create_timeline(
    items: list[TimelineItem],
    on_select: Callable[[int], None] | None = None,
    selected_index: int = -1,
) -> ui.element:
    """Create a horizontal timeline showing turn progression.

    Args:
        items: List of TimelineItem to display
        on_select: Callback when item is clicked (receives turn index)
        selected_index: Currently selected item index

    Returns:
        NiceGUI element containing the timeline
    """
    with ui.card().classes("w-full p-2") as timeline_card:
        ui.label("Timeline").classes("text-sm font-bold mb-2")

        # Legend
        with ui.row().classes("gap-2 mb-2 text-xs"):
            ui.html('<span class="inline-block w-3 h-3 bg-green-500 rounded-full"></span>', sanitize=False)
            ui.label("OK")
            ui.html('<span class="inline-block w-3 h-3 bg-yellow-500 rounded-full"></span>', sanitize=False)
            ui.label("Retry")
            ui.html('<span class="inline-block w-3 h-3 bg-orange-500 rounded-full"></span>', sanitize=False)
            ui.label("Format")
            ui.html('<span class="inline-block w-3 h-3 bg-red-500 rounded-full"></span>', sanitize=False)
            ui.label("GiveUp")

        # Timeline container with horizontal scroll
        with ui.scroll_area().classes("w-full").style("max-height: 80px"):
            with ui.row().classes("gap-1 items-center flex-nowrap"):
                for i, item in enumerate(items):
                    color = get_item_color(item)
                    speaker_icon = get_speaker_icon(item.speaker)

                    # Highlight selected
                    border_class = "ring-2 ring-blue-600" if i == selected_index else ""

                    # Create clickable turn indicator
                    with ui.element("div").classes(
                        f"flex flex-col items-center cursor-pointer {border_class}"
                    ).on("click", lambda _, idx=i: on_select(idx) if on_select else None):

                        # Turn circle with color
                        ui.element("div").classes(
                            f"w-6 h-6 rounded-full {color} flex items-center justify-center text-xs text-white font-bold"
                        ).style("min-width: 24px").props(f'title="T{item.turn_number}"')

                        # Speaker icon below
                        ui.label(speaker_icon).classes("text-xs")

                        # Turn number
                        ui.label(f"T{item.turn_number}").classes("text-xs text-gray-500")

                    # Connector line (except for last item)
                    if i < len(items) - 1:
                        connector_color = "bg-gray-300"
                        if item.has_issue:
                            connector_color = "bg-orange-200"
                        ui.element("div").classes(f"w-4 h-0.5 {connector_color}").style(
                            "margin-top: -20px"
                        )

    return timeline_card


def create_mini_timeline(
    items: list[TimelineItem],
    max_display: int = 20,
) -> ui.element:
    """Create a compact mini timeline for overview.

    Args:
        items: List of TimelineItem
        max_display: Maximum items to display

    Returns:
        NiceGUI element
    """
    display_items = items[:max_display]
    has_more = len(items) > max_display

    with ui.row().classes("gap-0.5 items-center") as row:
        for item in display_items:
            color = get_item_color(item)
            ui.element("div").classes(f"w-2 h-4 {color} rounded-sm").props(
                f'title="T{item.turn_number}: {item.speaker}"'
            )

        if has_more:
            ui.label(f"+{len(items) - max_display}").classes("text-xs text-gray-500 ml-1")

    return row


def turns_to_timeline_items(raw_turns: list[dict]) -> list[TimelineItem]:
    """Convert raw turns to TimelineItems.

    Args:
        raw_turns: List of raw turn dictionaries

    Returns:
        List of TimelineItem
    """
    items = []
    for turn in raw_turns:
        has_retry = turn.get("retry_steps", 0) > 0
        has_format_break = turn.get("format_break_triggered", False)
        has_give_up = turn.get("give_up", False)

        issue_type = ""
        if has_give_up:
            issue_type = "give_up"
        elif has_format_break:
            issue_type = "format_break"
        elif has_retry:
            issue_type = "retry"

        items.append(
            TimelineItem(
                turn_number=turn.get("turn_number", 0),
                speaker=turn.get("speaker", ""),
                has_issue=has_retry or has_format_break or has_give_up,
                issue_type=issue_type,
            )
        )

    return items
