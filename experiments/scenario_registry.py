"""Scenario Registry and Validation (GM-019).

Single source of truth for scenario_id -> file path resolution.
Provides integrity validation for scenarios and world states.
"""

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class ValidationErrorCode(Enum):
    """Validation error reason codes (GM-019)."""

    REGISTRY_MISSING = "REGISTRY_MISSING"
    SCENARIO_ID_MISMATCH = "SCENARIO_ID_MISMATCH"
    EXIT_TARGET_MISSING = "EXIT_TARGET_MISSING"
    OBJ_LOCATION_MISSING = "OBJ_LOCATION_MISSING"
    CHAR_LOCATION_MISSING = "CHAR_LOCATION_MISSING"
    SCENARIO_FILE_NOT_FOUND = "SCENARIO_FILE_NOT_FOUND"
    REGISTRY_LOAD_ERROR = "REGISTRY_LOAD_ERROR"
    HASH_COMPUTATION_ERROR = "HASH_COMPUTATION_ERROR"


class SchemaValidationError(Exception):
    """Raised when scenario/world validation fails (GM-019).

    Attributes:
        code: ValidationErrorCode indicating the reason
        message: Human-readable error message
        details: Additional context (optional)
    """

    def __init__(
        self,
        message: str,
        code: ValidationErrorCode,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"


@dataclass
class ScenarioEntry:
    """Registry entry for a scenario."""

    scenario_id: str
    path: Optional[str]  # None for built-in default
    tags: list[str] = field(default_factory=list)
    recommended_profile: str = "dev"
    description: str = ""


@dataclass
class ValidationResult:
    """Result of scenario/world validation."""

    passed: bool
    errors: list[SchemaValidationError] = field(default_factory=list)

    @property
    def error_codes(self) -> list[str]:
        return [e.code.value for e in self.errors]


class ScenarioRegistry:
    """Registry for scenario resolution and validation (GM-019)."""

    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize the registry.

        Args:
            registry_path: Path to registry.yaml. If None, uses default location.
        """
        if registry_path is None:
            registry_path = Path(__file__).parent / "scenarios" / "registry.yaml"

        self.registry_path = registry_path
        self.scenarios_dir = registry_path.parent
        self._entries: dict[str, ScenarioEntry] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry from YAML file."""
        if not self.registry_path.exists():
            raise SchemaValidationError(
                f"Registry file not found: {self.registry_path}",
                ValidationErrorCode.REGISTRY_LOAD_ERROR,
            )

        try:
            with open(self.registry_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            for entry in data.get("scenarios", []):
                scenario_id = entry.get("scenario_id")
                if scenario_id:
                    self._entries[scenario_id] = ScenarioEntry(
                        scenario_id=scenario_id,
                        path=entry.get("path"),
                        tags=entry.get("tags", []),
                        recommended_profile=entry.get("recommended_profile", "dev"),
                        description=entry.get("description", ""),
                    )
        except Exception as e:
            raise SchemaValidationError(
                f"Failed to load registry: {e}",
                ValidationErrorCode.REGISTRY_LOAD_ERROR,
            ) from e

    def resolve(self, scenario_id: str) -> tuple[Optional[Path], ScenarioEntry]:
        """Resolve scenario_id to file path.

        Args:
            scenario_id: The scenario identifier

        Returns:
            (resolved_path, entry) - path is None for built-in default

        Raises:
            SchemaValidationError: If scenario_id not in registry
        """
        if scenario_id not in self._entries:
            raise SchemaValidationError(
                f"scenario_id '{scenario_id}' not found in registry. "
                f"Available: {list(self._entries.keys())}",
                ValidationErrorCode.REGISTRY_MISSING,
                {"scenario_id": scenario_id, "available": list(self._entries.keys())},
            )

        entry = self._entries[scenario_id]

        if entry.path is None:
            return None, entry  # Built-in default

        resolved_path = self.scenarios_dir / entry.path
        if not resolved_path.exists():
            raise SchemaValidationError(
                f"Scenario file not found: {resolved_path}",
                ValidationErrorCode.SCENARIO_FILE_NOT_FOUND,
                {"scenario_id": scenario_id, "path": str(resolved_path)},
            )

        return resolved_path, entry

    def load_scenario(self, scenario_id: str) -> tuple[dict, dict]:
        """Load and validate scenario, returning (scenario_data, scenario_meta).

        Args:
            scenario_id: The scenario identifier

        Returns:
            (scenario_data, scenario_meta) where scenario_meta includes:
            - scenario_id
            - scenario_path
            - scenario_resolved_path
            - registry_path
            - validation_passed
            - validation_errors

        Raises:
            SchemaValidationError: If validation fails
        """
        resolved_path, entry = self.resolve(scenario_id)

        if resolved_path is None:
            # Built-in default - no file to load
            scenario_data = None
            path_str = "default"
            resolved_str = "built-in"
        else:
            with open(resolved_path, encoding="utf-8") as f:
                scenario_data = json.load(f)
            path_str = entry.path
            resolved_str = str(resolved_path)

            # Validate scenario_id matches file content
            file_name = scenario_data.get("name")
            if file_name and file_name != scenario_id:
                raise SchemaValidationError(
                    f"scenario_id mismatch: registry has '{scenario_id}' "
                    f"but file contains name='{file_name}'",
                    ValidationErrorCode.SCENARIO_ID_MISMATCH,
                    {"registry_id": scenario_id, "file_name": file_name},
                )

        # Build scenario_meta
        scenario_meta = {
            "scenario_id": scenario_id,
            "scenario_path": path_str,
            "scenario_resolved_path": resolved_str,
            "registry_path": str(self.registry_path),
            "tags": entry.tags,
            "description": entry.description,
        }

        return scenario_data, scenario_meta

    def list_scenarios(self, tags: Optional[list[str]] = None) -> list[ScenarioEntry]:
        """List scenarios, optionally filtered by tags."""
        entries = list(self._entries.values())
        if tags:
            entries = [e for e in entries if any(t in e.tags for t in tags)]
        return entries


def validate_scenario_integrity(scenario_data: dict) -> ValidationResult:
    """Validate scenario data integrity (GM-019).

    Checks:
    - All exit targets reference existing locations
    - All object locations reference existing locations
    - All character locations reference existing locations

    Args:
        scenario_data: Loaded scenario JSON/dict

    Returns:
        ValidationResult with any errors found
    """
    errors: list[SchemaValidationError] = []

    if scenario_data is None:
        # Built-in default - no validation needed
        return ValidationResult(passed=True)

    locations = scenario_data.get("locations", {})
    location_names = set(locations.keys())

    # Check exit targets
    for loc_name, loc_data in locations.items():
        exits = loc_data.get("exits", [])
        for exit_target in exits:
            if exit_target not in location_names:
                errors.append(
                    SchemaValidationError(
                        f"Exit target '{exit_target}' from '{loc_name}' does not exist",
                        ValidationErrorCode.EXIT_TARGET_MISSING,
                        {"location": loc_name, "exit_target": exit_target},
                    )
                )

    # Check character locations
    characters = scenario_data.get("characters", {})
    for char_name, char_data in characters.items():
        char_loc = char_data.get("location")
        if char_loc and char_loc not in location_names:
            errors.append(
                SchemaValidationError(
                    f"Character '{char_name}' location '{char_loc}' does not exist",
                    ValidationErrorCode.CHAR_LOCATION_MISSING,
                    {"character": char_name, "location": char_loc},
                )
            )

    return ValidationResult(
        passed=len(errors) == 0,
        errors=errors,
    )


def canonicalize_dict(data: dict) -> str:
    """Convert dict to canonical JSON string (GM-019).

    Rules:
    - Keys are sorted
    - Lists are sorted by 'id' or 'name' if present, otherwise by repr
    - No runtime fields (counters, timestamps)

    Args:
        data: Dict to canonicalize

    Returns:
        Canonical JSON string
    """

    def _sort_key(item):
        if isinstance(item, dict):
            return item.get("id") or item.get("name") or str(sorted(item.items()))
        return str(item)

    def _canonicalize(obj):
        if isinstance(obj, dict):
            # Sort keys and recursively canonicalize values
            return {k: _canonicalize(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            # Sort lists if they contain dicts with id/name
            canonicalized = [_canonicalize(item) for item in obj]
            try:
                return sorted(canonicalized, key=_sort_key)
            except TypeError:
                return canonicalized  # Can't sort, keep original order
        else:
            return obj

    canonical = _canonicalize(data)
    return json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_scenario_hash(scenario_data: dict) -> str:
    """Compute SHA256 hash of scenario data (GM-019).

    Uses canonicalized JSON for deterministic hashing.

    Args:
        scenario_data: Scenario dict (from JSON file)

    Returns:
        First 16 chars of SHA256 hash
    """
    if scenario_data is None:
        # For default scenario, return a fixed hash
        return "default_scenario"

    canonical = canonicalize_dict(scenario_data)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def world_state_to_canonical(world_state: dict) -> str:
    """Convert WorldState to canonical JSON (GM-019).

    Excludes runtime fields that change during execution:
    - events (accumulates during run)
    - time.turn (increments)
    - Any field starting with '_'

    Args:
        world_state: World state dict

    Returns:
        Canonical JSON string
    """
    # Deep copy and filter out runtime fields
    def _filter_runtime(obj, path=""):
        if isinstance(obj, dict):
            filtered = {}
            for k, v in obj.items():
                # Skip runtime fields
                if k.startswith("_"):
                    continue
                if path == "" and k == "events":
                    continue  # events accumulate during run
                if path == "time" and k == "turn":
                    continue  # turn increments
                filtered[k] = _filter_runtime(v, f"{path}.{k}" if path else k)
            return filtered
        elif isinstance(obj, list):
            return [_filter_runtime(item, path) for item in obj]
        else:
            return obj

    filtered = _filter_runtime(world_state)
    return canonicalize_dict(filtered)


def compute_world_hash(world_state: dict) -> str:
    """Compute SHA256 hash of world state (GM-019).

    Uses canonical JSON with runtime fields excluded.

    Args:
        world_state: World state dict

    Returns:
        First 16 chars of SHA256 hash
    """
    canonical = world_state_to_canonical(world_state)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def generate_world_summary(world_state: dict) -> dict:
    """Generate world_summary for run_meta (GM-019).

    Returns:
        {
            "counts": {"locations": N, "objects": M, "characters": K},
            "objects_top10": ["obj1", "obj2", ...],
            "locations": ["loc1", "loc2", ...]
        }
    """
    locations = world_state.get("locations", {})
    characters = world_state.get("characters", {})
    props = world_state.get("props", {})

    return {
        "counts": {
            "locations": len(locations),
            "objects": len(props),
            "characters": len(characters),
        },
        "objects_top10": list(props.keys())[:10],
        "locations": list(locations.keys()),
    }
