"""Results data loader.

Loads and parses run results from results/ directory.
"""

import json
import re
from pathlib import Path
from typing import TypedDict


class RunInfo(TypedDict, total=False):
    """Information about a run."""

    dir_name: str
    path: str
    profile: str
    scenarios: list[str]
    total_turns: int
    timestamp: str


def list_runs(results_dir: Path) -> list[RunInfo]:
    """List all run directories, sorted by timestamp (newest first).

    Args:
        results_dir: Path to results directory

    Returns:
        List of RunInfo dicts
    """
    runs = []

    for path in results_dir.iterdir():
        if not path.is_dir():
            continue

        dir_name = path.name

        # Extract timestamp from directory name (format: *_YYYYMMDD_HHMMSS)
        timestamp_match = re.search(r"(\d{8}_\d{6})$", dir_name)
        timestamp = timestamp_match.group(1) if timestamp_match else "000000_000000"

        runs.append(
            RunInfo(
                dir_name=dir_name,
                path=str(path),
                timestamp=timestamp,
            )
        )

    # Sort by timestamp descending (newest first)
    runs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return runs


def get_run_info(run_dir: Path) -> RunInfo:
    """Get detailed info about a run from result.json.

    Args:
        run_dir: Path to run directory

    Returns:
        RunInfo with metadata from result.json
    """
    result_path = run_dir / "result.json"

    info = RunInfo(
        dir_name=run_dir.name,
        path=str(run_dir),
    )

    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            info["profile"] = data.get("profile", "unknown")
            info["scenarios"] = data.get("scenarios", [])
            info["total_turns"] = data.get("total_turns", 0)
        except (json.JSONDecodeError, IOError):
            pass

    return info


def load_turns_log(run_dir: Path) -> list[dict]:
    """Load turns_log.json from a run directory.

    Args:
        run_dir: Path to run directory

    Returns:
        List of turn entries
    """
    log_path = run_dir / "turns_log.json"

    if not log_path.exists():
        return []

    try:
        return json.loads(log_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


class RunStatistics(TypedDict):
    """Statistics for a run."""

    total_turns: int
    retry_count: int
    give_up_count: int
    format_break_count: int


def get_run_statistics(run_dir: Path) -> RunStatistics:
    """Calculate statistics from turns_log.

    Args:
        run_dir: Path to run directory

    Returns:
        RunStatistics with counts
    """
    turns = load_turns_log(run_dir)

    stats = RunStatistics(
        total_turns=len(turns),
        retry_count=0,
        give_up_count=0,
        format_break_count=0,
    )

    for turn in turns:
        if turn.get("retry_steps", 0) > 0:
            stats["retry_count"] += 1
        if turn.get("give_up", False):
            stats["give_up_count"] += 1
        if turn.get("format_break_triggered", False):
            stats["format_break_count"] += 1

    return stats


def filter_issue_turns(turns: list[dict]) -> list[dict]:
    """Filter turns that have issues for quick triage.

    Issues include: retry, format_break, give_up

    Args:
        turns: List of turn dictionaries

    Returns:
        Filtered list of turns with issues
    """
    return [
        turn for turn in turns
        if (
            turn.get("retry_steps", 0) > 0 or
            turn.get("format_break_triggered", False) or
            turn.get("give_up", False)
        )
    ]
