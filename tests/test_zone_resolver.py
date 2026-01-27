"""Tests for zone_resolver module."""

import pytest

from hakoniwa.ui.zone_resolver import resolve_zone, icon_for, label_for


# --- resolve_zone tests ---


class TestResolveZone:
    """Test resolve_zone(obj) -> int."""

    def test_ui_zone_takes_priority(self):
        """ui_zone 指定が最優先で効く."""
        obj = {"name": "Magic Table", "type": "furniture", "ui_zone": "North"}
        assert resolve_zone(obj) == 1

    def test_door_in_name_maps_to_south(self):
        """'Door' を含む name → South(7)."""
        obj = {"name": "Iron Door", "type": "exit"}
        assert resolve_zone(obj) == 7

    def test_shelf_in_name_maps_to_north(self):
        """'Shelf' を含む name → North(1)."""
        obj = {"name": "Old Bookshelf"}
        assert resolve_zone(obj) == 1

    def test_fallback_to_center(self):
        """それ以外 → Center(4)."""
        obj = {"name": "Golden Key", "type": "item"}
        assert resolve_zone(obj) == 4

    def test_ui_zone_overrides_name_inference(self):
        """ui_zone は名前推論より優先."""
        obj = {"name": "Front Door", "ui_zone": "East"}
        assert resolve_zone(obj) == 5

    def test_all_zone_strings(self):
        """全 zone 文字列が正しくマッピングされる."""
        zone_map = {
            "North": 1, "West": 3, "Center": 4, "East": 5, "South": 7,
        }
        for zone_str, expected_idx in zone_map.items():
            obj = {"name": "x", "ui_zone": zone_str}
            assert resolve_zone(obj) == expected_idx, f"Failed for {zone_str}"

    def test_empty_object_returns_center(self):
        """空 dict でも落ちない → Center."""
        assert resolve_zone({}) == 4

    def test_name_none_returns_center(self):
        """name が None でも落ちない."""
        assert resolve_zone({"name": None}) == 4

    def test_bookcase_maps_to_north(self):
        """'Bookcase' を含む → North(1)."""
        obj = {"name": "Dusty Bookcase"}
        assert resolve_zone(obj) == 1

    def test_case_insensitive_name_inference(self):
        """名前推論は大文字小文字を区別しない."""
        obj = {"name": "wooden door"}
        assert resolve_zone(obj) == 7


# --- icon_for tests ---


class TestIconFor:
    """Test icon_for(obj) -> str."""

    def test_key_type(self):
        obj = {"name": "Iron Key", "type": "key"}
        assert icon_for(obj) == "🗝️"

    def test_door_type(self):
        obj = {"name": "Front Door", "type": "door"}
        assert icon_for(obj) == "🚪"

    def test_unknown_fallback(self):
        obj = {"name": "Mystery Object"}
        assert icon_for(obj) == "❓"

    def test_character_type(self):
        obj = {"name": "やな", "type": "character"}
        assert icon_for(obj) == "👤"

    def test_name_based_door(self):
        """type がなくても name に Door があればアイコンを返す."""
        obj = {"name": "Locked Door"}
        assert icon_for(obj) == "🚪"


# --- label_for tests ---


class TestLabelFor:
    """Test label_for(obj) -> str."""

    def test_returns_name(self):
        obj = {"name": "Iron Key"}
        assert label_for(obj) == "Iron Key"

    def test_missing_name_returns_unknown(self):
        obj = {"type": "item"}
        assert label_for(obj) == "???"

    def test_empty_dict(self):
        assert label_for({}) == "???"
