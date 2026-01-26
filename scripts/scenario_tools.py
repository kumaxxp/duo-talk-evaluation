"""Scenario tools for Phase C.

C1: Template generation
C2: Linter validation
C3: World summary generation
"""

import json
from pathlib import Path
from typing import TypedDict


# =============================================================================
# Type Definitions
# =============================================================================


class LocationTemplate(TypedDict, total=False):
    """Location structure in scenario.

    Extended fields for Phase C+ scenario ops:
    - containers: Objects that can contain other objects
    - hidden_objects: Objects not immediately visible (require search/interaction)
    """

    props: list[str]
    exits: list[str]
    containers: dict[str, list[str]]  # e.g., {"引き出し": ["鍵", "メモ"]}
    hidden_objects: list[str]  # e.g., ["隠し鍵", "秘密のメモ"]


class CharacterTemplate(TypedDict):
    """Character structure in scenario."""

    location: str
    holding: list[str]


class ScenarioTemplate(TypedDict, total=False):
    """Complete scenario template structure."""

    name: str
    description: str
    locations: dict[str, LocationTemplate]
    characters: dict[str, CharacterTemplate]
    time_of_day: str
    notes: str


class WorldSummary(TypedDict):
    """World summary structure for display."""

    name: str
    location_count: int
    prop_count: int
    character_positions: dict[str, str]
    exit_graph: dict[str, list[str]]


# =============================================================================
# C1: Template Generation
# =============================================================================


def generate_template(scenario_id: str) -> ScenarioTemplate:
    """Generate a new scenario template with default values.

    Args:
        scenario_id: Unique identifier for the scenario (e.g., "scn_001")

    Returns:
        ScenarioTemplate with default kitchen/living setup

    Note:
        Extended fields (containers, hidden_objects) are optional.
        - containers: {"引き出し": ["鍵", "メモ"]} - objects inside other objects
        - hidden_objects: ["隠し鍵"] - not visible until searched/revealed
    """
    return ScenarioTemplate(
        name=scenario_id,
        description="(シナリオの説明を入力)",
        locations={
            "キッチン": LocationTemplate(
                props=["コーヒーメーカー", "マグカップ", "冷蔵庫"],
                exits=["リビング"],
                containers={"引き出し": ["スプーン", "フォーク"]},
                hidden_objects=[],
            ),
            "リビング": LocationTemplate(
                props=["ソファ", "テレビ", "本棚"],
                exits=["キッチン"],
                containers={"本棚": ["古い写真", "日記帳"]},
                hidden_objects=["ソファの下の鍵"],
            ),
        },
        characters={
            "やな": CharacterTemplate(location="キッチン", holding=[]),
            "あゆ": CharacterTemplate(location="キッチン", holding=[]),
        },
        time_of_day="morning",
        notes="(シナリオの補足説明、期待される失敗パターンなど)\n"
        "containers: コンテナ内のオブジェクトはコンテナを開けると見える\n"
        "hidden_objects: 特定のアクションで発見可能な隠しオブジェクト",
    )


def write_template(template: ScenarioTemplate, output_path: Path) -> None:
    """Write scenario template to JSON file.

    Args:
        template: Scenario template to write
        output_path: Path to output JSON file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# =============================================================================
# C2: Linter Validation
# =============================================================================


class LintResult(TypedDict):
    """Result of linting a scenario."""

    errors: list[str]  # Fatal errors
    warnings: list[str]  # Non-fatal warnings


def lint_scenario(scenario: dict) -> list[str]:
    """Validate scenario for common errors.

    Args:
        scenario: Scenario dictionary to validate

    Returns:
        List of error messages (empty if valid)
        Note: For detailed results including warnings, use lint_scenario_detailed()
    """
    result = lint_scenario_detailed(scenario)
    # For backwards compatibility, return errors + warnings as a single list
    return result["errors"] + [f"[warning] {w}" for w in result["warnings"]]


def lint_scenario_detailed(scenario: dict) -> LintResult:
    """Validate scenario with detailed error/warning separation.

    Args:
        scenario: Scenario dictionary to validate

    Returns:
        LintResult with separate errors and warnings

    Note:
        Supports lint_allow.unidirectional_exits to suppress warnings for
        intentionally one-way exits (e.g., locked doors).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check required fields
    required_fields = ["name", "locations", "characters"]
    for field in required_fields:
        if field not in scenario:
            errors.append(f"必須フィールド '{field}' がありません")

    # If missing required fields, return early
    if errors:
        return LintResult(errors=errors, warnings=warnings)

    locations = scenario.get("locations", {})
    characters = scenario.get("characters", {})

    # Get allowlist for unidirectional exits
    lint_allow = scenario.get("lint_allow", {})
    allowed_unidirectional = set(lint_allow.get("unidirectional_exits", []))

    # Check exit references (ERROR - invalid reference)
    for loc_name, loc_data in locations.items():
        exits = loc_data.get("exits", [])
        for exit_loc in exits:
            if exit_loc not in locations:
                errors.append(
                    f"無効なexit参照: '{loc_name}' から '{exit_loc}' への出口がありますが、"
                    f"'{exit_loc}' は存在しません"
                )

    # Check bidirectional exits (WARNING - intentional design may have one-way)
    for loc_name, loc_data in locations.items():
        exits = loc_data.get("exits", [])
        for exit_loc in exits:
            if exit_loc in locations:
                other_exits = locations[exit_loc].get("exits", [])
                if loc_name not in other_exits:
                    # Check if this location is in the allowlist
                    if loc_name not in allowed_unidirectional:
                        warnings.append(
                            f"一方向(unidirectional) exit: '{loc_name}' -> '{exit_loc}' "
                            f"の逆方向がありません"
                        )

    # Check character locations (ERROR - invalid location)
    for char_name, char_data in characters.items():
        char_location = char_data.get("location", "")
        if char_location not in locations:
            errors.append(
                f"キャラクター '{char_name}' の location '{char_location}' は "
                f"定義されていません"
            )

    # Check containers (WARNING - parent should exist in props)
    for loc_name, loc_data in locations.items():
        props = set(loc_data.get("props", []))
        containers = loc_data.get("containers", {})

        for container_name in containers.keys():
            if container_name not in props:
                warnings.append(
                    f"コンテナ '{container_name}' は '{loc_name}' の props に"
                    f"ありません（lint_allow.orphan_containersで抑制可）"
                )

    # Check hidden_objects (WARNING - should not overlap with visible props)
    for loc_name, loc_data in locations.items():
        props = set(loc_data.get("props", []))
        hidden = loc_data.get("hidden_objects", [])

        for hidden_obj in hidden:
            if hidden_obj in props:
                warnings.append(
                    f"'{hidden_obj}' は '{loc_name}' の props と hidden_objects "
                    f"の両方に存在します"
                )

    return LintResult(errors=errors, warnings=warnings)


# =============================================================================
# C3: World Summary
# =============================================================================


def generate_world_summary(scenario: dict) -> WorldSummary:
    """Generate world summary for display.

    Args:
        scenario: Scenario dictionary

    Returns:
        WorldSummary with aggregated information
    """
    locations = scenario.get("locations", {})
    characters = scenario.get("characters", {})

    # Count props across all locations
    prop_count = sum(
        len(loc_data.get("props", [])) for loc_data in locations.values()
    )

    # Build character positions
    character_positions = {
        char_name: char_data.get("location", "不明")
        for char_name, char_data in characters.items()
    }

    # Build exit graph
    exit_graph = {
        loc_name: loc_data.get("exits", [])
        for loc_name, loc_data in locations.items()
    }

    return WorldSummary(
        name=scenario.get("name", "unnamed"),
        location_count=len(locations),
        prop_count=prop_count,
        character_positions=character_positions,
        exit_graph=exit_graph,
    )


def format_summary_text(summary: WorldSummary) -> str:
    """Format world summary as human-readable text.

    Args:
        summary: WorldSummary to format

    Returns:
        Formatted text string
    """
    lines = [
        f"=== {summary['name']} ===",
        f"Locations: {summary['location_count']}",
        f"Props: {summary['prop_count']}",
        "",
        "Characters:",
    ]

    for char_name, location in summary["character_positions"].items():
        lines.append(f"  {char_name}: {location}")

    lines.append("")
    lines.append("Exit Graph:")

    for loc_name, exits in summary["exit_graph"].items():
        exit_str = ", ".join(exits) if exits else "(no exits)"
        lines.append(f"  {loc_name} -> {exit_str}")

    return "\n".join(lines)


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    """CLI entry point for scenario tools."""
    import argparse

    parser = argparse.ArgumentParser(description="Scenario tools for duo-talk evaluation")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # new command
    new_parser = subparsers.add_parser("new", help="Generate new scenario template")
    new_parser.add_argument("id", help="Scenario ID (e.g., scn_001)")
    new_parser.add_argument(
        "-o", "--output",
        help="Output directory (default: experiments/scenarios)",
        default="experiments/scenarios",
    )

    # lint command
    lint_parser = subparsers.add_parser("lint", help="Validate scenario file(s)")
    lint_parser.add_argument("files", nargs="+", help="Scenario JSON file(s) to lint")

    # summary command
    summary_parser = subparsers.add_parser("summary", help="Generate world summary")
    summary_parser.add_argument("file", help="Scenario JSON file")

    args = parser.parse_args()

    if args.command == "new":
        template = generate_template(args.id)
        output_path = Path(args.output) / f"{args.id}.json"
        write_template(template, output_path)
        print(f"Created: {output_path}")

    elif args.command == "lint":
        all_valid = True
        for file_path in args.files:
            path = Path(file_path)
            if not path.exists():
                print(f"ERROR: {file_path} not found")
                all_valid = False
                continue

            scenario = json.loads(path.read_text(encoding="utf-8"))
            result = lint_scenario_detailed(scenario)

            if result["errors"]:
                print(f"FAIL: {file_path}")
                for error in result["errors"]:
                    print(f"  [ERROR] {error}")
                for warning in result["warnings"]:
                    print(f"  [WARN] {warning}")
                all_valid = False
            elif result["warnings"]:
                print(f"WARN: {file_path}")
                for warning in result["warnings"]:
                    print(f"  [WARN] {warning}")
                # Warnings don't fail the lint
            else:
                print(f"OK: {file_path}")

        return 0 if all_valid else 1

    elif args.command == "summary":
        path = Path(args.file)
        if not path.exists():
            print(f"ERROR: {args.file} not found")
            return 1

        scenario = json.loads(path.read_text(encoding="utf-8"))
        summary = generate_world_summary(scenario)
        print(format_summary_text(summary))
        return 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
