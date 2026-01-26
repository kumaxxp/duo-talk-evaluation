"""Configuration schema for HAKONIWA."""

from pydantic import BaseModel, ConfigDict, Field


class SemanticMatcherConfig(BaseModel):
    """Configuration for Semantic Matcher.

    The Semantic Matcher provides "Did you mean?" suggestions
    when MISSING_OBJECT errors occur.

    IMPORTANT: Auto-adopt is ALWAYS disabled (suggestion only).
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable semantic matcher suggestions (default: ON)",
    )
    suggest_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for suggestions (0.0-1.0)",
    )
    use_expansion: bool = Field(
        default=True,
        description="Enable query expansion (XのY pattern, etc.)",
    )
    max_suggestions: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum suggestions to show (1-5)",
    )
    # Note: auto_adopt_threshold is intentionally NOT exposed
    # Auto-adopt is ALWAYS disabled for safety


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

    # Semantic Matcher settings (P-Next4)
    semantic_matcher: SemanticMatcherConfig = Field(
        default_factory=SemanticMatcherConfig,
        description="Semantic matcher configuration for MISSING_OBJECT suggestions",
    )
