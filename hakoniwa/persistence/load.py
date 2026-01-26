"""Load functionality for HAKONIWA world state.

Load --dry-run: Validate file integrity without full load
Load: Hydrate WorldStateDTO from file
"""

import json
from pathlib import Path

from hakoniwa.dto.manifest import CURRENT_SCHEMA_VERSION
from hakoniwa.dto.world_state import WorldStateDTO
from hakoniwa.serializer.canonical import compute_hash, deserialize_from_json


def load_dry_run(path: Path) -> tuple[bool, list[str]]:
    """Validate world state file without loading.

    Checks:
    1. File exists
    2. Hash file exists and matches
    3. JSON is valid
    4. Schema version is compatible

    Args:
        path: Path to state file

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors: list[str] = []

    # Check file exists
    if not path.exists():
        return False, [f"File not found: {path}"]

    # Check hash file exists
    hash_path = Path(str(path) + ".sha256")
    if not hash_path.exists():
        return False, [f"Hash file not found: {hash_path}"]

    # Read content
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"Failed to read file: {e}"]

    # Verify hash
    expected_hash = hash_path.read_text(encoding="utf-8").strip()
    actual_hash = compute_hash(content)

    if actual_hash != expected_hash:
        errors.append(f"Hash mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}...")
        return False, errors

    # Validate JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    # Check schema version
    manifest = data.get("manifest", {})
    schema_version = manifest.get("schema_version", "unknown")

    if not _is_compatible_version(schema_version, CURRENT_SCHEMA_VERSION):
        errors.append(
            f"Schema version mismatch: file has {schema_version}, "
            f"current is {CURRENT_SCHEMA_VERSION}"
        )
        return False, errors

    # Try to parse as DTO (validates structure)
    try:
        deserialize_from_json(content, WorldStateDTO)
    except Exception as e:
        return False, [f"Invalid world state structure: {e}"]

    return True, []


def _is_compatible_version(file_version: str, current_version: str) -> bool:
    """Check if file version is compatible with current version.

    Currently uses simple major version check.

    Args:
        file_version: Version from file
        current_version: Current schema version

    Returns:
        True if compatible
    """
    try:
        file_major = int(file_version.split(".")[0])
        current_major = int(current_version.split(".")[0])
        return file_major == current_major
    except (ValueError, IndexError):
        return False


def load_world_state(path: Path) -> WorldStateDTO:
    """Load world state from file.

    Args:
        path: Path to state file

    Returns:
        Loaded WorldStateDTO

    Raises:
        ValueError: If file is invalid
        FileNotFoundError: If file doesn't exist
    """
    # First validate
    is_valid, errors = load_dry_run(path)
    if not is_valid:
        raise ValueError(f"Invalid world state file: {'; '.join(errors)}")

    # Load and deserialize
    content = path.read_text(encoding="utf-8")
    return deserialize_from_json(content, WorldStateDTO)
