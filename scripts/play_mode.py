"""Interactive CLI Play Mode for scenario exploration.

Allows step-by-step exploration of scenarios from the command line.
Usage: python scripts/play_mode.py <scenario_id>
       make play s=<scenario_id>
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict

# Default save path for state files
DEFAULT_STATE_PATH = Path("artifacts/scn_mystery_mansion_v1_state.json")


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
    unlocked_doors: list[str]  # Doors that have been unlocked


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
        unlocked_doors=[],
    )


# =============================================================================
# Display Formatting
# =============================================================================


def format_world_state(state: PlayState) -> str:
    """Format world state for CLI display.

    Shows exit-door mapping for locked doors (BUG-004 fix).

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

    # Get locked exits info for door mapping display (BUG-004)
    locations = state["scenario_data"].get("locations", {})
    current_loc_data = locations.get(state["current_location"], {})
    locked_exits = current_loc_data.get("locked_exits", {})

    for exit_loc in state["available_exits"]:
        # Check if this exit has a locked door
        if exit_loc in locked_exits:
            lock_info = locked_exits[exit_loc]
            door_name = lock_info.get("door_name", exit_loc)
            is_unlocked = door_name in state.get("unlocked_doors", [])
            lock_icon = "🔓" if is_unlocked else "🔒"
            lines.append(f"  - {exit_loc} (via {door_name} {lock_icon})")
        else:
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
# Save/Load Functions
# =============================================================================


def save_play_state(state: PlayState, path: Path | None = None) -> Path:
    """Save play state to JSON file.

    Args:
        state: Current play state
        path: Optional path to save to (default: artifacts/scn_mystery_mansion_v1_state.json)

    Returns:
        Path where state was saved
    """
    if path is None:
        path = DEFAULT_STATE_PATH

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create saveable data (exclude non-serializable scenario_data reference)
    save_data = {
        "schema_version": "1.0.0",
        "saved_at": datetime.now().isoformat(),
        "scenario_name": state["scenario_name"],
        "current_location": state["current_location"],
        "holding": state["holding"],
        "unlocked_doors": state["unlocked_doors"],
        "scenario_data": state["scenario_data"],  # Include full scenario state
    }

    # Serialize to canonical JSON (sorted keys for reproducibility)
    content = json.dumps(save_data, ensure_ascii=False, indent=2, sort_keys=True)
    if not content.endswith("\n"):
        content += "\n"

    # Write state file
    path.write_text(content, encoding="utf-8")

    # Write hash file for hakoniwa CLI compatibility
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    hash_path = Path(str(path) + ".sha256")
    hash_path.write_text(content_hash, encoding="utf-8")

    return path


def load_play_state(path: Path) -> PlayState:
    """Load play state from JSON file.

    Args:
        path: Path to load from

    Returns:
        PlayState restored from file

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"State file not found: {path}")

    save_data = json.loads(path.read_text(encoding="utf-8"))

    # Reconstruct PlayState
    scenario_data = save_data["scenario_data"]
    locations = scenario_data.get("locations", {})
    current_location = save_data["current_location"]
    current_loc_data = locations.get(current_location, {})

    return PlayState(
        scenario_name=save_data["scenario_name"],
        current_location=current_location,
        available_objects=current_loc_data.get("props", []),
        available_exits=current_loc_data.get("exits", []),
        character_positions={
            name: data.get("location", "不明")
            for name, data in scenario_data.get("characters", {}).items()
        },
        holding=save_data["holding"],
        scenario_data=scenario_data,
        unlocked_doors=save_data["unlocked_doors"],
    )


# =============================================================================
# Command Parsing
# =============================================================================


# Command aliases for quick reference
COMMAND_ALIASES: dict[str, list[str]] = {
    "look": ["look", "l", "見る", "look around"],
    "move": ["move", "go", "g", "移動", "行く"],
    "take": ["take", "get", "t", "取る", "拾う"],
    "open": ["open", "o", "開ける", "開く"],
    "search": ["search", "inspect", "x", "examine", "調べる", "探す"],
    "use": ["use", "unlock", "使う", "解錠"],
    "where": ["where", "w", "どこ", "現在地"],
    "inventory": ["inventory", "inv", "i", "持ち物", "所持品"],
    "map": ["map", "m", "地図", "マップ"],
    "help": ["help", "h", "?", "ヘルプ"],
    "quit": ["quit", "exit", "q", "終了"],
    "status": ["status", "st", "状態", "ステータス"],
    "save": ["save", "セーブ", "保存"],
    "load": ["load", "ロード", "読み込み"],
}

# Direction aliases for movement (location-specific)
# Maps direction -> exit name by current location
DIRECTION_ALIASES: dict[str, dict[str, str]] = {
    "start_hall": {
        "north": "locked_study",
        "n": "locked_study",
    },
    "locked_study": {
        "up": "goal_attic",
        "u": "goal_attic",
        "south": "start_hall",
        "s": "start_hall",
    },
    "goal_attic": {
        "down": "locked_study",
        "d": "locked_study",
    },
}


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

    # Normalize commands using alias dictionary
    for cmd, aliases in COMMAND_ALIASES.items():
        if action in aliases:
            # Commands that don't use targets
            if cmd in ("where", "inventory", "map", "help", "quit", "status"):
                return ParsedCommand(action=cmd, target=None)
            # save/load use optional path
            if cmd in ("save", "load"):
                return ParsedCommand(action=cmd, target=target)
            return ParsedCommand(action=cmd, target=target)

    return ParsedCommand(action="unknown", target=user_input)


def _find_similar_objects(query: str, candidates: list[str], threshold: float = 0.5) -> list[str]:
    """Find similar objects using basic fuzzy matching.

    P2: BUG-006 - Semantic Matcher verification path.
    Uses simple substring/prefix matching and difflib for suggestions.

    Args:
        query: The search query
        candidates: List of available object names
        threshold: Similarity threshold (0.0-1.0)

    Returns:
        List of similar object names (deduplicated)
    """
    import difflib

    suggestions = []

    # First, check for substring matches
    query_lower = query.lower()
    for candidate in candidates:
        if query_lower in candidate.lower() or candidate.lower() in query_lower:
            suggestions.append(candidate)

    # If no substring matches, use difflib
    if not suggestions:
        close_matches = difflib.get_close_matches(
            query, candidates, n=2, cutoff=threshold
        )
        suggestions.extend(close_matches)

    # Deduplicate while preserving order
    seen = set()
    unique_suggestions = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            unique_suggestions.append(s)

    return unique_suggestions[:2]  # Return max 2 suggestions


def suggest_command(user_input: str) -> str | None:
    """Suggest a similar command for typos or unknown input.

    Args:
        user_input: The unknown user input

    Returns:
        Suggestion message or None if no good match
    """
    if not user_input:
        return None

    action = user_input.split()[0].lower()

    # Common typos and suggestions
    suggestions: dict[str, str] = {
        "lok": "look",
        "loo": "look",
        "mve": "move",
        "mov": "move",
        "tke": "take",
        "tak": "take",
        "opn": "open",
        "serch": "search",
        "srch": "search",
        "wher": "where",
        "invent": "inventory",
        "invetory": "inventory",
        "mp": "map",
        "hlp": "help",
        "hep": "help",
        "ext": "quit",
        "exi": "quit",
    }

    if action in suggestions:
        return f"もしかして: {suggestions[action]}"

    # Check if it starts like a known command
    for cmd, aliases in COMMAND_ALIASES.items():
        for alias in aliases:
            if len(action) >= 2 and alias.startswith(action):
                return f"もしかして: {alias}"

    return None


def get_help_text() -> str:
    """Get help text with available commands.

    Returns:
        Help text string
    """
    return """
📖 コマンド一覧

【探索】
  look (l)              現在地の情報を表示
  move <場所> (go, g)   指定した場所に移動 ※方角も可 (north, up等)
  search [対象] (x)     対象を調べる / 隠されたものを探す
  map (m)               全体マップを表示

【アイテム】
  take <物> (get, t)    物を拾う
  open <容器> (o)       容器を開けて中身を見る
  use <鍵> <ドア>       鍵を使って施錠を解除 ※出口名でもOK
  inventory (inv, i)    所持品一覧

【情報】
  where (w)             現在地とキャラクター位置
  status (st)           キャラクター状態を表示
  help (h, ?)           このヘルプを表示

【セーブ/ロード】
  save [path]           状態を保存 (デフォルト: artifacts/*.json)
  load [path]           状態を読み込み

【システム】
  quit (q)              終了

【使用例】
  t iron_key            iron_key を拾う (t = take)
  o coat_rack           coat_rack を開ける (o = open)
  x coat_rack           coat_rack を調べる (x = search)
  g north               北へ移動 (g = go)
  go up                 上へ移動 (階段など)
  use iron_key locked_study   鍵で出口を解錠
  save                  状態をセーブ
  load                  セーブデータをロード

💡 ヒント: 括弧内は省略形です (例: l=look, t=take, o=open, x=search)
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

    elif cmd["action"] == "save":
        # P0: BUG-001 Save/Load blocker fix
        path = Path(cmd["target"]) if cmd["target"] else None
        try:
            saved_path = save_play_state(state, path)
            return f"💾 セーブ完了: {saved_path.absolute()}", state
        except Exception as e:
            return f"❌ セーブ失敗: {e}", state

    elif cmd["action"] == "load":
        # P0: BUG-001 Save/Load blocker fix
        path = Path(cmd["target"]) if cmd["target"] else DEFAULT_STATE_PATH
        try:
            new_state = load_play_state(path)
            return f"📂 ロード完了: {path}\n\n{format_world_state(new_state)}", new_state
        except FileNotFoundError:
            return f"❌ ファイルが見つかりません: {path}", state
        except Exception as e:
            return f"❌ ロード失敗: {e}", state

    elif cmd["action"] == "move":
        target = cmd["target"]
        if not target:
            return "移動先を指定してください (例: move リビング)", state

        # P1: BUG-005 - Resolve direction aliases (up, north, etc.)
        current_loc = state["current_location"]
        if current_loc in DIRECTION_ALIASES:
            target = DIRECTION_ALIASES[current_loc].get(target.lower(), target)

        if target not in state["available_exits"]:
            available = ", ".join(state["available_exits"])
            # Show direction hints if available
            if current_loc in DIRECTION_ALIASES:
                directions = list(DIRECTION_ALIASES[current_loc].keys())
                return f"'{cmd['target']}' には移動できません。移動可能: {available} (方角: {', '.join(directions)})", state
            return f"'{target}' には移動できません。移動可能: {available}", state

        # Check for locked exits (Preflight check)
        locations = state["scenario_data"].get("locations", {})
        current_loc_data = locations.get(state["current_location"], {})
        locked_exits = current_loc_data.get("locked_exits", {})

        if target in locked_exits:
            lock_info = locked_exits[target]
            door_name = lock_info.get("door_name", target)

            # Check if door is still locked
            if lock_info.get("locked", False) and door_name not in state["unlocked_doors"]:
                # Preflight: Locked door - give hints, not hard deny
                hint = lock_info.get("hint_on_locked", "施錠されています。")
                suggestions = lock_info.get("suggestions", ["look around"])
                suggestions_str = " / ".join(suggestions)

                return (
                    f"[PREFLIGHT] 🔒 {door_name} は施錠されています。{hint}\n"
                    f"💡 次の行動候補: {suggestions_str}"
                ), state

        # Update location
        new_loc_data = locations.get(target, {})

        new_state = PlayState(
            scenario_name=state["scenario_name"],
            current_location=target,
            available_objects=new_loc_data.get("props", []),
            available_exits=new_loc_data.get("exits", []),
            character_positions=state["character_positions"],
            holding=state["holding"],
            scenario_data=state["scenario_data"],
            unlocked_doors=state["unlocked_doors"],
        )

        # Check for goal
        is_goal = new_loc_data.get("is_goal", False)
        result = f"📍 {target} に移動しました\n\n{format_world_state(new_state)}"

        if is_goal:
            result += "\n\n🎉 [CLEAR] ゴールに到達しました！クリアおめでとうございます！"

        return result, new_state

    elif cmd["action"] == "take":
        target = cmd["target"]
        if not target:
            return "取る物を指定してください (例: take コーヒーメーカー)", state

        # P1: BUG-002 - Check if already in inventory
        if target in state["holding"]:
            return f"🎒 '{target}' は既に持っています", state

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
            unlocked_doors=state["unlocked_doors"],
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
            unlocked_doors=state["unlocked_doors"],
        )

        contents_str = ", ".join(contents)
        return f"📦 {target} を開けました。中には: {contents_str}", new_state

    elif cmd["action"] == "search":
        target = cmd["target"]

        # Get current location data
        locations = state["scenario_data"].get("locations", {})
        current_loc_data = locations.get(state["current_location"], {})
        hidden_objects = current_loc_data.get("hidden_objects", [])
        containers = current_loc_data.get("containers", {})

        # P1: BUG-003 - If target is a container, suggest open command
        if target and target in containers:
            contents_hint = "何かが入っているようです" if containers[target] else "空のようです"
            return (
                f"🔍 {target} を調べました。{contents_hint}\n"
                f"💡 ヒント: 'open {target}' で中身を確認できます"
            ), state

        # P2: BUG-006 - If target doesn't exist, try semantic matcher suggestions
        if target:
            all_objects = state["available_objects"] + list(containers.keys())
            if target not in all_objects:
                # Try to find similar objects using basic fuzzy matching
                suggestions = _find_similar_objects(target, all_objects)
                if suggestions:
                    suggestion_str = ", ".join(suggestions)
                    return (
                        f"🔍 '{target}' はここにありません。\n"
                        f"💡 もしかして: {suggestion_str}"
                    ), state
                return f"🔍 '{target}' はここにありません。利用可能: {', '.join(all_objects)}", state

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
            unlocked_doors=state["unlocked_doors"],
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

    elif cmd["action"] == "use":
        target = cmd["target"]
        if not target:
            return "使用するアイテムとドアを指定してください (例: use iron_key north_door)", state

        # Parse "key door" format
        parts = target.split()
        if len(parts) < 2:
            return "使用するアイテムとドアを指定してください (例: use iron_key north_door)", state

        key_item = parts[0]
        door_or_exit = parts[1]

        # Check if player has the key
        if key_item not in state["holding"]:
            return f"🎒 '{key_item}' を持っていません。(所持品: {', '.join(state['holding']) or 'なし'})", state

        # Find locked exit that matches the door
        locations = state["scenario_data"].get("locations", {})
        current_loc_data = locations.get(state["current_location"], {})
        locked_exits = current_loc_data.get("locked_exits", {})

        # P1: BUG-004 - Accept both exit_name and door_name
        # First try to match by door_name
        target_exit = None
        lock_info = None
        door_name = None

        for exit_name, info in locked_exits.items():
            if info.get("door_name") == door_or_exit:
                target_exit = exit_name
                lock_info = info
                door_name = door_or_exit
                break

        # If no match by door_name, try by exit_name
        if not lock_info and door_or_exit in locked_exits:
            target_exit = door_or_exit
            lock_info = locked_exits[door_or_exit]
            door_name = lock_info.get("door_name", door_or_exit)

        if not lock_info:
            # Show available doors with their exit mappings
            available_doors = []
            for exit_name, info in locked_exits.items():
                d_name = info.get("door_name", exit_name)
                available_doors.append(f"{d_name} ({exit_name})")
            if available_doors:
                return f"🚪 '{door_or_exit}' という施錠されたドアは見当たりません。\n💡 利用可能: {', '.join(available_doors)}", state
            return f"🚪 '{door_or_exit}' という施錠されたドアは見当たりません", state

        # Check if key matches
        required_key = lock_info.get("required_key")
        if key_item != required_key:
            return f"🔑 '{key_item}' では '{door_name}' を開けられません", state

        # Unlock the door
        new_unlocked = [*state["unlocked_doors"], door_name]

        new_state = PlayState(
            scenario_name=state["scenario_name"],
            current_location=state["current_location"],
            available_objects=state["available_objects"],
            available_exits=state["available_exits"],
            character_positions=state["character_positions"],
            holding=state["holding"],
            scenario_data=state["scenario_data"],
            unlocked_doors=new_unlocked,
        )

        return f"🔓 {key_item} で {door_name} を解錠しました！{target_exit} への道が開けました", new_state

    elif cmd["action"] == "quit":
        return "終了します。", state

    else:
        msg = f"❓ 不明なコマンド: {cmd.get('target', '')}"
        suggestion = suggest_command(cmd.get("target", ""))
        if suggestion:
            msg += f"\n💡 {suggestion}"
        msg += "\n📖 'help' でコマンド一覧を表示"
        return msg, state


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
    print("─" * 40)
    print("💡 クイックコマンド: l=見る g=移動 t=取る o=開ける x=調べる")
    print("   h=ヘルプ m=マップ i=所持品 save/load=セーブ q=終了")
    print("─" * 40)
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
