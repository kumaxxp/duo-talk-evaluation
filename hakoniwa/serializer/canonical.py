"""Canonical JSON serialization for HAKONIWA.

Provides deterministic serialization for world state to enable:
- Hash-based change detection
- Reproducible builds
- Diff-friendly output
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Type, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


def _datetime_handler(obj: Any) -> str:
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def serialize_to_json(obj: BaseModel) -> str:
    """Serialize Pydantic model to canonical JSON.

    Produces deterministic output with:
    - Sorted keys
    - 2-space indentation
    - No trailing whitespace
    - UTF-8 encoding
    - Trailing newline

    Args:
        obj: Pydantic model to serialize

    Returns:
        Canonical JSON string
    """
    # Convert to dict, handling datetime
    data = obj.model_dump(mode="json")

    # Serialize with canonical settings
    content = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_datetime_handler,
    )

    # Ensure trailing newline
    if not content.endswith("\n"):
        content += "\n"

    return content


def deserialize_from_json(content: str, model_class: Type[T]) -> T:
    """Deserialize JSON to Pydantic model.

    Args:
        content: JSON string
        model_class: Pydantic model class to deserialize to

    Returns:
        Deserialized model instance
    """
    data = json.loads(content)
    return model_class(**data)


def compute_hash(content: str) -> str:
    """Compute SHA256 hash of content.

    Args:
        content: String content to hash

    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
