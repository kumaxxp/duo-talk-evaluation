"""Latest run pointer management.

Tracks the latest run for each scenario.
"""

import json
from pathlib import Path
from typing import TypedDict


class LatestPointer(TypedDict, total=False):
    """Latest run pointer data."""

    scenario_id: str
    run_dir: str
    scenario_hash: str
    world_hash: str
    gm_version: str
    prompt_version: str
    timestamp: str
    give_up_count: int
    retry_count: int
    format_break_count: int
    total_turns: int


def get_latest_pointer_path(results_dir: Path, scenario_id: str) -> Path:
    """Get path to latest pointer file.

    Args:
        results_dir: Results directory
        scenario_id: Scenario identifier

    Returns:
        Path to latest pointer JSON file
    """
    return results_dir / f"latest_{scenario_id}.json"


def save_latest_pointer(
    results_dir: Path,
    scenario_id: str,
    pointer_data: LatestPointer,
) -> None:
    """Save latest run pointer.

    Args:
        results_dir: Results directory
        scenario_id: Scenario identifier
        pointer_data: Pointer data to save
    """
    pointer_path = get_latest_pointer_path(results_dir, scenario_id)
    pointer_path.write_text(
        json.dumps(pointer_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_latest_pointer(
    results_dir: Path,
    scenario_id: str,
) -> LatestPointer | None:
    """Load latest run pointer.

    Args:
        results_dir: Results directory
        scenario_id: Scenario identifier

    Returns:
        LatestPointer data or None if not found
    """
    pointer_path = get_latest_pointer_path(results_dir, scenario_id)

    if not pointer_path.exists():
        return None

    try:
        return json.loads(pointer_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None
