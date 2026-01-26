"""Tests for Interactive CLI Play Mode (TDD).

Play mode allows step-by-step exploration of scenarios.
- Displays world state
- Shows character positions
- Simulates GM step requests
"""

import json
import pytest
from pathlib import Path


class TestPlayModeLoader:
    """Tests for loading scenarios in play mode."""

    def test_load_scenario_for_play(self, tmp_path):
        """Should load scenario and prepare initial state."""
        from scripts.play_mode import load_scenario_for_play

        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()

        scenario_data = {
            "name": "test_scenario",
            "description": "Test description",
            "locations": {
                "キッチン": {"props": ["コーヒーメーカー", "マグカップ"], "exits": ["リビング"]},
                "リビング": {"props": ["ソファ"], "exits": ["キッチン"]},
            },
            "characters": {
                "やな": {"location": "キッチン", "holding": []},
                "あゆ": {"location": "キッチン", "holding": []},
            },
        }
        (scenarios_dir / "test_scenario.json").write_text(
            json.dumps(scenario_data, ensure_ascii=False)
        )

        state = load_scenario_for_play(scenarios_dir / "test_scenario.json")

        assert state["scenario_name"] == "test_scenario"
        assert state["current_location"] == "キッチン"  # やな's starting location
        assert "コーヒーメーカー" in state["available_objects"]
        assert "リビング" in state["available_exits"]

    def test_scenario_not_found_raises_error(self, tmp_path):
        """Should raise FileNotFoundError for missing scenario."""
        from scripts.play_mode import load_scenario_for_play

        with pytest.raises(FileNotFoundError):
            load_scenario_for_play(tmp_path / "nonexistent.json")


class TestPlayModeDisplay:
    """Tests for play mode display formatting."""

    def test_format_world_state(self):
        """Should format world state for CLI display."""
        from scripts.play_mode import format_world_state

        state = {
            "scenario_name": "coffee_trap",
            "current_location": "キッチン",
            "available_objects": ["コーヒーメーカー", "マグカップ"],
            "available_exits": ["リビング"],
            "character_positions": {"やな": "キッチン", "あゆ": "キッチン"},
            "holding": [],
        }

        output = format_world_state(state)

        assert "coffee_trap" in output
        assert "キッチン" in output
        assert "コーヒーメーカー" in output
        assert "リビング" in output

    def test_format_character_status(self):
        """Should format character positions."""
        from scripts.play_mode import format_character_status

        positions = {"やな": "キッチン", "あゆ": "リビング"}

        output = format_character_status(positions)

        assert "やな" in output
        assert "キッチン" in output
        assert "あゆ" in output
        assert "リビング" in output


class TestPlayModeCommands:
    """Tests for play mode command parsing."""

    def test_parse_look_command(self):
        """Should parse 'look' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("look")

        assert cmd["action"] == "look"
        assert cmd["target"] is None

    def test_parse_move_command(self):
        """Should parse 'move <location>' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("move リビング")

        assert cmd["action"] == "move"
        assert cmd["target"] == "リビング"

    def test_parse_take_command(self):
        """Should parse 'take <object>' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("take コーヒーメーカー")

        assert cmd["action"] == "take"
        assert cmd["target"] == "コーヒーメーカー"

    def test_parse_help_command(self):
        """Should parse 'help' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("help")

        assert cmd["action"] == "help"

    def test_parse_quit_command(self):
        """Should parse 'quit' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("quit")

        assert cmd["action"] == "quit"

    def test_parse_unknown_command(self):
        """Should handle unknown commands."""
        from scripts.play_mode import parse_command

        cmd = parse_command("unknown_action xyz")

        assert cmd["action"] == "unknown"


class TestPlayModeHelp:
    """Tests for play mode help text."""

    def test_get_help_text(self):
        """Should return help text with available commands."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        assert "look" in help_text
        assert "move" in help_text
        assert "take" in help_text
        assert "quit" in help_text


class TestOpenCommand:
    """Tests for 'open <container>' command (Phase F)."""

    def test_parse_open_command(self):
        """Should parse 'open' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("open 引き出し")

        assert cmd["action"] == "open"
        assert cmd["target"] == "引き出し"

    def test_open_container_shows_contents(self):
        """Should show container contents when opened."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="リビング",
            available_objects=["ソファ", "引き出し"],
            available_exits=["キッチン"],
            character_positions={"やな": "リビング"},
            holding=[],
            scenario_data={
                "locations": {
                    "リビング": {
                        "props": ["ソファ", "引き出し"],
                        "exits": ["キッチン"],
                        "containers": {"引き出し": ["鍵", "メモ"]},
                    }
                }
            },
            unlocked_doors=[],
        )

        cmd = {"action": "open", "target": "引き出し"}
        output, new_state = execute_command(cmd, state)

        assert "鍵" in output
        assert "メモ" in output
        # Container contents should be accessible for take
        assert "鍵" in new_state["available_objects"]
        assert "メモ" in new_state["available_objects"]

    def test_open_nonexistent_container_shows_available(self):
        """Should show available objects when container doesn't exist."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="リビング",
            available_objects=["ソファ", "引き出し"],
            available_exits=["キッチン"],
            character_positions={"やな": "リビング"},
            holding=[],
            scenario_data={
                "locations": {
                    "リビング": {
                        "props": ["ソファ", "引き出し"],
                        "exits": ["キッチン"],
                        "containers": {"引き出し": ["鍵"]},
                    }
                }
            },
        )

        cmd = {"action": "open", "target": "本棚"}
        output, _ = execute_command(cmd, state)

        assert "本棚" in output
        assert "開けられません" in output or "ありません" in output
        # Should show available containers
        assert "引き出し" in output

    def test_open_non_container_object(self):
        """Should fail gracefully when opening non-container object."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="リビング",
            available_objects=["ソファ", "引き出し"],
            available_exits=["キッチン"],
            character_positions={"やな": "リビング"},
            holding=[],
            scenario_data={
                "locations": {
                    "リビング": {
                        "props": ["ソファ", "引き出し"],
                        "exits": ["キッチン"],
                        "containers": {"引き出し": ["鍵"]},
                    }
                }
            },
        )

        cmd = {"action": "open", "target": "ソファ"}
        output, _ = execute_command(cmd, state)

        assert "ソファ" in output
        # Should indicate it's not a container
        assert "開けられません" in output or "コンテナではありません" in output


class TestSearchCommand:
    """Tests for 'search <target>' command (Phase F)."""

    def test_parse_search_command(self):
        """Should parse 'search' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("search ソファ")

        assert cmd["action"] == "search"
        assert cmd["target"] == "ソファ"

    def test_search_reveals_hidden_object(self):
        """Should reveal hidden objects when searching."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="リビング",
            available_objects=["ソファ"],
            available_exits=["キッチン"],
            character_positions={"やな": "リビング"},
            holding=[],
            scenario_data={
                "locations": {
                    "リビング": {
                        "props": ["ソファ"],
                        "exits": ["キッチン"],
                        "hidden_objects": ["ソファの下の鍵"],
                    }
                }
            },
            unlocked_doors=[],
        )

        cmd = {"action": "search", "target": "ソファ"}
        output, new_state = execute_command(cmd, state)

        assert "ソファの下の鍵" in output
        # Hidden object should now be available
        assert "ソファの下の鍵" in new_state["available_objects"]

    def test_search_nothing_found(self):
        """Should indicate when nothing is found."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="リビング",
            available_objects=["ソファ"],
            available_exits=["キッチン"],
            character_positions={"やな": "リビング"},
            holding=[],
            scenario_data={
                "locations": {
                    "リビング": {
                        "props": ["ソファ"],
                        "exits": ["キッチン"],
                    }
                }
            },
        )

        cmd = {"action": "search", "target": "ソファ"}
        output, _ = execute_command(cmd, state)

        assert "見つかりませんでした" in output or "何も見つかりません" in output

    def test_search_location_without_target(self):
        """Should search current location when no target specified."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="リビング",
            available_objects=["ソファ"],
            available_exits=["キッチン"],
            character_positions={"やな": "リビング"},
            holding=[],
            scenario_data={
                "locations": {
                    "リビング": {
                        "props": ["ソファ"],
                        "exits": ["キッチン"],
                        "hidden_objects": ["床下の宝箱"],
                    }
                }
            },
            unlocked_doors=[],
        )

        cmd = {"action": "search", "target": None}
        output, new_state = execute_command(cmd, state)

        assert "床下の宝箱" in output
        assert "床下の宝箱" in new_state["available_objects"]

    def test_help_includes_new_commands(self):
        """Should include open and search in help text."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        assert "open" in help_text
        assert "search" in help_text


class TestWhereCommand:
    """Tests for 'where' command (P-Next1)."""

    def test_parse_where_command(self):
        """Should parse 'where' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("where")

        assert cmd["action"] == "where"
        assert cmd["target"] is None

    def test_where_shows_current_location(self):
        """Should show current location and character positions."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="キッチン",
            available_objects=["コーヒーメーカー"],
            available_exits=["リビング"],
            character_positions={"やな": "キッチン", "あゆ": "リビング"},
            holding=[],
            scenario_data={},
        )

        cmd = {"action": "where", "target": None}
        output, _ = execute_command(cmd, state)

        assert "キッチン" in output
        assert "やな" in output
        assert "あゆ" in output
        assert "リビング" in output

    def test_where_command_alias_w(self):
        """Should parse 'w' as where alias."""
        from scripts.play_mode import parse_command

        cmd = parse_command("w")

        assert cmd["action"] == "where"


class TestInventoryCommand:
    """Tests for 'inventory' command (P-Next1)."""

    def test_parse_inventory_command(self):
        """Should parse 'inventory' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("inventory")

        assert cmd["action"] == "inventory"
        assert cmd["target"] is None

    def test_inventory_shows_held_items(self):
        """Should show all held items."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="キッチン",
            available_objects=[],
            available_exits=[],
            character_positions={"やな": "キッチン"},
            holding=["鍵", "コーヒーカップ", "メモ"],
            scenario_data={},
        )

        cmd = {"action": "inventory", "target": None}
        output, _ = execute_command(cmd, state)

        assert "鍵" in output
        assert "コーヒーカップ" in output
        assert "メモ" in output

    def test_inventory_empty_shows_message(self):
        """Should show message when inventory is empty."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="キッチン",
            available_objects=[],
            available_exits=[],
            character_positions={"やな": "キッチン"},
            holding=[],
            scenario_data={},
        )

        cmd = {"action": "inventory", "target": None}
        output, _ = execute_command(cmd, state)

        assert "なし" in output or "空" in output or "持っていません" in output

    def test_inventory_command_aliases(self):
        """Should parse 'i' and 'inv' as inventory aliases."""
        from scripts.play_mode import parse_command

        assert parse_command("i")["action"] == "inventory"
        assert parse_command("inv")["action"] == "inventory"
        assert parse_command("持ち物")["action"] == "inventory"


class TestMapCommand:
    """Tests for 'map' command (P-Next1)."""

    def test_parse_map_command(self):
        """Should parse 'map' command."""
        from scripts.play_mode import parse_command

        cmd = parse_command("map")

        assert cmd["action"] == "map"
        assert cmd["target"] is None

    def test_map_shows_all_locations(self):
        """Should show all locations and their connections."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="キッチン",
            available_objects=[],
            available_exits=["リビング"],
            character_positions={"やな": "キッチン"},
            holding=[],
            scenario_data={
                "locations": {
                    "キッチン": {"props": [], "exits": ["リビング", "玄関"]},
                    "リビング": {"props": [], "exits": ["キッチン"]},
                    "玄関": {"props": [], "exits": ["キッチン"]},
                }
            },
        )

        cmd = {"action": "map", "target": None}
        output, _ = execute_command(cmd, state)

        # All locations should appear
        assert "キッチン" in output
        assert "リビング" in output
        assert "玄関" in output
        # Current location should be marked
        assert "📍" in output or "★" in output or "*" in output

    def test_map_shows_connections(self):
        """Should show which locations connect to which."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="キッチン",
            available_objects=[],
            available_exits=["リビング"],
            character_positions={},
            holding=[],
            scenario_data={
                "locations": {
                    "キッチン": {"props": [], "exits": ["リビング"]},
                    "リビング": {"props": [], "exits": ["キッチン", "玄関"]},
                    "玄関": {"props": [], "exits": ["リビング"]},
                }
            },
        )

        cmd = {"action": "map", "target": None}
        output, _ = execute_command(cmd, state)

        # Should show connections (arrows or similar)
        assert "→" in output or "->" in output or "exits" in output.lower() or ":" in output

    def test_map_command_alias(self):
        """Should parse 'm' and '地図' as map aliases."""
        from scripts.play_mode import parse_command

        assert parse_command("m")["action"] == "map"
        assert parse_command("地図")["action"] == "map"


class TestHelpUpdatedForNewCommands:
    """Tests that help includes new commands."""

    def test_help_includes_where(self):
        """Help should include where command."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        assert "where" in help_text

    def test_help_includes_inventory(self):
        """Help should include inventory command."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        assert "inventory" in help_text or "inv" in help_text

    def test_help_includes_map(self):
        """Help should include map command."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        assert "map" in help_text
