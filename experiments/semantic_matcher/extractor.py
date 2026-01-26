"""Extract MISSING_OBJECT samples from evaluation logs.

Extracts samples from turns_log.json and world_canonical.json
for evaluating the Semantic Matcher's ability to rescue missing objects.
"""

import json
from pathlib import Path

from .eval_types import MissingObjectSample


def extract_world_objects(world_canonical_path: Path) -> set[str]:
    """Extract all valid object names from world_canonical.json.

    Args:
        world_canonical_path: Path to world_canonical.json

    Returns:
        Set of valid object names (props)
    """
    with open(world_canonical_path, encoding="utf-8") as f:
        world = json.load(f)

    # Extract all prop names
    props = world.get("props", {})
    return set(props.keys())


def extract_samples_from_run(
    run_path: Path,
    scenario: str | None = None,
) -> list[MissingObjectSample]:
    """Extract MISSING_OBJECT samples from a single run directory.

    Looks for:
    - invented_objects: Objects LLM tried to use but don't exist
    - blocked_target_before/after: Objects blocked by GM
    - denied_reason == "MISSING_OBJECT": Hard denial cases

    Args:
        run_path: Path to run directory containing turns_log.json
        scenario: Override scenario name (optional)

    Returns:
        List of MissingObjectSample instances
    """
    samples = []

    turns_log_path = run_path / "turns_log.json"
    if not turns_log_path.exists():
        return samples

    # Find world_canonical.json in artifacts subdirectory
    world_objects: set[str] = set()
    artifacts_dir = run_path / "artifacts"
    if artifacts_dir.exists():
        # Look for any session's world_canonical.json
        for session_dir in artifacts_dir.iterdir():
            if session_dir.is_dir():
                world_path = session_dir / "world_canonical.json"
                if world_path.exists():
                    world_objects = extract_world_objects(world_path)
                    break

    with open(turns_log_path, encoding="utf-8") as f:
        turns = json.load(f)

    for turn in turns:
        session_id = turn.get("session_id", "")
        turn_number = turn.get("turn_number", 0)
        speaker = turn.get("speaker", "")
        denied_reason = turn.get("denied_reason")
        scenario_name = scenario or turn.get("scenario", "unknown")

        # Check for invented_objects (soft denial - objects not in world)
        invented_objects = turn.get("invented_objects", [])
        invented_reasons = turn.get("invented_reasons", {})

        for obj in invented_objects:
            sample_id = f"{session_id}_t{turn_number}_invented_{obj}"
            reason = invented_reasons.get(obj, "invented_object")

            # Try to determine ground truth from marker_targets
            # If the original target was in world, that's likely the GT
            gt = _infer_ground_truth(obj, turn, world_objects)

            samples.append(
                MissingObjectSample(
                    sample_id=sample_id,
                    run_path=run_path,
                    session_id=session_id,
                    turn_number=turn_number,
                    query=obj,
                    world_objects=world_objects.copy(),
                    scenario=scenario_name,
                    speaker=speaker,
                    denied_reason=reason,
                    ground_truth=gt,
                )
            )

        # Check for blocked_target (objects blocked by preflight/GM)
        blocked_before = turn.get("blocked_target_before")
        blocked_after = turn.get("blocked_target_after")

        for blocked in [blocked_before, blocked_after]:
            if blocked and blocked not in [obj for obj in invented_objects]:
                sample_id = f"{session_id}_t{turn_number}_blocked_{blocked}"
                gt = _infer_ground_truth(blocked, turn, world_objects)

                samples.append(
                    MissingObjectSample(
                        sample_id=sample_id,
                        run_path=run_path,
                        session_id=session_id,
                        turn_number=turn_number,
                        query=blocked,
                        world_objects=world_objects.copy(),
                        scenario=scenario_name,
                        speaker=speaker,
                        denied_reason=denied_reason or "blocked_target",
                        ground_truth=gt,
                    )
                )

        # Check for hard MISSING_OBJECT denial
        if denied_reason == "MISSING_OBJECT":
            # Extract target from marker_targets if not already captured
            marker_targets = turn.get("marker_targets_before", [])
            for target in marker_targets:
                if target not in world_objects:
                    # Already captured via invented_objects or blocked_target check
                    existing = [s.query for s in samples if s.turn_number == turn_number]
                    if target not in existing:
                        sample_id = f"{session_id}_t{turn_number}_denied_{target}"
                        gt = _infer_ground_truth(target, turn, world_objects)

                        samples.append(
                            MissingObjectSample(
                                sample_id=sample_id,
                                run_path=run_path,
                                session_id=session_id,
                                turn_number=turn_number,
                                query=target,
                                world_objects=world_objects.copy(),
                                scenario=scenario_name,
                                speaker=speaker,
                                denied_reason="MISSING_OBJECT",
                                ground_truth=gt,
                            )
                        )

    return samples


def _infer_ground_truth(
    query: str,
    turn: dict,
    world_objects: set[str],
) -> str | None:
    """Try to infer ground truth match for a query.

    Heuristics:
    1. If query is a substring of a world object, that's likely GT
    2. If world object is a substring of query, that's likely GT
    3. If marker_targets_after contains a world object, that's likely GT

    Args:
        query: The missing object query
        turn: Turn data from turns_log.json
        world_objects: Valid objects in world

    Returns:
        Inferred ground truth or None if cannot determine
    """
    # Normalize query for comparison
    query_lower = query.lower()

    # Check exact match (shouldn't happen but handle it)
    if query in world_objects:
        return query

    # Check substring matches
    for obj in world_objects:
        obj_lower = obj.lower()
        # Query is substring of world object (e.g., "カップ" → "マグカップ")
        if query_lower in obj_lower:
            return obj
        # World object is substring of query (e.g., "大きなマグカップ" → "マグカップ")
        if obj_lower in query_lower:
            return obj

    # Check marker_targets_after for successful resolution
    marker_after = turn.get("marker_targets_after", [])
    for target in marker_after:
        if target in world_objects and target != query:
            return target

    # Check resolved_target field
    resolved = turn.get("resolved_target")
    if resolved and resolved in world_objects:
        return resolved

    return None


def extract_samples_from_results_dir(
    results_dir: Path,
    pattern: str = "gm_*",
) -> list[MissingObjectSample]:
    """Extract samples from all runs matching pattern in results directory.

    Args:
        results_dir: Path to results/ directory
        pattern: Glob pattern for run directories

    Returns:
        List of all extracted samples
    """
    all_samples = []

    for run_dir in results_dir.glob(pattern):
        if run_dir.is_dir():
            samples = extract_samples_from_run(run_dir)
            all_samples.extend(samples)

    return all_samples


def deduplicate_samples(
    samples: list[MissingObjectSample],
) -> list[MissingObjectSample]:
    """Remove duplicate samples based on sample_id.

    Args:
        samples: List of samples

    Returns:
        Deduplicated list
    """
    seen: set[str] = set()
    unique = []

    for sample in samples:
        if sample.sample_id not in seen:
            seen.add(sample.sample_id)
            unique.append(sample)

    return unique


def filter_samples_with_gt(
    samples: list[MissingObjectSample],
) -> tuple[list[MissingObjectSample], list[MissingObjectSample]]:
    """Split samples into those with and without ground truth.

    Args:
        samples: All samples

    Returns:
        Tuple of (samples_with_gt, samples_without_gt)
    """
    with_gt = [s for s in samples if s.ground_truth is not None]
    without_gt = [s for s in samples if s.ground_truth is None]
    return with_gt, without_gt
