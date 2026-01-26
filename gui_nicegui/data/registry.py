"""Scenario registry loading.

Loads scenario definitions from registry.yaml.
"""

import hashlib
import json
from pathlib import Path
from typing import TypedDict

import yaml


class RegistryEntry(TypedDict, total=False):
    """Registry entry for a scenario."""

    scenario_id: str
    path: str | None
    tags: list[str]
    recommended_profile: str
    description: str


def load_registry(registry_path: Path) -> list[RegistryEntry]:
    """Load scenario registry from YAML file.

    Args:
        registry_path: Path to registry.yaml

    Returns:
        List of RegistryEntry dicts
    """
    if not registry_path.exists():
        return []

    content = registry_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    if not data or "scenarios" not in data:
        return []

    return data["scenarios"]


def get_scenario_hash(scenario: dict) -> str:
    """Generate a short hash for scenario content.

    Used for quick identification of scenario versions.

    Args:
        scenario: Scenario dictionary

    Returns:
        16-character hex hash
    """
    # Create a stable JSON representation
    content = json.dumps(scenario, sort_keys=True, ensure_ascii=False)
    full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return full_hash[:16]
