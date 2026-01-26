"""WorldStateDTO - Canonical representation of world state for persistence.

This is the single source of truth for world state serialization.
All saves/loads go through this DTO.

Key principles:
- History is immutable (confirmed past, no re-generation)
- Artifacts are stored as relative path references
- Runtime state tracks current position for resume
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hakoniwa.config.schema import HakoniwaConfig
from hakoniwa.dto.manifest import Manifest


class TurnRecord(BaseModel):
    """Record of a single turn in the conversation.

    This is the confirmed past - once saved, it should not be modified.
    """

    model_config = ConfigDict(extra="forbid")

    # Turn identification
    turn_index: int = Field(
        ge=0,
        description="Zero-based turn index",
    )
    speaker: str = Field(
        description="Character who spoke (やな or あゆ)",
    )

    # Response content
    response: str = Field(
        description="The actual response text",
    )
    thought: str | None = Field(
        default=None,
        description="Internal thought if available",
    )

    # Metadata
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retries for this turn",
    )
    give_up: bool = Field(
        default=False,
        description="Whether GM gave up on this turn",
    )
    evaluation_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Evaluation score if available",
    )

    # Timestamp
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this turn was generated",
    )


class RuntimeState(BaseModel):
    """Runtime state for resume capability.

    Tracks current position in the session for resume.
    """

    model_config = ConfigDict(extra="forbid")

    # Current position
    turn_index: int = Field(
        default=0,
        ge=0,
        description="Next turn index to generate",
    )
    last_actor: str | None = Field(
        default=None,
        description="Last character who acted",
    )

    # Pending action (for resume)
    pending_action: str | None = Field(
        default=None,
        description="Action that was pending when saved",
    )

    # Session state
    is_complete: bool = Field(
        default=False,
        description="Whether session is complete",
    )
    completion_reason: str | None = Field(
        default=None,
        description="Reason for completion if complete",
    )


class ArtifactReference(BaseModel):
    """Reference to an artifact file.

    Artifacts are stored as relative paths to support export/import.

    Path Resolution Policy:
    - Paths are relative to the directory containing the state file
    - Example: state file at results/session/state.json
              artifact at results/session/turn_0.log
              relative_path = "turn_0.log"
    - On load, resolve: state_file.parent / relative_path

    Note: ZIP bundling is not implemented. Artifacts must exist
    at the resolved path for successful resume.
    """

    model_config = ConfigDict(extra="forbid")

    # Turn association
    turn_index: int = Field(
        ge=0,
        description="Turn this artifact belongs to",
    )

    # Artifact info
    artifact_type: str = Field(
        description="Type of artifact (raw_response, evaluation, etc.)",
    )
    relative_path: str = Field(
        description="Relative path from save directory",
    )


class WorldStateDTO(BaseModel):
    """Canonical representation of world state for persistence.

    This DTO is the single source of truth for world state.
    All serialization goes through this structure.

    Key sections:
    - manifest: Metadata about this save (version, session_id, etc.)
    - scenario_id: Which scenario this is for
    - history: List of confirmed turns (immutable past)
    - artifacts: References to artifact files
    - runtime: Current state for resume
    - config: Config snapshot at save time
    """

    model_config = ConfigDict(extra="forbid")

    # Manifest (required)
    manifest: Manifest = Field(
        description="Metadata about this world state",
    )

    # Scenario identification
    scenario_id: str = Field(
        description="Scenario this state belongs to",
    )

    # Turn history (immutable confirmed past)
    history: list[TurnRecord] = Field(
        default_factory=list,
        description="Confirmed turn history",
    )

    # Artifact references
    artifacts: list[ArtifactReference] = Field(
        default_factory=list,
        description="References to artifact files",
    )

    # Runtime state for resume
    runtime: RuntimeState = Field(
        default_factory=RuntimeState,
        description="Current runtime state",
    )

    # Config snapshot
    config: HakoniwaConfig = Field(
        default_factory=HakoniwaConfig,
        description="Config snapshot at save time",
    )

    @field_validator("history", mode="before")
    @classmethod
    def copy_history(cls, v):
        """Ensure history is a copy, not a reference."""
        if isinstance(v, list):
            return list(v)
        return v
