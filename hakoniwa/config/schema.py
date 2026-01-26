"""Configuration schema for HAKONIWA."""

from pydantic import BaseModel, ConfigDict, Field


class HakoniwaConfig(BaseModel):
    """Configuration for HAKONIWA sessions."""

    model_config = ConfigDict(extra="forbid")

    # LLM settings
    llm_backend: str = Field(
        default="ollama",
        description="LLM backend (ollama, koboldcpp)",
    )
    llm_model: str = Field(
        default="gemma3:12b",
        description="LLM model name",
    )
    llm_base_url: str = Field(
        default="http://localhost:11434",
        description="LLM API base URL",
    )

    # Session settings
    max_turns: int = Field(
        default=10,
        ge=1,
        description="Maximum turns per session",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retries per turn",
    )

    # Output settings
    results_dir: str = Field(
        default="results",
        description="Directory for session results",
    )
