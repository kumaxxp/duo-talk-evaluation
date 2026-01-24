#!/usr/bin/env python
"""CI Experiment Runner for duo-talk-evaluation

Runs standardized experiments and outputs CI-friendly results.

Usage:
    python scripts/ci/run_experiments.py [EXPERIMENT] [OPTIONS]

Experiments:
    - quick: Quick smoke test (fastest)
    - director-ab: Director A/B comparison test
    - generation-mode: TWO_PASS vs Two-Phase comparison

Exit codes:
    0: Experiment completed successfully
    1: Experiment failed
    2: Configuration error
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ExperimentResult:
    """Experiment result for CI"""

    experiment: str
    success: bool
    duration_seconds: float
    output_dir: Optional[str]
    summary: dict
    error: Optional[str]


# Project paths
EVALUATION_ROOT = Path(__file__).parent.parent.parent
EXPERIMENTS_DIR = EVALUATION_ROOT / "experiments"
RESULTS_DIR = EVALUATION_ROOT / "results"

# Experiment configurations
EXPERIMENTS = {
    "quick": {
        "script": "quick_test.py",
        "description": "Quick smoke test",
        "timeout": 60,
    },
    "director-ab": {
        "script": "director_ab_test.py",
        "description": "Director A/B comparison",
        "timeout": 300,
        "args": ["--runs", "1"],  # Minimal for CI
    },
    "generation-mode": {
        "script": "generation_mode_comparison.py",
        "description": "TWO_PASS vs Two-Phase comparison",
        "timeout": 300,
        "args": ["--runs", "1"],  # Minimal for CI
    },
    "benchmark": {
        "script": "../scripts/ci/run_benchmark.py",
        "description": "Regression mini-benchmark (Phase 2.3)",
        "timeout": 600,
        "args": ["--scenarios", "all"],
    },
}


def run_experiment(
    experiment_name: str,
    extra_args: Optional[list[str]] = None,
) -> ExperimentResult:
    """Run a single experiment

    Args:
        experiment_name: Name of experiment to run
        extra_args: Additional command-line arguments

    Returns:
        ExperimentResult with status and summary
    """
    if experiment_name not in EXPERIMENTS:
        return ExperimentResult(
            experiment=experiment_name,
            success=False,
            duration_seconds=0.0,
            output_dir=None,
            summary={},
            error=f"Unknown experiment: {experiment_name}",
        )

    config = EXPERIMENTS[experiment_name]
    script_path = EXPERIMENTS_DIR / config["script"]

    if not script_path.exists():
        return ExperimentResult(
            experiment=experiment_name,
            success=False,
            duration_seconds=0.0,
            output_dir=None,
            summary={},
            error=f"Script not found: {script_path}",
        )

    # Build command
    cmd = [sys.executable, str(script_path)]
    if "args" in config:
        cmd.extend(config["args"])
    if extra_args:
        cmd.extend(extra_args)

    print(f"\n{'='*60}")
    print(f"Running: {config['description']}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    start_time = datetime.now()

    try:
        result = subprocess.run(
            cmd,
            cwd=EVALUATION_ROOT,
            capture_output=True,
            text=True,
            timeout=config.get("timeout", 300),
        )
    except subprocess.TimeoutExpired:
        return ExperimentResult(
            experiment=experiment_name,
            success=False,
            duration_seconds=config.get("timeout", 300),
            output_dir=None,
            summary={},
            error="Experiment timed out",
        )
    except Exception as e:
        return ExperimentResult(
            experiment=experiment_name,
            success=False,
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            output_dir=None,
            summary={},
            error=str(e),
        )

    duration = (datetime.now() - start_time).total_seconds()

    # Print output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Find output directory (most recent in results/)
    output_dir = _find_latest_result_dir(experiment_name)

    # Parse summary from output
    summary = _parse_experiment_summary(result.stdout)

    return ExperimentResult(
        experiment=experiment_name,
        success=result.returncode == 0,
        duration_seconds=duration,
        output_dir=str(output_dir) if output_dir else None,
        summary=summary,
        error=None if result.returncode == 0 else f"Exit code: {result.returncode}",
    )


def _find_latest_result_dir(experiment_name: str) -> Optional[Path]:
    """Find the most recent result directory for an experiment"""
    # Map experiment names to result directory patterns
    patterns = {
        "director-ab": "director_ab_*",
        "generation-mode": "generation_mode_*",
    }

    pattern = patterns.get(experiment_name)
    if not pattern:
        return None

    dirs = list(RESULTS_DIR.glob(pattern))
    if not dirs:
        return None

    # Return most recent
    return max(dirs, key=lambda d: d.stat().st_mtime)


def _parse_experiment_summary(output: str) -> dict:
    """Parse summary from experiment output

    Returns:
        Dict with key metrics
    """
    summary = {}

    # Look for common patterns
    import re

    # Format success rate pattern
    match = re.search(r"format[=:]?\s*(\d+\.?\d*)%", output, re.IGNORECASE)
    if match:
        summary["format_success_rate"] = float(match.group(1))

    # Retries pattern
    match = re.search(r"retries[=:]?\s*(\d+\.?\d*)", output, re.IGNORECASE)
    if match:
        summary["avg_retries"] = float(match.group(1))

    return summary


def main():
    parser = argparse.ArgumentParser(description="CI Experiment Runner")
    parser.add_argument(
        "experiment",
        choices=list(EXPERIMENTS.keys()) + ["all"],
        help="Experiment to run",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Additional arguments to pass to experiment",
    )
    args = parser.parse_args()

    # Determine experiments to run
    if args.experiment == "all":
        experiments = list(EXPERIMENTS.keys())
    else:
        experiments = [args.experiment]

    # Run experiments
    results = []
    for exp in experiments:
        result = run_experiment(exp, args.extra_args)
        results.append(result)

    # Output results
    all_success = all(r.success for r in results)

    if args.json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "all_success": all_success,
            "results": [asdict(r) for r in results],
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print("EXPERIMENT SUMMARY")
        print(f"{'='*60}")
        for r in results:
            status = "✅ SUCCESS" if r.success else "❌ FAILED"
            print(f"{r.experiment}: {status} ({r.duration_seconds:.1f}s)")
            if r.output_dir:
                print(f"  Output: {r.output_dir}")
            if r.error:
                print(f"  Error: {r.error}")

    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    main()
