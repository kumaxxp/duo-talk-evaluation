#!/usr/bin/env python
"""CI Test Runner for duo-talk-evaluation

Runs all tests across the ecosystem and reports results in CI-friendly format.

Usage:
    python scripts/ci/run_tests.py [--component COMPONENT] [--coverage]

Components:
    - all: Run all tests (default)
    - core: duo-talk-core tests only
    - director: duo-talk-director tests only
    - evaluation: duo-talk-evaluation tests only

Exit codes:
    0: All tests passed
    1: Tests failed
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
class TestResult:
    """Test run result"""

    component: str
    passed: int
    failed: int
    errors: int
    skipped: int
    coverage: Optional[float]
    duration_seconds: float
    success: bool


@dataclass
class CIReport:
    """CI test report"""

    timestamp: str
    total_passed: int
    total_failed: int
    total_errors: int
    all_success: bool
    results: list[TestResult]


# Project paths
ECOSYSTEM_ROOT = Path(__file__).parent.parent.parent.parent
COMPONENTS = {
    "core": ECOSYSTEM_ROOT / "duo-talk-core",
    "director": ECOSYSTEM_ROOT / "duo-talk-director",
    "evaluation": ECOSYSTEM_ROOT / "duo-talk-evaluation",
    "gm": ECOSYSTEM_ROOT / "duo-talk-gm",
}


def run_pytest(
    component_path: Path,
    coverage: bool = False,
) -> TestResult:
    """Run pytest for a component

    Args:
        component_path: Path to component directory
        coverage: Whether to run with coverage

    Returns:
        TestResult with pass/fail counts
    """
    component_name = component_path.name.replace("duo-talk-", "")
    start_time = datetime.now()

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-q",
    ]

    if coverage:
        cmd.extend([
            f"--cov=src/{component_path.name.replace('-', '_')}",
            "--cov-report=term-missing",
            "--cov-fail-under=70",
        ])

    try:
        result = subprocess.run(
            cmd,
            cwd=component_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return TestResult(
            component=component_name,
            passed=0,
            failed=0,
            errors=1,
            skipped=0,
            coverage=None,
            duration_seconds=300.0,
            success=False,
        )

    duration = (datetime.now() - start_time).total_seconds()

    # Parse pytest output
    passed, failed, errors, skipped = _parse_pytest_output(result.stdout + result.stderr)
    coverage_pct = _parse_coverage(result.stdout) if coverage else None

    return TestResult(
        component=component_name,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        coverage=coverage_pct,
        duration_seconds=duration,
        success=result.returncode == 0,
    )


def _parse_pytest_output(output: str) -> tuple[int, int, int, int]:
    """Parse pytest summary line

    Returns:
        Tuple of (passed, failed, errors, skipped)
    """
    import re

    # Match patterns like "34 passed", "2 failed", etc.
    passed = 0
    failed = 0
    errors = 0
    skipped = 0

    patterns = {
        "passed": r"(\d+) passed",
        "failed": r"(\d+) failed",
        "error": r"(\d+) error",
        "skipped": r"(\d+) skipped",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            value = int(match.group(1))
            if key == "passed":
                passed = value
            elif key == "failed":
                failed = value
            elif key == "error":
                errors = value
            elif key == "skipped":
                skipped = value

    return passed, failed, errors, skipped


def _parse_coverage(output: str) -> Optional[float]:
    """Parse coverage percentage from pytest-cov output

    Returns:
        Coverage percentage or None
    """
    import re

    # Match "TOTAL ... XX%" pattern
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)%", output)
    if match:
        return float(match.group(1))

    return None


def run_all_tests(
    components: list[str],
    coverage: bool = False,
    json_output: bool = False,
) -> CIReport:
    """Run tests for all specified components

    Args:
        components: List of component names to test
        coverage: Whether to run with coverage
        json_output: If True, status messages go to stderr (for clean JSON stdout)

    Returns:
        CIReport with all results
    """
    results = []
    # Use stderr for status when JSON output is requested
    out = sys.stderr if json_output else sys.stdout

    for comp in components:
        if comp not in COMPONENTS:
            print(f"Unknown component: {comp}", file=sys.stderr)
            continue

        print(f"\n{'='*60}", file=out)
        print(f"Running tests for: {comp}", file=out)
        print(f"{'='*60}", file=out)

        result = run_pytest(COMPONENTS[comp], coverage=coverage)
        results.append(result)

        status = "✅ PASSED" if result.success else "❌ FAILED"
        print(f"\n{comp}: {status}", file=out)
        print(f"  Passed: {result.passed}, Failed: {result.failed}, Errors: {result.errors}", file=out)
        if result.coverage is not None:
            print(f"  Coverage: {result.coverage:.1f}%", file=out)

    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    total_errors = sum(r.errors for r in results)
    all_success = all(r.success for r in results)

    return CIReport(
        timestamp=datetime.now().isoformat(),
        total_passed=total_passed,
        total_failed=total_failed,
        total_errors=total_errors,
        all_success=all_success,
        results=results,
    )


def main():
    parser = argparse.ArgumentParser(description="CI Test Runner")
    parser.add_argument(
        "--component",
        choices=["all", "core", "director", "evaluation", "gm"],
        default="all",
        help="Component to test",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run with coverage",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    # Determine components to test
    if args.component == "all":
        components = list(COMPONENTS.keys())
    else:
        components = [args.component]

    # Run tests
    report = run_all_tests(components, coverage=args.coverage, json_output=args.json)

    # Output results
    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Total Passed: {report.total_passed}")
        print(f"Total Failed: {report.total_failed}")
        print(f"Total Errors: {report.total_errors}")
        print(f"Status: {'✅ ALL PASSED' if report.all_success else '❌ FAILED'}")

    # Exit with appropriate code
    sys.exit(0 if report.all_success else 1)


if __name__ == "__main__":
    main()
