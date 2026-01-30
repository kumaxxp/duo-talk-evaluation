#!/usr/bin/env python
"""Load test script for One-Step flow.

Runs concurrent One-Step simulations and measures:
- Success rate
- Latency (min, max, avg, p95)
- Failure modes

Usage:
    python scripts/load_test_one_step.py --concurrent 5 --iterations 3
    python scripts/load_test_one_step.py -n 10 -i 5 --output reports/load_test.csv
"""

import argparse
import asyncio
import csv
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gui_nicegui.adapters import core_adapter, director_adapter
from gui_nicegui.clients import gm_client


@dataclass
class OneStepResult:
    """Result of a single One-Step execution."""

    success: bool
    total_latency_ms: int
    thought_latency_ms: int
    director_thought_latency_ms: int
    utterance_latency_ms: int
    director_speech_latency_ms: int
    gm_latency_ms: int
    error: str | None = None
    thought: str | None = None
    utterance: str | None = None
    director_thought_status: str | None = None
    director_speech_status: str | None = None


@dataclass
class LoadTestResult:
    """Aggregated load test results."""

    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    latencies_ms: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def min_latency(self) -> int:
        return min(self.latencies_ms) if self.latencies_ms else 0

    @property
    def max_latency(self) -> int:
        return max(self.latencies_ms) if self.latencies_ms else 0

    @property
    def avg_latency(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def p95_latency(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]


async def run_one_step(speaker: str, topic: str, session_id: str) -> OneStepResult:
    """Execute a single One-Step flow and measure latency."""
    start_time = time.perf_counter()

    thought_latency = 0
    director_thought_latency = 0
    utterance_latency = 0
    director_speech_latency = 0
    gm_latency = 0

    try:
        # Phase 1: Generate Thought
        thought_result = await core_adapter.generate_thought(
            session_id=session_id,
            speaker=speaker,
            topic=topic,
            timeout=30.0,  # Long timeout for real LLM
            history=[],
        )
        thought_latency = thought_result["latency_ms"]
        thought = thought_result["thought"]

        # Phase 2: Director Check (Thought)
        director_thought = await director_adapter.check(
            stage="thought",
            content=thought,
            context={"speaker": speaker, "topic": topic, "turn_number": 1, "history": []},
            timeout=10.0,
        )
        director_thought_latency = director_thought["latency_ms"]

        # Phase 3: Generate Utterance
        utterance_result = await core_adapter.generate_utterance(
            session_id=session_id,
            speaker=speaker,
            thought=thought,
            timeout=30.0,
            history=[],
        )
        utterance_latency = utterance_result["latency_ms"]
        utterance = utterance_result["speech"]

        # Phase 4: Director Check (Speech)
        director_speech = await director_adapter.check(
            stage="speech",
            content=utterance,
            context={"speaker": speaker, "topic": topic, "turn_number": 1, "history": []},
            timeout=10.0,
        )
        director_speech_latency = director_speech["latency_ms"]

        # Phase 5: GM Step
        gm_result = await gm_client.post_step(
            payload={
                "session_id": session_id,
                "turn_number": 1,
                "speaker": speaker,
                "utterance": utterance,
                "world_state": {},
            },
            timeout=5.0,
        )
        gm_latency = gm_result["latency_ms"]

        total_latency = int((time.perf_counter() - start_time) * 1000)

        return OneStepResult(
            success=True,
            total_latency_ms=total_latency,
            thought_latency_ms=thought_latency,
            director_thought_latency_ms=director_thought_latency,
            utterance_latency_ms=utterance_latency,
            director_speech_latency_ms=director_speech_latency,
            gm_latency_ms=gm_latency,
            thought=thought,
            utterance=utterance,
            director_thought_status=director_thought["status"],
            director_speech_status=director_speech["status"],
        )

    except asyncio.TimeoutError as e:
        total_latency = int((time.perf_counter() - start_time) * 1000)
        return OneStepResult(
            success=False,
            total_latency_ms=total_latency,
            thought_latency_ms=thought_latency,
            director_thought_latency_ms=director_thought_latency,
            utterance_latency_ms=utterance_latency,
            director_speech_latency_ms=director_speech_latency,
            gm_latency_ms=gm_latency,
            error=f"Timeout: {e}",
        )
    except Exception as e:
        total_latency = int((time.perf_counter() - start_time) * 1000)
        return OneStepResult(
            success=False,
            total_latency_ms=total_latency,
            thought_latency_ms=thought_latency,
            director_thought_latency_ms=director_thought_latency,
            utterance_latency_ms=utterance_latency,
            director_speech_latency_ms=director_speech_latency,
            gm_latency_ms=gm_latency,
            error=str(e),
        )


async def run_load_test(
    concurrent: int, iterations: int, speaker: str = "やな", topic: str = "朝の挨拶"
) -> tuple[LoadTestResult, list[OneStepResult]]:
    """Run load test with specified concurrency and iterations."""
    all_results: list[OneStepResult] = []

    print(f"Starting load test: {concurrent} concurrent x {iterations} iterations")
    print(f"Speaker: {speaker}, Topic: {topic}")
    print("-" * 60)

    for iteration in range(iterations):
        print(f"Iteration {iteration + 1}/{iterations}...")

        # Create concurrent tasks
        tasks = []
        for i in range(concurrent):
            session_id = f"load_test_{iteration}_{i}"
            tasks.append(run_one_step(speaker, topic, session_id))

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                all_results.append(
                    OneStepResult(
                        success=False,
                        total_latency_ms=0,
                        thought_latency_ms=0,
                        director_thought_latency_ms=0,
                        utterance_latency_ms=0,
                        director_speech_latency_ms=0,
                        gm_latency_ms=0,
                        error=str(result),
                    )
                )
            else:
                all_results.append(result)

            status = "✓" if (isinstance(result, OneStepResult) and result.success) else "✗"
            latency = result.total_latency_ms if isinstance(result, OneStepResult) else 0
            print(f"  [{status}] Task {i + 1}: {latency}ms")

    # Aggregate results
    successful = [r for r in all_results if r.success]
    failed = [r for r in all_results if not r.success]

    load_result = LoadTestResult(
        total_runs=len(all_results),
        successful_runs=len(successful),
        failed_runs=len(failed),
        success_rate=len(successful) / len(all_results) * 100 if all_results else 0,
        latencies_ms=[r.total_latency_ms for r in successful],
        errors=[r.error for r in failed if r.error],
    )

    return load_result, all_results


def save_csv(results: list[OneStepResult], output_path: Path) -> None:
    """Save results to CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "success",
            "total_latency_ms",
            "thought_latency_ms",
            "director_thought_latency_ms",
            "utterance_latency_ms",
            "director_speech_latency_ms",
            "gm_latency_ms",
            "director_thought_status",
            "director_speech_status",
            "error",
        ])
        for r in results:
            writer.writerow([
                r.success,
                r.total_latency_ms,
                r.thought_latency_ms,
                r.director_thought_latency_ms,
                r.utterance_latency_ms,
                r.director_speech_latency_ms,
                r.gm_latency_ms,
                r.director_thought_status,
                r.director_speech_status,
                r.error,
            ])
    print(f"Results saved to {output_path}")


def save_report(
    load_result: LoadTestResult,
    results: list[OneStepResult],
    concurrent: int,
    iterations: int,
    output_path: Path,
) -> None:
    """Save report to Markdown file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# Load Test Report

**Date**: {timestamp}
**Configuration**: {concurrent} concurrent x {iterations} iterations = {concurrent * iterations} total runs

## Summary

| Metric | Value |
|--------|-------|
| Total Runs | {load_result.total_runs} |
| Successful | {load_result.successful_runs} |
| Failed | {load_result.failed_runs} |
| Success Rate | {load_result.success_rate:.1f}% |

## Latency (successful runs only)

| Metric | Value |
|--------|-------|
| Min | {load_result.min_latency}ms |
| Max | {load_result.max_latency}ms |
| Avg | {load_result.avg_latency:.1f}ms |
| P95 | {load_result.p95_latency:.1f}ms |

## Phase Breakdown (averages)

"""
    if load_result.successful_runs > 0:
        successful = [r for r in results if r.success]
        avg_thought = statistics.mean([r.thought_latency_ms for r in successful])
        avg_dir_thought = statistics.mean([r.director_thought_latency_ms for r in successful])
        avg_utterance = statistics.mean([r.utterance_latency_ms for r in successful])
        avg_dir_speech = statistics.mean([r.director_speech_latency_ms for r in successful])
        avg_gm = statistics.mean([r.gm_latency_ms for r in successful])

        report += f"""| Phase | Avg Latency |
|-------|-------------|
| Thought Generation | {avg_thought:.1f}ms |
| Director (Thought) | {avg_dir_thought:.1f}ms |
| Utterance Generation | {avg_utterance:.1f}ms |
| Director (Speech) | {avg_dir_speech:.1f}ms |
| GM Step | {avg_gm:.1f}ms |

"""

    if load_result.errors:
        report += "## Errors\n\n"
        error_counts: dict[str, int] = {}
        for error in load_result.errors:
            error_counts[error] = error_counts.get(error, 0) + 1
        for error, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            report += f"- ({count}x) {error}\n"
        report += "\n"

    report += """---
*Generated by load_test_one_step.py*
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Load test for One-Step flow")
    parser.add_argument(
        "-n", "--concurrent", type=int, default=5, help="Number of concurrent requests"
    )
    parser.add_argument(
        "-i", "--iterations", type=int, default=3, help="Number of iterations"
    )
    parser.add_argument(
        "--speaker", type=str, default="やな", help="Speaker name"
    )
    parser.add_argument(
        "--topic", type=str, default="朝の挨拶", help="Topic for generation"
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output CSV file path"
    )
    parser.add_argument(
        "--report", type=str, default=None, help="Output report MD file path"
    )

    args = parser.parse_args()

    # Run load test
    load_result, results = asyncio.run(
        run_load_test(args.concurrent, args.iterations, args.speaker, args.topic)
    )

    # Print summary
    print("\n" + "=" * 60)
    print("LOAD TEST SUMMARY")
    print("=" * 60)
    print(f"Total Runs: {load_result.total_runs}")
    print(f"Success Rate: {load_result.success_rate:.1f}%")
    print(f"Latency (ms): min={load_result.min_latency}, max={load_result.max_latency}, "
          f"avg={load_result.avg_latency:.1f}, p95={load_result.p95_latency:.1f}")

    if load_result.errors:
        print(f"\nErrors ({len(load_result.errors)}):")
        for error in set(load_result.errors)[:5]:
            print(f"  - {error}")

    # Save outputs
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_csv(results, output_path)

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        save_report(load_result, results, args.concurrent, args.iterations, report_path)

    # Default: save to reports/
    if not args.output and not args.report:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        reports_dir = PROJECT_ROOT / "reports"
        reports_dir.mkdir(exist_ok=True)
        save_csv(results, reports_dir / f"load_test_{timestamp}.csv")
        save_report(
            load_result, results, args.concurrent, args.iterations,
            reports_dir / f"load_test_{timestamp}.md"
        )


if __name__ == "__main__":
    main()
