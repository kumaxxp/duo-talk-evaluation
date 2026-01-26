#!/usr/bin/env python3
"""CLI for Semantic Matcher Evaluation.

Usage:
    python -m experiments.semantic_matcher.eval [OPTIONS]

Examples:
    # Evaluate using results from latest run
    python -m experiments.semantic_matcher.eval --run results/gm_2x2_dev_*/

    # Evaluate with custom threshold grid
    python -m experiments.semantic_matcher.eval --thresholds 0.7,0.8,0.9

    # Output to specific directory
    python -m experiments.semantic_matcher.eval --output results/eval_output/
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .extractor import (
    extract_samples_from_run,
    extract_samples_from_results_dir,
    deduplicate_samples,
    filter_samples_with_gt,
)
from .evaluator import run_evaluation, DEFAULT_THRESHOLD_GRID


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate Semantic Matcher on MISSING_OBJECT samples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--run",
        type=Path,
        help="Path to a specific run directory",
    )

    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Path to results directory (default: results/)",
    )

    parser.add_argument(
        "--pattern",
        type=str,
        default="gm_*",
        help="Glob pattern for run directories (default: gm_*)",
    )

    parser.add_argument(
        "--thresholds",
        type=str,
        help="Comma-separated thresholds to evaluate (default: 0.7,0.75,0.8,0.85,0.9)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output directory (default: results/semantic_eval_<timestamp>/)",
    )

    parser.add_argument(
        "--format",
        choices=["json", "markdown", "both"],
        default="both",
        help="Output format (default: both)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Parse threshold grid
    if args.thresholds:
        threshold_grid = [float(t.strip()) for t in args.thresholds.split(",")]
    else:
        threshold_grid = DEFAULT_THRESHOLD_GRID

    # Setup output directory
    if args.output:
        output_dir = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("results") / f"semantic_eval_{timestamp}"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract samples
    print("=" * 60)
    print("Semantic Matcher Evaluation")
    print("=" * 60)

    if args.run:
        print(f"Extracting samples from: {args.run}")
        samples = extract_samples_from_run(args.run)
        input_source = str(args.run)
    else:
        print(f"Extracting samples from: {args.results_dir} (pattern: {args.pattern})")
        samples = extract_samples_from_results_dir(args.results_dir, args.pattern)
        input_source = f"{args.results_dir}/{args.pattern}"

    # Deduplicate
    samples = deduplicate_samples(samples)
    print(f"Total samples extracted: {len(samples)}")

    # Split by GT availability
    samples_with_gt, samples_without_gt = filter_samples_with_gt(samples)
    print(f"Samples with ground truth: {len(samples_with_gt)}")
    print(f"Samples without ground truth: {len(samples_without_gt)}")

    if not samples_with_gt:
        print("\nNo samples with ground truth found. Cannot compute metrics.")
        print("Samples without GT will be logged for manual review.")

        # Save sample list for review
        sample_list = [
            {
                "sample_id": s.sample_id,
                "query": s.query,
                "scenario": s.scenario,
                "session_id": s.session_id,
                "turn_number": s.turn_number,
                "denied_reason": s.denied_reason,
                "world_objects": list(s.world_objects)[:10],  # Truncate
            }
            for s in samples_without_gt[:50]  # Limit output
        ]

        samples_path = output_dir / "samples_no_gt.json"
        with open(samples_path, "w", encoding="utf-8") as f:
            json.dump(sample_list, f, ensure_ascii=False, indent=2)
        print(f"\nSamples saved to: {samples_path}")

        return 1

    # Run evaluation
    print(f"\nRunning evaluation with thresholds: {threshold_grid}")
    print("-" * 60)

    summary = run_evaluation(
        samples=samples,
        threshold_grid=threshold_grid,
        output_dir=output_dir,
        input_source=input_source,
    )

    # Display results
    print(f"\nBest Threshold: {summary.best_threshold}")
    print(f"Best Recall: {summary.best_metrics.recall:.1%}")
    print(f"Best Precision: {summary.best_metrics.precision:.1%}")
    print(f"Best FP Rate: {summary.best_metrics.fp_rate:.1%}")

    # Print threshold grid
    print("\nThreshold Grid:")
    print("-" * 60)
    print(f"{'Threshold':>10} | {'Recall':>8} | {'Precision':>10} | {'FP Rate':>8} | {'TP':>4} | {'FP':>4}")
    print("-" * 60)

    for threshold in summary.threshold_grid:
        m = summary.metrics_by_threshold[threshold]
        marker = " *" if threshold == summary.best_threshold else "  "
        print(
            f"{threshold:>10.2f}{marker}| {m.recall:>8.1%} | {m.precision:>10.1%} | "
            f"{m.fp_rate:>8.1%} | {m.true_positives:>4} | {m.false_positives:>4}"
        )

    print("-" * 60)
    print(f"* = best threshold by F1 score")

    # Save outputs
    if args.format in ["json", "both"]:
        json_path = output_dir / "summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"\nJSON saved to: {json_path}")

    if args.format in ["markdown", "both"]:
        md_path = output_dir / "summary.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(summary.to_markdown())
        print(f"Markdown saved to: {md_path}")

    # Save sample details
    sample_details = [
        {
            "sample_id": s.sample_id,
            "query": s.query,
            "ground_truth": s.ground_truth,
            "scenario": s.scenario,
            "session_id": s.session_id,
            "turn_number": s.turn_number,
            "speaker": s.speaker,
            "denied_reason": s.denied_reason,
        }
        for s in samples_with_gt
    ]
    details_path = output_dir / "samples.json"
    with open(details_path, "w", encoding="utf-8") as f:
        json.dump(sample_details, f, ensure_ascii=False, indent=2)
    print(f"Samples saved to: {details_path}")

    print(f"\nAudit log: {output_dir / 'audit.jsonl'}")
    print(f"\nEvaluation complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
