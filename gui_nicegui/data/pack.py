"""Demo pack management.

Manages demo pack scenarios and pack runs.
"""

from datetime import datetime
from pathlib import Path
from typing import TypedDict


class DemoScenario(TypedDict, total=False):
    """Demo scenario from registry."""

    scenario_id: str
    path: str | None
    tags: list[str]
    recommended_profile: str
    description: str


def get_demo_scenarios(registry: list[dict]) -> list[DemoScenario]:
    """Filter scenarios with 'demo' tag from registry.

    Args:
        registry: List of registry entries

    Returns:
        List of scenarios with 'demo' tag
    """
    return [
        entry for entry in registry
        if "demo" in entry.get("tags", [])
    ]


def create_pack_run_id() -> str:
    """Create unique pack run ID.

    Returns:
        Pack run ID with timestamp (e.g., demo_pack_20260125_120000)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"demo_pack_{timestamp}"


def get_pack_run_dir(results_dir: Path, pack_id: str) -> Path:
    """Get pack run directory path.

    Args:
        results_dir: Base results directory
        pack_id: Pack run ID

    Returns:
        Path to pack run directory
    """
    return results_dir / pack_id


# =============================================================================
# Play Mode Integration (Phase F)
# =============================================================================


def generate_play_command(scenario_id: str, include_path: bool = False) -> str:
    """Generate CLI command for play mode.

    Args:
        scenario_id: Scenario ID to play
        include_path: If True, include full python command path

    Returns:
        CLI command string
    """
    if include_path:
        return f"python scripts/play_mode.py {scenario_id}"
    return f"make play s={scenario_id}"
