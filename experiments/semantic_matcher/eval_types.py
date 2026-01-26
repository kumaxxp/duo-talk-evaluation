"""Type definitions for Semantic Matcher evaluation.

Defines DTOs for evaluation samples, results, and metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class MissingObjectSample:
    """A single MISSING_OBJECT sample extracted from logs.

    Attributes:
        sample_id: Unique identifier for this sample
        run_path: Path to the run directory
        session_id: Session identifier
        turn_number: Turn number where the issue occurred
        query: The object name that was missing (from invented_objects or blocked_target)
        world_objects: Set of valid objects in the world at that time
        scenario: Scenario name
        speaker: Character who triggered the issue
        denied_reason: Original denial reason (if any)
        ground_truth: Expected correct match (if known, else None)
    """

    sample_id: str
    run_path: Path
    session_id: str
    turn_number: int
    query: str
    world_objects: set[str]
    scenario: str
    speaker: str
    denied_reason: str | None = None
    ground_truth: str | None = None  # Pseudo-GT if determinable


@dataclass
class EvalResult:
    """Result of evaluating one sample with the Semantic Matcher.

    Attributes:
        sample: The original sample
        candidates: List of (name, score) tuples returned by matcher
        top_candidate: The highest-scored candidate (if any)
        top_score: Score of top candidate
        is_true_positive: True if top candidate matches ground_truth
        is_false_positive: True if top candidate exists but doesn't match GT
        is_no_match: True if no candidates above threshold
        gt_in_candidates: True if ground_truth appears anywhere in candidates
        threshold_used: The threshold that was used
    """

    sample: MissingObjectSample
    candidates: list[tuple[str, float]]
    top_candidate: str | None
    top_score: float
    is_true_positive: bool
    is_false_positive: bool
    is_no_match: bool
    gt_in_candidates: bool
    threshold_used: float


@dataclass
class EvalMetrics:
    """Aggregated metrics from evaluation.

    Attributes:
        total_samples: Total samples evaluated
        excluded_samples: Samples excluded (no GT determinable)
        exclusion_rate: excluded_samples / (total_samples + excluded_samples)
        true_positives: Correct suggestions
        false_positives: Wrong suggestions
        no_matches: No suggestion made
        recall: TP / total_samples (rescue rate)
        precision: TP / (TP + FP) (suggestion accuracy)
        fp_rate: FP / total_samples
        threshold: Threshold used for this metric
    """

    total_samples: int
    excluded_samples: int
    exclusion_rate: float
    true_positives: int
    false_positives: int
    no_matches: int
    recall: float
    precision: float
    fp_rate: float
    threshold: float

    @classmethod
    def compute(
        cls,
        results: list[EvalResult],
        excluded_count: int,
        threshold: float,
    ) -> "EvalMetrics":
        """Compute metrics from evaluation results.

        Args:
            results: List of evaluation results
            excluded_count: Number of samples excluded
            threshold: Threshold used

        Returns:
            EvalMetrics instance
        """
        total = len(results)
        if total == 0:
            return cls(
                total_samples=0,
                excluded_samples=excluded_count,
                exclusion_rate=1.0 if excluded_count > 0 else 0.0,
                true_positives=0,
                false_positives=0,
                no_matches=0,
                recall=0.0,
                precision=0.0,
                fp_rate=0.0,
                threshold=threshold,
            )

        tp = sum(1 for r in results if r.is_true_positive)
        fp = sum(1 for r in results if r.is_false_positive)
        no_match = sum(1 for r in results if r.is_no_match)

        total_with_excluded = total + excluded_count
        exclusion_rate = excluded_count / total_with_excluded if total_with_excluded > 0 else 0.0

        recall = tp / total if total > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        fp_rate = fp / total if total > 0 else 0.0

        return cls(
            total_samples=total,
            excluded_samples=excluded_count,
            exclusion_rate=exclusion_rate,
            true_positives=tp,
            false_positives=fp,
            no_matches=no_match,
            recall=recall,
            precision=precision,
            fp_rate=fp_rate,
            threshold=threshold,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_samples": self.total_samples,
            "excluded_samples": self.excluded_samples,
            "exclusion_rate": round(self.exclusion_rate, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "no_matches": self.no_matches,
            "recall": round(self.recall, 4),
            "precision": round(self.precision, 4),
            "fp_rate": round(self.fp_rate, 4),
            "threshold": self.threshold,
        }


@dataclass
class EvalSummary:
    """Summary of evaluation across multiple thresholds.

    Attributes:
        generated_at: Timestamp of generation
        input_source: Description of input data source
        threshold_grid: List of thresholds evaluated
        metrics_by_threshold: Dict mapping threshold -> EvalMetrics
        best_threshold: Threshold with best F1 score
        best_metrics: Metrics at best threshold
    """

    generated_at: datetime
    input_source: str
    threshold_grid: list[float]
    metrics_by_threshold: dict[float, EvalMetrics]
    best_threshold: float
    best_metrics: EvalMetrics

    @classmethod
    def find_best(
        cls,
        metrics_by_threshold: dict[float, EvalMetrics],
        input_source: str,
    ) -> "EvalSummary":
        """Find best threshold by F1 score.

        Args:
            metrics_by_threshold: Dict of threshold -> metrics
            input_source: Description of input source

        Returns:
            EvalSummary with best threshold identified
        """
        best_f1 = -1.0
        best_threshold = 0.7
        best_metrics = None

        for threshold, metrics in metrics_by_threshold.items():
            # F1 = 2 * (precision * recall) / (precision + recall)
            if metrics.precision + metrics.recall > 0:
                f1 = 2 * metrics.precision * metrics.recall / (metrics.precision + metrics.recall)
            else:
                f1 = 0.0

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
                best_metrics = metrics

        if best_metrics is None:
            # Fallback to first threshold
            best_threshold = list(metrics_by_threshold.keys())[0]
            best_metrics = metrics_by_threshold[best_threshold]

        return cls(
            generated_at=datetime.now(),
            input_source=input_source,
            threshold_grid=sorted(metrics_by_threshold.keys()),
            metrics_by_threshold=metrics_by_threshold,
            best_threshold=best_threshold,
            best_metrics=best_metrics,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "input_source": self.input_source,
            "threshold_grid": self.threshold_grid,
            "metrics_by_threshold": {
                str(k): v.to_dict() for k, v in self.metrics_by_threshold.items()
            },
            "best_threshold": self.best_threshold,
            "best_metrics": self.best_metrics.to_dict(),
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Semantic Matcher Evaluation Report",
            "",
            f"**Generated**: {self.generated_at.isoformat()}",
            f"**Input Source**: {self.input_source}",
            "",
            "## Summary",
            "",
            f"- **Best Threshold**: {self.best_threshold}",
            f"- **Best Recall**: {self.best_metrics.recall:.1%}",
            f"- **Best Precision**: {self.best_metrics.precision:.1%}",
            f"- **Best FP Rate**: {self.best_metrics.fp_rate:.1%}",
            "",
            "## Threshold Grid Comparison",
            "",
            "| Threshold | Recall | Precision | FP Rate | TP | FP | NoMatch | Samples |",
            "|-----------|--------|-----------|---------|----|----|---------|---------|",
        ]

        for threshold in self.threshold_grid:
            m = self.metrics_by_threshold[threshold]
            marker = " **" if threshold == self.best_threshold else ""
            marker_end = "**" if threshold == self.best_threshold else ""
            lines.append(
                f"| {marker}{threshold}{marker_end} | {m.recall:.1%} | {m.precision:.1%} | "
                f"{m.fp_rate:.1%} | {m.true_positives} | {m.false_positives} | "
                f"{m.no_matches} | {m.total_samples} |"
            )

        lines.extend([
            "",
            "## Data Quality",
            "",
            f"- **Total Samples (with GT)**: {self.best_metrics.total_samples}",
            f"- **Excluded Samples (no GT)**: {self.best_metrics.excluded_samples}",
            f"- **Exclusion Rate**: {self.best_metrics.exclusion_rate:.1%}",
            "",
            "## Interpretation",
            "",
            "- **Recall** = TP / Total Samples (how many MISSING_OBJECT issues could be rescued)",
            "- **Precision** = TP / (TP + FP) (how accurate the suggestions are)",
            "- **FP Rate** = FP / Total Samples (how often we suggest wrong objects)",
            "",
            "---",
            "",
            "*Auto-adopt is DISABLED. All matches are suggestions only.*",
        ])

        return "\n".join(lines)
