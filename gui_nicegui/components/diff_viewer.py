"""Diff viewer component with inline highlighting.

Provides visual diff display with color-coded changes.
"""

from nicegui import ui


def create_diff_viewer(
    old_text: str,
    new_text: str,
    title: str = "Diff",
    max_length: int = 500,
) -> ui.element:
    """Create a visual diff viewer with inline highlighting.

    Args:
        old_text: Original text
        new_text: New/modified text
        title: Title for the diff section
        max_length: Maximum text length to display

    Returns:
        NiceGUI element containing the diff
    """
    # Truncate if needed
    old_display = old_text[:max_length] + ("..." if len(old_text) > max_length else "")
    new_display = new_text[:max_length] + ("..." if len(new_text) > max_length else "")

    with ui.card().classes("w-full") as card:
        ui.label(title).classes("text-sm font-bold mb-2")

        if old_text == new_text:
            ui.label("No changes").classes("text-gray-500 text-sm italic")
            return card

        # Side-by-side view
        with ui.row().classes("w-full gap-2"):
            # Old (removed)
            with ui.card().classes("flex-1 bg-red-50 border-l-4 border-red-400"):
                ui.label("Before").classes("text-xs font-bold text-red-700")
                with ui.scroll_area().classes("max-h-32"):
                    ui.code(old_display).classes("text-xs whitespace-pre-wrap")

            # New (added)
            with ui.card().classes("flex-1 bg-green-50 border-l-4 border-green-400"):
                ui.label("After").classes("text-xs font-bold text-green-700")
                with ui.scroll_area().classes("max-h-32"):
                    ui.code(new_display).classes("text-xs whitespace-pre-wrap")

    return card


def create_inline_diff(
    old_text: str,
    new_text: str,
    title: str = "",
) -> ui.element:
    """Create inline diff with word-level highlighting.

    Args:
        old_text: Original text
        new_text: New text
        title: Optional title

    Returns:
        NiceGUI element
    """
    with ui.element("div").classes("w-full") as container:
        if title:
            ui.label(title).classes("text-xs font-bold mb-1")

        # Split into words for comparison
        old_words = old_text.split()
        new_words = new_text.split()

        old_set = set(old_words)
        new_set = set(new_words)

        # Build highlighted HTML
        html_parts = []

        # Show removed words
        removed = [w for w in old_words if w not in new_set]
        if removed:
            for word in removed[:10]:  # Limit display
                html_parts.append(
                    f'<span class="bg-red-200 text-red-800 px-1 rounded line-through">{word}</span>'
                )
            if len(removed) > 10:
                html_parts.append(f'<span class="text-gray-500">...+{len(removed) - 10}</span>')

        # Show added words
        added = [w for w in new_words if w not in old_set]
        if added:
            if html_parts:
                html_parts.append('<span class="mx-2">→</span>')
            for word in added[:10]:
                html_parts.append(
                    f'<span class="bg-green-200 text-green-800 px-1 rounded">{word}</span>'
                )
            if len(added) > 10:
                html_parts.append(f'<span class="text-gray-500">...+{len(added) - 10}</span>')

        if html_parts:
            ui.html(" ".join(html_parts), sanitize=False).classes("text-sm")
        else:
            ui.label("Structural changes only").classes("text-xs text-gray-500")

    return container


def create_change_summary(
    old_text: str,
    new_text: str,
) -> dict:
    """Create a summary of changes between two texts.

    Args:
        old_text: Original text
        new_text: New text

    Returns:
        Dictionary with change statistics
    """
    old_words = set(old_text.split())
    new_words = set(new_text.split())

    removed = old_words - new_words
    added = new_words - old_words
    unchanged = old_words & new_words

    return {
        "removed_count": len(removed),
        "added_count": len(added),
        "unchanged_count": len(unchanged),
        "change_ratio": len(removed) + len(added) / max(len(old_words), 1),
        "removed_words": list(removed)[:5],
        "added_words": list(added)[:5],
    }


def create_change_badge(summary: dict) -> ui.element:
    """Create a compact change badge from summary.

    Args:
        summary: Change summary from create_change_summary

    Returns:
        NiceGUI badge element
    """
    removed = summary["removed_count"]
    added = summary["added_count"]

    with ui.row().classes("gap-1") as row:
        if removed > 0:
            ui.badge(f"-{removed}").props("color=red outline").classes("text-xs")
        if added > 0:
            ui.badge(f"+{added}").props("color=green outline").classes("text-xs")

    return row
