"""Evaluation engine for Semantic Matcher.

Runs the matcher on extracted samples and computes evaluation metrics.
"""

from datetime import datetime
from pathlib import Path

from .audit_log import AuditLogger
from .eval_types import (
    MissingObjectSample,
    EvalResult,
    EvalMetrics,
    EvalSummary,
)
from .fuzzy import FuzzyMatcher
from .types import AuditLogEntry


# Default threshold grid for evaluation
DEFAULT_THRESHOLD_GRID = [0.7, 0.75, 0.8, 0.85, 0.9]


def evaluate_sample(
    sample: MissingObjectSample,
    matcher: FuzzyMatcher,
    threshold: float,
    audit_logger: AuditLogger | None = None,
) -> EvalResult:
    """Evaluate a single sample using the matcher.

    Args:
        sample: The sample to evaluate
        matcher: The matcher instance
        threshold: Current threshold being evaluated
        audit_logger: Optional audit logger for recording

    Returns:
        EvalResult with evaluation outcome
    """
    # Run matcher
    result = matcher.match(sample.query, sample.world_objects)

    # Extract candidates as (name, score) tuples
    candidates = [(c.name, c.score) for c in result.candidates]

    # Determine top candidate
    top_candidate = candidates[0][0] if candidates else None
    top_score = candidates[0][1] if candidates else 0.0

    # Check if top candidate is above threshold
    has_suggestion = top_score >= threshold if candidates else False

    # Determine evaluation outcome
    is_true_positive = False
    is_false_positive = False
    is_no_match = False
    gt_in_candidates = False

    if sample.ground_truth:
        # Check if GT appears in any candidate
        gt_in_candidates = any(
            c[0] == sample.ground_truth for c in candidates
        )

        if has_suggestion:
            if top_candidate == sample.ground_truth:
                is_true_positive = True
            else:
                is_false_positive = True
        else:
            is_no_match = True
    else:
        # No GT - can only track if we made a suggestion
        if has_suggestion:
            is_false_positive = True  # Conservative: count as FP
        else:
            is_no_match = True

    eval_result = EvalResult(
        sample=sample,
        candidates=candidates,
        top_candidate=top_candidate,
        top_score=top_score,
        is_true_positive=is_true_positive,
        is_false_positive=is_false_positive,
        is_no_match=is_no_match,
        gt_in_candidates=gt_in_candidates,
        threshold_used=threshold,
    )

    # Record to audit log using existing AuditLogger
    if audit_logger:
        audit_logger.log_match_result(result, sample.world_objects)

    return eval_result


def evaluate_samples_at_threshold(
    samples: list[MissingObjectSample],
    threshold: float,
    audit_logger: AuditLogger | None = None,
) -> tuple[list[EvalResult], int]:
    """Evaluate all samples at a specific threshold.

    Args:
        samples: Samples with ground truth
        threshold: Threshold to evaluate
        audit_logger: Optional audit logger

    Returns:
        Tuple of (results, excluded_count)
    """
    # Create matcher with current threshold (auto-adopt disabled)
    matcher = FuzzyMatcher(
        suggest_threshold=threshold,
        allow_auto_adopt=False,  # CRITICAL: Auto-adopt disabled
    )

    results = []
    excluded_count = 0

    for sample in samples:
        # Skip samples without GT for metrics calculation
        if sample.ground_truth is None:
            excluded_count += 1
            continue

        result = evaluate_sample(sample, matcher, threshold, audit_logger)
        results.append(result)

    return results, excluded_count


def run_evaluation(
    samples: list[MissingObjectSample],
    threshold_grid: list[float] | None = None,
    output_dir: Path | None = None,
    input_source: str = "unknown",
) -> EvalSummary:
    """Run full evaluation across threshold grid.

    Args:
        samples: All samples to evaluate
        threshold_grid: Thresholds to evaluate (default: 0.7-0.9)
        output_dir: Directory to save audit log
        input_source: Description of input source

    Returns:
        EvalSummary with all metrics
    """
    if threshold_grid is None:
        threshold_grid = DEFAULT_THRESHOLD_GRID

    # Setup audit logger
    audit_logger = None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        audit_logger = AuditLogger(output_dir / "audit.jsonl")

    metrics_by_threshold: dict[float, EvalMetrics] = {}

    for threshold in threshold_grid:
        results, excluded_count = evaluate_samples_at_threshold(
            samples, threshold, audit_logger
        )

        metrics = EvalMetrics.compute(results, excluded_count, threshold)
        metrics_by_threshold[threshold] = metrics

    # Find best threshold and create summary
    summary = EvalSummary.find_best(metrics_by_threshold, input_source)

    return summary


def evaluate_single_query(
    query: str,
    world_objects: set[str],
    threshold: float = 0.7,
) -> tuple[str | None, float, list[tuple[str, float]]]:
    """Evaluate a single query (for interactive/testing use).

    Args:
        query: The query to match
        world_objects: Valid world objects
        threshold: Suggestion threshold

    Returns:
        Tuple of (top_match, score, all_candidates)
    """
    matcher = FuzzyMatcher(
        suggest_threshold=threshold,
        allow_auto_adopt=False,
    )

    result = matcher.match(query, world_objects)
    candidates = [(c.name, c.score) for c in result.candidates]

    if candidates and candidates[0][1] >= threshold:
        return candidates[0][0], candidates[0][1], candidates
    return None, 0.0, candidates
