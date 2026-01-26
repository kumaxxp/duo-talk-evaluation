"""Manifest schema for HAKONIWA world state.

The manifest contains metadata about the saved world state.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# Current schema version - increment when breaking changes occur
CURRENT_SCHEMA_VERSION = "1.0.0"


def _generate_session_id() -> str:
    """Generate a unique session ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"hakoniwa_{timestamp}_{unique_id}"


class Manifest(BaseModel):
    """Manifest for world state persistence.

    Contains metadata about the saved state including version,
    session ID, and timestamps.
    """

    model_config = ConfigDict(extra="forbid")

    # Schema version for compatibility checking
    schema_version: str = Field(
        default=CURRENT_SCHEMA_VERSION,
        description="Schema version for compatibility",
    )

    # Unique session identifier
    session_id: str = Field(
        default_factory=_generate_session_id,
        description="Unique session identifier",
    )

    # Creation timestamp
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when state was created",
    )

    # Last modified timestamp
    modified_at: datetime | None = Field(
        default=None,
        description="Timestamp when state was last modified",
    )

    # Optional description
    description: str = Field(
        default="",
        description="Optional description of this save",
    )
