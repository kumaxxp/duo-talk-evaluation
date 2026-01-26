"""Tests for GUI components (P-Next1/PR3)."""

import pytest


class TestTimelineComponent:
    """Tests for timeline component."""

    def test_turns_to_timeline_items_basic(self):
        """Should convert raw turns to timeline items."""
        from gui_nicegui.components.timeline import turns_to_timeline_items

        raw_turns = [
            {"turn_number": 1, "speaker": "やな", "retry_steps": 0},
            {"turn_number": 2, "speaker": "あゆ", "retry_steps": 1},
            {"turn_number": 3, "speaker": "やな", "give_up": True},
        ]

        items = turns_to_timeline_items(raw_turns)

        assert len(items) == 3
        assert items[0].turn_number == 1
        assert items[0].speaker == "やな"
        assert items[0].has_issue is False

        assert items[1].turn_number == 2
        assert items[1].has_issue is True
        assert items[1].issue_type == "retry"

        assert items[2].turn_number == 3
        assert items[2].has_issue is True
        assert items[2].issue_type == "give_up"

    def test_turns_to_timeline_items_format_break(self):
        """Should detect format break issues."""
        from gui_nicegui.components.timeline import turns_to_timeline_items

        raw_turns = [
            {"turn_number": 1, "speaker": "やな", "format_break_triggered": True},
        ]

        items = turns_to_timeline_items(raw_turns)

        assert items[0].has_issue is True
        assert items[0].issue_type == "format_break"

    def test_turns_to_timeline_items_empty(self):
        """Should handle empty turn list."""
        from gui_nicegui.components.timeline import turns_to_timeline_items

        items = turns_to_timeline_items([])

        assert items == []

    def test_get_item_color_normal(self):
        """Should return green for normal turns."""
        from gui_nicegui.components.timeline import get_item_color, TimelineItem

        item = TimelineItem(turn_number=1, speaker="やな", has_issue=False)
        color = get_item_color(item)

        assert "green" in color

    def test_get_item_color_give_up(self):
        """Should return red for give_up."""
        from gui_nicegui.components.timeline import get_item_color, TimelineItem

        item = TimelineItem(
            turn_number=1, speaker="やな", has_issue=True, issue_type="give_up"
        )
        color = get_item_color(item)

        assert "red" in color

    def test_get_speaker_icon(self):
        """Should return correct icons for speakers."""
        from gui_nicegui.components.timeline import get_speaker_icon

        assert get_speaker_icon("やな") == "👧"
        assert get_speaker_icon("あゆ") == "👩"
        assert get_speaker_icon("unknown") == "👤"


class TestDiffViewerComponent:
    """Tests for diff viewer component."""

    def test_create_change_summary_basic(self):
        """Should create change summary correctly."""
        from gui_nicegui.components.diff_viewer import create_change_summary

        old_text = "Hello world foo bar"
        new_text = "Hello world baz qux"

        summary = create_change_summary(old_text, new_text)

        assert summary["removed_count"] == 2  # foo, bar
        assert summary["added_count"] == 2  # baz, qux
        assert summary["unchanged_count"] == 2  # Hello, world

    def test_create_change_summary_no_changes(self):
        """Should handle identical texts."""
        from gui_nicegui.components.diff_viewer import create_change_summary

        text = "Hello world"
        summary = create_change_summary(text, text)

        assert summary["removed_count"] == 0
        assert summary["added_count"] == 0

    def test_create_change_summary_complete_change(self):
        """Should handle complete text change."""
        from gui_nicegui.components.diff_viewer import create_change_summary

        old_text = "foo bar"
        new_text = "baz qux"

        summary = create_change_summary(old_text, new_text)

        assert summary["removed_count"] == 2
        assert summary["added_count"] == 2
        assert summary["unchanged_count"] == 0


class TestTimelineItemDataclass:
    """Tests for TimelineItem dataclass."""

    def test_timeline_item_defaults(self):
        """Should have correct default values."""
        from gui_nicegui.components.timeline import TimelineItem

        item = TimelineItem(turn_number=1, speaker="やな")

        assert item.turn_number == 1
        assert item.speaker == "やな"
        assert item.has_issue is False
        assert item.issue_type == ""
        assert item.is_selected is False

    def test_timeline_item_with_issue(self):
        """Should store issue information."""
        from gui_nicegui.components.timeline import TimelineItem

        item = TimelineItem(
            turn_number=5,
            speaker="あゆ",
            has_issue=True,
            issue_type="give_up",
            is_selected=True,
        )

        assert item.turn_number == 5
        assert item.has_issue is True
        assert item.issue_type == "give_up"
        assert item.is_selected is True
