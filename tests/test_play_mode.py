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

    def test_help_includes_use(self):
        """Help should include use command (P-Next1)."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        assert "use" in help_text


class TestShortAliases:
    """Tests for short command aliases (P-Next1/PR2)."""

    def test_parse_g_as_move(self):
        """'g' should be alias for move."""
        from scripts.play_mode import parse_command

        cmd = parse_command("g リビング")
        assert cmd["action"] == "move"
        assert cmd["target"] == "リビング"

    def test_parse_t_as_take(self):
        """'t' should be alias for take."""
        from scripts.play_mode import parse_command

        cmd = parse_command("t コーヒー豆")
        assert cmd["action"] == "take"
        assert cmd["target"] == "コーヒー豆"

    def test_parse_o_as_open(self):
        """'o' should be alias for open."""
        from scripts.play_mode import parse_command

        cmd = parse_command("o 引き出し")
        assert cmd["action"] == "open"
        assert cmd["target"] == "引き出し"

    def test_parse_x_as_search(self):
        """'x' should be alias for search (examine)."""
        from scripts.play_mode import parse_command

        cmd = parse_command("x 本棚")
        assert cmd["action"] == "search"
        assert cmd["target"] == "本棚"

    def test_parse_examine_as_search(self):
        """'examine' should be alias for search."""
        from scripts.play_mode import parse_command

        cmd = parse_command("examine 壁")
        assert cmd["action"] == "search"
        assert cmd["target"] == "壁"


class TestSuggestCommand:
    """Tests for command suggestion on typos (P-Next1/PR2)."""

    def test_suggest_for_common_typo(self):
        """Should suggest correct command for common typos."""
        from scripts.play_mode import suggest_command

        result_lok = suggest_command("lok")
        result_mov = suggest_command("mov")
        result_tke = suggest_command("tke")

        assert result_lok is not None and "look" in result_lok
        assert result_mov is not None and "move" in result_mov
        assert result_tke is not None and "take" in result_tke

    def test_suggest_for_partial_match(self):
        """Should suggest command for partial input."""
        from scripts.play_mode import suggest_command

        # Should match commands starting with partial input
        result = suggest_command("hel")
        assert result is not None
        assert "help" in result

    def test_no_suggestion_for_valid_command(self):
        """Should return None for unrecognized input without close match."""
        from scripts.play_mode import suggest_command

        result = suggest_command("xyzabc")
        assert result is None

    def test_unknown_command_shows_suggestion(self):
        """Unknown command should show suggestion in output."""
        from scripts.play_mode import execute_command, PlayState, ParsedCommand

        state = PlayState(
            scenario_name="test",
            current_location="キッチン",
            available_objects=[],
            available_exits=[],
            character_positions={},
            holding=[],
            scenario_data={},
            unlocked_doors=[],
        )

        cmd = ParsedCommand(action="unknown", target="lok")
        output, _ = execute_command(cmd, state)

        assert "不明なコマンド" in output
        assert "help" in output


class TestImprovedHelp:
    """Tests for improved help formatting (P-Next1/PR2)."""

    def test_help_has_categories(self):
        """Help should have category headers."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        assert "探索" in help_text
        assert "アイテム" in help_text
        assert "情報" in help_text
        assert "システム" in help_text

    def test_help_shows_aliases(self):
        """Help should show command aliases."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        # Check that short aliases are shown
        assert "(l)" in help_text  # look alias
        assert "(g)" in help_text or "go, g" in help_text  # move alias
        assert "(t)" in help_text or "get, t" in help_text  # take alias

    def test_help_has_examples(self):
        """Help should include usage examples."""
        from scripts.play_mode import get_help_text

        help_text = get_help_text()

        assert "使用例" in help_text
        assert "move リビング" in help_text or "リビング" in help_text


class TestCommandAliasesDictionary:
    """Tests for COMMAND_ALIASES dictionary (P-Next1/PR2)."""

    def test_command_aliases_exists(self):
        """COMMAND_ALIASES dictionary should exist."""
        from scripts.play_mode import COMMAND_ALIASES

        assert isinstance(COMMAND_ALIASES, dict)
        assert "look" in COMMAND_ALIASES
        assert "move" in COMMAND_ALIASES

    def test_all_commands_have_aliases(self):
        """All main commands should have aliases defined."""
        from scripts.play_mode import COMMAND_ALIASES

        expected_commands = [
            "look", "move", "take", "open", "search", "use",
            "where", "inventory", "map", "help", "quit", "status"
        ]
        for cmd in expected_commands:
            assert cmd in COMMAND_ALIASES, f"Missing alias for: {cmd}"

    def test_japanese_aliases_included(self):
        """Japanese aliases should be included."""
        from scripts.play_mode import COMMAND_ALIASES

        # Check some Japanese aliases exist
        all_aliases = []
        for aliases in COMMAND_ALIASES.values():
            all_aliases.extend(aliases)

        assert "見る" in all_aliases
        assert "移動" in all_aliases
        assert "取る" in all_aliases


class TestUseCommand:
    """Tests for 'use <key> <door>' command (P-Next1)."""

    def test_parse_use_command(self):
        """Should parse 'use' command with key and door."""
        from scripts.play_mode import parse_command

        cmd = parse_command("use iron_key north_door")

        assert cmd["action"] == "use"
        assert cmd["target"] == "iron_key north_door"

    def test_parse_use_command_aliases(self):
        """Should parse 'unlock' and '解錠' as use aliases."""
        from scripts.play_mode import parse_command

        assert parse_command("unlock iron_key door")["action"] == "use"
        assert parse_command("使う iron_key door")["action"] == "use"
        assert parse_command("解錠 iron_key door")["action"] == "use"

    def test_use_unlocks_door_with_correct_key(self):
        """Should unlock door when correct key is used."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="start_hall",
            available_objects=["coat_rack", "mirror"],
            available_exits=["locked_study"],
            character_positions={"やな": "start_hall"},
            holding=["iron_key"],
            scenario_data={
                "locations": {
                    "start_hall": {
                        "props": ["coat_rack", "mirror"],
                        "exits": ["locked_study"],
                        "locked_exits": {
                            "locked_study": {
                                "door_name": "north_door",
                                "required_key": "iron_key",
                                "locked": True,
                            }
                        },
                    },
                    "locked_study": {"props": [], "exits": ["start_hall"]},
                }
            },
            unlocked_doors=[],
        )

        cmd = {"action": "use", "target": "iron_key north_door"}
        output, new_state = execute_command(cmd, state)

        assert "解錠" in output or "unlock" in output.lower()
        assert "north_door" in new_state["unlocked_doors"]

    def test_use_fails_without_key_in_inventory(self):
        """Should fail when player doesn't have the key."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="start_hall",
            available_objects=["coat_rack"],
            available_exits=["locked_study"],
            character_positions={"やな": "start_hall"},
            holding=[],  # No key
            scenario_data={
                "locations": {
                    "start_hall": {
                        "props": ["coat_rack"],
                        "exits": ["locked_study"],
                        "locked_exits": {
                            "locked_study": {
                                "door_name": "north_door",
                                "required_key": "iron_key",
                                "locked": True,
                            }
                        },
                    }
                }
            },
            unlocked_doors=[],
        )

        cmd = {"action": "use", "target": "iron_key north_door"}
        output, new_state = execute_command(cmd, state)

        assert "持っていません" in output or "don't have" in output.lower()
        assert "north_door" not in new_state["unlocked_doors"]

    def test_use_fails_with_wrong_key(self):
        """Should fail when wrong key is used."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="start_hall",
            available_objects=["coat_rack"],
            available_exits=["locked_study"],
            character_positions={"やな": "start_hall"},
            holding=["old_locket"],  # Wrong item
            scenario_data={
                "locations": {
                    "start_hall": {
                        "props": ["coat_rack"],
                        "exits": ["locked_study"],
                        "locked_exits": {
                            "locked_study": {
                                "door_name": "north_door",
                                "required_key": "iron_key",
                                "locked": True,
                            }
                        },
                    }
                }
            },
            unlocked_doors=[],
        )

        cmd = {"action": "use", "target": "old_locket north_door"}
        output, new_state = execute_command(cmd, state)

        assert "開けられません" in output or "doesn't work" in output.lower()
        assert "north_door" not in new_state["unlocked_doors"]


class TestLockedDoorPreflight:
    """Tests for locked door preflight check (P-Next1)."""

    def test_move_to_locked_exit_shows_preflight(self):
        """Should show preflight message when moving to locked exit."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="start_hall",
            available_objects=["coat_rack"],
            available_exits=["locked_study"],
            character_positions={"やな": "start_hall"},
            holding=[],
            scenario_data={
                "locations": {
                    "start_hall": {
                        "props": ["coat_rack"],
                        "exits": ["locked_study"],
                        "locked_exits": {
                            "locked_study": {
                                "door_name": "north_door",
                                "required_key": "iron_key",
                                "locked": True,
                            }
                        },
                    },
                    "locked_study": {"props": [], "exits": ["start_hall"]},
                }
            },
            unlocked_doors=[],
        )

        cmd = {"action": "move", "target": "locked_study"}
        output, new_state = execute_command(cmd, state)

        assert "PREFLIGHT" in output or "🔒" in output
        assert "施錠" in output or "locked" in output.lower()
        # Should not move
        assert new_state["current_location"] == "start_hall"

    def test_move_to_unlocked_exit_succeeds(self):
        """Should allow movement after door is unlocked."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="start_hall",
            available_objects=["coat_rack"],
            available_exits=["locked_study"],
            character_positions={"やな": "start_hall"},
            holding=["iron_key"],
            scenario_data={
                "locations": {
                    "start_hall": {
                        "props": ["coat_rack"],
                        "exits": ["locked_study"],
                        "locked_exits": {
                            "locked_study": {
                                "door_name": "north_door",
                                "required_key": "iron_key",
                                "locked": True,
                            }
                        },
                    },
                    "locked_study": {"props": ["bookshelf"], "exits": ["start_hall"]},
                }
            },
            unlocked_doors=["north_door"],  # Already unlocked
        )

        cmd = {"action": "move", "target": "locked_study"}
        output, new_state = execute_command(cmd, state)

        assert new_state["current_location"] == "locked_study"
        assert "PREFLIGHT" not in output


class TestGoalDetection:
    """Tests for goal detection on move (P-Next1)."""

    def test_move_to_goal_shows_clear_message(self):
        """Should show CLEAR message when reaching goal."""
        from scripts.play_mode import execute_command, PlayState

        state = PlayState(
            scenario_name="test",
            current_location="locked_study",
            available_objects=[],
            available_exits=["goal_attic"],
            character_positions={"やな": "locked_study"},
            holding=[],
            scenario_data={
                "locations": {
                    "locked_study": {"props": [], "exits": ["goal_attic"]},
                    "goal_attic": {"props": ["treasure"], "exits": ["locked_study"], "is_goal": True},
                }
            },
            unlocked_doors=[],
        )

        cmd = {"action": "move", "target": "goal_attic"}
        output, new_state = execute_command(cmd, state)

        assert new_state["current_location"] == "goal_attic"
        assert "CLEAR" in output or "クリア" in output or "🎉" in output
