"""Save functionality for HAKONIWA world state.

Saves WorldStateDTO to canonical JSON with hash file.
"""

from pathlib import Path

from hakoniwa.dto.world_state import WorldStateDTO
from hakoniwa.serializer.canonical import serialize_to_json, compute_hash


def save_world_state(dto: WorldStateDTO, path: Path) -> str:
    """Save world state to file.

    Creates:
    - path: Canonical JSON file with world state
    - path.sha256: Hash file for integrity verification

    Args:
        dto: WorldStateDTO to save
        path: Path to save file

    Returns:
        SHA256 hash of saved content
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize to canonical JSON
    content = serialize_to_json(dto)

    # Compute hash
    content_hash = compute_hash(content)

    # Write state file
    path.write_text(content, encoding="utf-8")

    # Write hash file
    hash_path = Path(str(path) + ".sha256")
    hash_path.write_text(content_hash, encoding="utf-8")

    return content_hash
