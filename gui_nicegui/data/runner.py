"""Runner command generation for GUI execution.

Generates correct commands and environment for running experiments.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict


class RunnerCommand(TypedDict):
    """Command configuration for runner execution."""

    cmd: list[str]
    env: dict[str, str]
    cwd: Path


def generate_experiment_id(scenario_id: str, profile: str) -> str:
    """Generate unique experiment ID.

    Args:
        scenario_id: Scenario identifier
        profile: Experiment profile (dev/gate/full)

    Returns:
        Unique experiment ID with timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"gui_{scenario_id}_{profile}_{timestamp}"


def build_runner_command(
    scenario_id: str,
    profile: str,
    project_root: Path,
    max_turns: int | None = None,
    mode: str = "real",
    llm_model: str | None = None,
) -> RunnerCommand:
    """Build command to run experiment.

    Args:
        scenario_id: Scenario to run
        profile: Experiment profile (dev/gate/full)
        project_root: Project root directory
        max_turns: Optional max turns override
        mode: Generation mode - "real" (Ollama) or "sim" (simulation)
        llm_model: Optional Ollama model name

    Returns:
        RunnerCommand with cmd, env, and cwd
    """
    experiment_id = generate_experiment_id(scenario_id, profile)

    cmd = [
        sys.executable,
        "experiments/gm_2x2_runner.py",
        "--experiment_id",
        experiment_id,
        "--profile",
        profile,
        "--scenarios",
        scenario_id,
        "--mode",
        mode,
    ]

    if max_turns is not None:
        cmd.extend(["--max_turns", str(max_turns)])

    if llm_model is not None:
        cmd.extend(["--llm_model", llm_model])

    # Environment must include PYTHONPATH for module imports
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    return RunnerCommand(
        cmd=cmd,
        env=env,
        cwd=project_root,
    )
