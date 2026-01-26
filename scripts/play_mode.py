"""Interactive CLI Play Mode for scenario exploration.

Allows step-by-step exploration of scenarios from the command line.
Usage: python scripts/play_mode.py <scenario_id>
       make play s=<scenario_id>
"""

import json
import sys
from pathlib import Path
from typing import TypedDict


# =============================================================================
# Type Definitions
# =============================================================================


class PlayState(TypedDict):
    """Current state for play mode."""

    scenario_name: str
    current_location: str
    available_objects: list[str]
    available_exits: list[str]
    character_positions: dict[str, str]
    holding: list[str]
    scenario_data: dict


class ParsedCommand(TypedDict):
    """Parsed command from user input."""

    action: str
    target: str | None


# =============================================================================
# Scenario Loading
# =============================================================================


def load_scenario_for_play(scenario_path: Path) -> PlayState:
    """Load scenario and prepare initial play state.

    Args:
        scenario_path: Path to scenario JSON file

    Returns:
        PlayState with initial world state

    Raises:
        FileNotFoundError: If scenario file doesn't exist
    """
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_path}")

    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))

    # Extract character positions
    characters = scenario.get("characters", {})
    character_positions = {
        name: data.get("location", "不明")
        for name, data in characters.items()
    }

    # Get やな's starting location (primary viewpoint)
    yana_location = character_positions.get("やな", "")
    if not yana_location:
        # Fallback to first character's location
        yana_location = next(iter(character_positions.values()), "")

    # Get available objects and exits at starting location
    locations = scenario.get("locations", {})
    current_loc_data = locations.get(yana_location, {})

    return PlayState(
        scenario_name=scenario.get("name", "unnamed"),
        current_location=yana_location,
        available_objects=current_loc_data.get("props", []),
        available_exits=current_loc_data.get("exits", []),
        character_positions=character_positions,
        holding=[],
        scenario_data=scenario,
    )


# =============================================================================
# Display Formatting
# =============================================================================


def format_world_state(state: PlayState) -> str:
    """Format world state for CLI display.

    Args:
        state: Current play state

    Returns:
        Formatted string for display
    """
    lines = [
        f"=== {state['scenario_name']} ===",
        f"",
        f"📍 現在地: {state['current_location']}",
        f"",
        f"🎒 所持品: {', '.join(state['holding']) or '(なし)'}",
        f"",
        f"📦 オブジェクト:",
    ]

    for obj in state["available_objects"]:
        lines.append(f"  - {obj}")

    if not state["available_objects"]:
        lines.append("  (なし)")

    lines.append(f"")
    lines.append(f"🚪 出口:")

    for exit_loc in state["available_exits"]:
        lines.append(f"  - {exit_loc}")

    if not state["available_exits"]:
        lines.append("  (なし)")

    return "\n".join(lines)


def format_character_status(positions: dict[str, str]) -> str:
    """Format character positions for display.

    Args:
        positions: Character name -> location mapping

    Returns:
        Formatted string
    """
    lines = ["👥 キャラクター:"]

    for name, location in positions.items():
        lines.append(f"  - {name}: {location}")

    return "\n".join(lines)


# =============================================================================
# Command Parsing
# =============================================================================


def parse_command(user_input: str) -> ParsedCommand:
    """Parse user input into command.

    Args:
        user_input: Raw user input string

    Returns:
        ParsedCommand with action and target
    """
    parts = user_input.strip().split(maxsplit=1)

    if not parts:
        return ParsedCommand(action="unknown", target=None)

    action = parts[0].lower()
    target = parts[1] if len(parts) > 1 else None

    # Normalize commands
    if action in ("look", "l", "見る"):
        return ParsedCommand(action="look", target=target)
    elif action in ("move", "go", "移動"):
        return ParsedCommand(action="move", target=target)
    elif action in ("take", "get", "取る"):
        return ParsedCommand(action="take", target=target)
    elif action in ("open", "開ける"):
        return ParsedCommand(action="open", target=target)
    elif action in ("search", "inspect", "調べる"):
        return ParsedCommand(action="search", target=target)
    elif action in ("where", "w", "どこ"):
        return ParsedCommand(action="where", target=None)
    elif action in ("inventory", "inv", "i", "持ち物"):
        return ParsedCommand(action="inventory", target=None)
    elif action in ("map", "m", "地図"):
        return ParsedCommand(action="map", target=None)
    elif action in ("help", "h", "?"):
        return ParsedCommand(action="help", target=None)
    elif action in ("quit", "exit", "q"):
        return ParsedCommand(action="quit", target=None)
    elif action in ("status", "st", "状態"):
        return ParsedCommand(action="status", target=None)
    else:
        return ParsedCommand(action="unknown", target=user_input)


def get_help_text() -> str:
    """Get help text with available commands.

    Returns:
        Help text string
    """
    return """
📖 コマンド一覧:
  look, l           - 現在地の情報を表示
  move <場所>       - 指定した場所に移動
  take <物>         - 物を拾う
  open <容器>       - 容器を開けて中身を見る
  search [対象]     - 隠されたものを探す
  where, w          - 現在地とキャラクター位置
  inventory, inv, i - 所持品一覧
  map, m            - 全体マップを表示
  status, st        - キャラクター状態を表示
  help, h           - このヘルプを表示
  quit, q           - 終了
"""


# =============================================================================
# Command Execution
# =============================================================================


def execute_command(cmd: ParsedCommand, state: PlayState) -> tuple[str, PlayState]:
    """Execute a parsed command and return result.

    Args:
        cmd: Parsed command
        state: Current play state

    Returns:
        Tuple of (output message, updated state)
    """
    if cmd["action"] == "look":
        return format_world_state(state), state

    elif cmd["action"] == "status":
        return format_character_status(state["character_positions"]), state

    elif cmd["action"] == "help":
        return get_help_text(), state

    elif cmd["action"] == "move":
        target = cmd["target"]
        if not target:
            return "移動先を指定してください (例: move リビング)", state

        if target not in state["available_exits"]:
            available = ", ".join(state["available_exits"])
            return f"'{target}' には移動できません。移動可能: {available}", state

        # Update location
        locations = state["scenario_data"].get("locations", {})
        new_loc_data = locations.get(target, {})

        new_state = PlayState(
            scenario_name=state["scenario_name"],
            current_location=target,
            available_objects=new_loc_data.get("props", []),
            available_exits=new_loc_data.get("exits", []),
            character_positions=state["character_positions"],
            holding=state["holding"],
            scenario_data=state["scenario_data"],
        )

        return f"📍 {target} に移動しました\n\n{format_world_state(new_state)}", new_state

    elif cmd["action"] == "take":
        target = cmd["target"]
        if not target:
            return "取る物を指定してください (例: take コーヒーメーカー)", state

        if target not in state["available_objects"]:
            available = ", ".join(state["available_objects"])
            return f"'{target}' はここにありません。利用可能: {available}", state

        # Pick up object
        new_objects = [obj for obj in state["available_objects"] if obj != target]
        new_holding = [*state["holding"], target]

        new_state = PlayState(
            scenario_name=state["scenario_name"],
            current_location=state["current_location"],
            available_objects=new_objects,
            available_exits=state["available_exits"],
            character_positions=state["character_positions"],
            holding=new_holding,
            scenario_data=state["scenario_data"],
        )

        return f"🎒 {target} を拾いました", new_state

    elif cmd["action"] == "open":
        target = cmd["target"]
        if not target:
            return "開ける対象を指定してください (例: open 引き出し)", state

        # Get current location data
        locations = state["scenario_data"].get("locations", {})
        current_loc_data = locations.get(state["current_location"], {})
        containers = current_loc_data.get("containers", {})

        # Check if target is a valid container
        if target not in containers:
            # Check if it exists as an object but not a container
            if target in state["available_objects"]:
                return f"'{target}' は開けられません（コンテナではありません）", state
            # List available containers
            available_containers = list(containers.keys())
            if available_containers:
                return f"'{target}' は開けられません。開けられる容器: {', '.join(available_containers)}", state
            return f"'{target}' は開けられません。この場所に開けられる容器はありません", state

        # Open container and reveal contents
        contents = containers[target]
        new_objects = [*state["available_objects"], *contents]

        new_state = PlayState(
            scenario_name=state["scenario_name"],
            current_location=state["current_location"],
            available_objects=new_objects,
            available_exits=state["available_exits"],
            character_positions=state["character_positions"],
            holding=state["holding"],
            scenario_data=state["scenario_data"],
        )

        contents_str = ", ".join(contents)
        return f"📦 {target} を開けました。中には: {contents_str}", new_state

    elif cmd["action"] == "search":
        target = cmd["target"]

        # Get current location data
        locations = state["scenario_data"].get("locations", {})
        current_loc_data = locations.get(state["current_location"], {})
        hidden_objects = current_loc_data.get("hidden_objects", [])

        if not hidden_objects:
            if target:
                return f"🔍 {target} を調べましたが、何も見つかりませんでした", state
            return f"🔍 {state['current_location']} を調べましたが、何も見つかりませんでした", state

        # Reveal hidden objects
        new_objects = [*state["available_objects"], *hidden_objects]

        # Remove hidden objects from scenario data to prevent re-discovery
        new_scenario_data = state["scenario_data"].copy()
        new_locations = new_scenario_data.get("locations", {}).copy()
        new_loc_data = new_locations.get(state["current_location"], {}).copy()
        new_loc_data["hidden_objects"] = []
        new_locations[state["current_location"]] = new_loc_data
        new_scenario_data["locations"] = new_locations

        new_state = PlayState(
            scenario_name=state["scenario_name"],
            current_location=state["current_location"],
            available_objects=new_objects,
            available_exits=state["available_exits"],
            character_positions=state["character_positions"],
            holding=state["holding"],
            scenario_data=new_scenario_data,
        )

        found_str = ", ".join(hidden_objects)
        if target:
            return f"🔍 {target} を調べると、{found_str} を発見しました！", new_state
        return f"🔍 {state['current_location']} を調べると、{found_str} を発見しました！", new_state

    elif cmd["action"] == "where":
        lines = [
            f"📍 現在地: {state['current_location']}",
            "",
            "👥 キャラクター位置:",
        ]
        for name, location in state["character_positions"].items():
            marker = " ← あなた" if location == state["current_location"] else ""
            lines.append(f"  - {name}: {location}{marker}")
        return "\n".join(lines), state

    elif cmd["action"] == "inventory":
        if not state["holding"]:
            return "🎒 所持品: 何も持っていません", state
        items_str = ", ".join(state["holding"])
        return f"🎒 所持品 ({len(state['holding'])}個): {items_str}", state

    elif cmd["action"] == "map":
        locations = state["scenario_data"].get("locations", {})
        if not locations:
            return "🗺️ マップ情報がありません", state

        lines = ["🗺️ マップ:"]
        for loc_name, loc_data in locations.items():
            marker = "📍" if loc_name == state["current_location"] else "  "
            exits = loc_data.get("exits", [])
            exits_str = ", ".join(exits) if exits else "(行き止まり)"
            lines.append(f"{marker} {loc_name} → {exits_str}")
        return "\n".join(lines), state

    elif cmd["action"] == "quit":
        return "終了します。", state

    else:
        return f"不明なコマンド: {cmd.get('target', '')}。'help' でコマンド一覧を表示", state


# =============================================================================
# Main REPL
# =============================================================================


def run_play_mode(scenario_path: Path):
    """Run interactive play mode.

    Args:
        scenario_path: Path to scenario JSON file
    """
    try:
        state = load_scenario_for_play(scenario_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"\n🎮 Play Mode: {state['scenario_name']}")
    print("'help' でコマンド一覧、'quit' で終了")
    print()
    print(format_world_state(state))
    print()

    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break

        if not user_input:
            continue

        cmd = parse_command(user_input)

        if cmd["action"] == "quit":
            print("終了します。")
            break

        output, state = execute_command(cmd, state)
        print(output)
        print()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Interactive scenario play mode")
    parser.add_argument(
        "scenario_id",
        help="Scenario ID (e.g., coffee_trap) or path to JSON file",
    )
    parser.add_argument(
        "--scenarios-dir",
        default="experiments/scenarios",
        help="Directory containing scenario files",
    )

    args = parser.parse_args()

    # Resolve scenario path
    if args.scenario_id.endswith(".json"):
        scenario_path = Path(args.scenario_id)
    else:
        scenario_path = Path(args.scenarios_dir) / f"{args.scenario_id}.json"

    run_play_mode(scenario_path)


if __name__ == "__main__":
    main()
