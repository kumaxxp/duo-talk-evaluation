"""Config loading and validation for HAKONIWA."""

import hashlib
from pathlib import Path

import yaml

from hakoniwa.config.schema import HakoniwaConfig


def load_config(path: Path | None = None) -> HakoniwaConfig:
    """Load config from YAML file or return defaults.

    Args:
        path: Path to YAML config file (optional)

    Returns:
        Loaded HakoniwaConfig
    """
    if path is None or not path.exists():
        return HakoniwaConfig()

    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content) or {}

    return HakoniwaConfig(**data)


def validate_config(path: Path) -> tuple[bool, list[str]]:
    """Validate config file.

    Args:
        path: Path to config file

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors: list[str] = []

    if not path.exists():
        return False, [f"Config file not found: {path}"]

    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        if data is None:
            data = {}

        HakoniwaConfig(**data)
        return True, []

    except yaml.YAMLError as e:
        return False, [f"Invalid YAML: {e}"]
    except Exception as e:
        return False, [str(e)]


def get_config_hash(config: HakoniwaConfig) -> str:
    """Get hash of config for change detection.

    Args:
        config: Config to hash

    Returns:
        Short hash string
    """
    content = config.model_dump_json(indent=None)
    full_hash = hashlib.sha256(content.encode()).hexdigest()
    return full_hash[:12]


def get_health_summary(config: HakoniwaConfig) -> dict:
    """Get health summary for config.

    Args:
        config: Config to summarize

    Returns:
        Health summary dict
    """
    return {
        "status": "OK",
        "config_hash": get_config_hash(config),
        "llm_backend": config.llm_backend,
        "llm_model": config.llm_model,
        "llm_base_url": config.llm_base_url,
        "max_turns": config.max_turns,
        "max_retries": config.max_retries,
        "results_dir": config.results_dir,
    }
