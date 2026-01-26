"""Scenario data loader.

Loads and parses scenario files from experiments/scenarios/.
"""

import json
from pathlib import Path
from typing import TypedDict


class ScenarioSummary(TypedDict):
    """Summary info extracted from scenario."""

    name: str
    description: str
    location_count: int
    character_count: int
    top_props: list[str]


def list_scenarios(scenarios_dir: Path) -> list[dict]:
    """List all scenario files in a directory.

    Args:
        scenarios_dir: Path to scenarios directory

    Returns:
        List of scenario dicts with at least 'name' and 'path' keys
    """
    scenarios = []
    for path in sorted(scenarios_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_path"] = str(path)
            scenarios.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    return scenarios


def load_scenario(path: Path) -> dict:
    """Load a single scenario file.

    Args:
        path: Path to scenario JSON file

    Returns:
        Parsed scenario dict
    """
    return json.loads(path.read_text(encoding="utf-8"))


def get_scenario_summary(scenario: dict) -> ScenarioSummary:
    """Extract summary info from a scenario.

    Args:
        scenario: Parsed scenario dict

    Returns:
        ScenarioSummary with key metrics
    """
    locations = scenario.get("locations", {})
    characters = scenario.get("characters", {})

    # Collect all props from all locations
    all_props: list[str] = []
    for loc_data in locations.values():
        props = loc_data.get("props", [])
        all_props.extend(props)

    return ScenarioSummary(
        name=scenario.get("name", "unknown"),
        description=scenario.get("description", ""),
        location_count=len(locations),
        character_count=len(characters),
        top_props=all_props[:5],  # First 5 props
    )
