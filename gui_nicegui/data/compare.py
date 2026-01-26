"""Run comparison utilities.

Compares current run with previous run.
"""

from typing import TypedDict


class MetaDiff(TypedDict):
    """Metadata comparison result."""

    is_first_run: bool
    scenario_hash_changed: bool
    world_hash_changed: bool
    gm_version_changed: bool
    prompt_version_changed: bool


class MetricsDiff(TypedDict):
    """Metrics comparison result."""

    give_up_delta: int
    retry_delta: int
    format_break_delta: int
    total_turns_delta: int


def compare_run_meta(
    current: dict,
    previous: dict | None,
) -> MetaDiff:
    """Compare run metadata and detect changes.

    Args:
        current: Current run metadata
        previous: Previous run metadata (None if first run)

    Returns:
        MetaDiff with change flags
    """
    if previous is None:
        return MetaDiff(
            is_first_run=True,
            scenario_hash_changed=False,
            world_hash_changed=False,
            gm_version_changed=False,
            prompt_version_changed=False,
        )

    return MetaDiff(
        is_first_run=False,
        scenario_hash_changed=(
            current.get("scenario_hash") != previous.get("scenario_hash")
        ),
        world_hash_changed=(
            current.get("world_hash") != previous.get("world_hash")
        ),
        gm_version_changed=(
            current.get("gm_version") != previous.get("gm_version")
        ),
        prompt_version_changed=(
            current.get("prompt_version") != previous.get("prompt_version")
        ),
    )


def compare_metrics(
    current: dict,
    previous: dict,
) -> MetricsDiff:
    """Compare key metrics between runs.

    Args:
        current: Current run metrics
        previous: Previous run metrics

    Returns:
        MetricsDiff with deltas (negative = improvement)
    """
    return MetricsDiff(
        give_up_delta=(
            current.get("give_up_count", 0) - previous.get("give_up_count", 0)
        ),
        retry_delta=(
            current.get("retry_count", 0) - previous.get("retry_count", 0)
        ),
        format_break_delta=(
            current.get("format_break_count", 0) - previous.get("format_break_count", 0)
        ),
        total_turns_delta=(
            current.get("total_turns", 0) - previous.get("total_turns", 0)
        ),
    )
