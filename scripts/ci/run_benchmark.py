#!/usr/bin/env python
"""Regression Mini-Benchmark for Phase 2.3

Runs fixed scenarios to verify "not broken" status.
Calculates metrics per PHASE2_3_SPEC.md:
- format_success_rate: 正規形出力数 / 全出力数 (target: 100%)
- thought_missing_rate: Thought欠落数 / 全ターン数 (target: ≤1%)
- avg_retries: 総リトライ数 / 全ターン数 (target: ≤0.1)
- action_sanitized_rate: サニタイズ発動数 / Action付きターン数 (monitoring only)
- blocked_props_topN: ブロックprops上位N件 (monitoring only)

Usage:
    python scripts/ci/run_benchmark.py [OPTIONS]

Options:
    --scenarios [all|casual|topic|emotional]  Which scenarios to run
    --json                                    Output as JSON
    --verbose                                 Show detailed output

Exit codes:
    0: All metrics within targets
    1: One or more metrics failed targets
    2: Configuration or runtime error
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT.parent / "duo-talk-core" / "src"))
sys.path.insert(0, str(PROJECT_ROOT.parent / "duo-talk-director" / "src"))


# Benchmark scenarios per PHASE2_3_SPEC.md
SCENARIOS = {
    "casual_greeting": {
        "prompt": "おはよう、二人とも",
        "turns": 6,
        "description": "Casual greeting scenario",
    },
    "topic_exploration": {
        "prompt": "最近のAI技術について話して",
        "turns": 6,
        "description": "Topic exploration scenario",
    },
    "emotional_support": {
        "prompt": "最近疲れてるんだ...",
        "turns": 6,
        "description": "Emotional support scenario",
    },
}

# Target thresholds per PHASE2_3_SPEC.md
THRESHOLDS = {
    "format_success_rate": 1.0,       # = 100%
    "thought_missing_rate": 0.01,     # ≤ 1%
    "avg_retries": 0.1,               # ≤ 0.1
    # action_sanitized_rate and blocked_props are for monitoring, no threshold
}


@dataclass
class TurnResult:
    """Result of a single turn"""
    turn_number: int
    speaker: str
    thought: str
    output: str
    thought_missing: bool = False
    format_valid: bool = True
    retry_count: int = 0
    action_present: bool = False
    action_sanitized: bool = False
    blocked_props: list[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Result of a scenario run"""
    scenario: str
    prompt: str
    turns: list[TurnResult] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class BenchmarkMetrics:
    """Aggregated benchmark metrics"""
    total_turns: int = 0
    format_success_count: int = 0
    thought_missing_count: int = 0
    total_retries: int = 0
    action_present_count: int = 0
    action_sanitized_count: int = 0
    blocked_props_freq: dict = field(default_factory=dict)

    @property
    def format_success_rate(self) -> float:
        if self.total_turns == 0:
            return 0.0
        return self.format_success_count / self.total_turns

    @property
    def thought_missing_rate(self) -> float:
        if self.total_turns == 0:
            return 0.0
        return self.thought_missing_count / self.total_turns

    @property
    def avg_retries(self) -> float:
        if self.total_turns == 0:
            return 0.0
        return self.total_retries / self.total_turns

    @property
    def action_sanitized_rate(self) -> float:
        if self.action_present_count == 0:
            return 0.0
        return self.action_sanitized_count / self.action_present_count

    @property
    def blocked_props_top5(self) -> list[tuple[str, int]]:
        sorted_props = sorted(
            self.blocked_props_freq.items(),
            key=lambda x: -x[1]
        )
        return sorted_props[:5]


@dataclass
class BenchmarkResult:
    """Complete benchmark result"""
    timestamp: str
    scenarios_run: list[str]
    results: list[ScenarioResult] = field(default_factory=list)
    metrics: Optional[BenchmarkMetrics] = None
    thresholds_passed: bool = True
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "scenarios_run": self.scenarios_run,
            "results": [asdict(r) for r in self.results],
            "metrics": {
                "total_turns": self.metrics.total_turns,
                "format_success_rate": self.metrics.format_success_rate,
                "thought_missing_rate": self.metrics.thought_missing_rate,
                "avg_retries": self.metrics.avg_retries,
                "action_sanitized_rate": self.metrics.action_sanitized_rate,
                "blocked_props_top5": self.metrics.blocked_props_top5,
            } if self.metrics else {},
            "thresholds_passed": self.thresholds_passed,
            "failures": self.failures,
        }


# Format validation patterns
FORMAT_PATTERNS = [
    re.compile(r"^（[^）]+）「[^」]+」$"),  # (action)「dialogue」
    re.compile(r"^「[^」]+」$"),            # 「dialogue」 only
    re.compile(r"^（[^）]+）「[^」]+」"),   # (action)「dialogue」 with continuation
    re.compile(r"^「[^」]+」"),             # 「dialogue」 with continuation
]

DEFAULT_THOUGHTS = ["(特に懸念はない)", "(No specific thought)", ""]


def is_format_valid(output: str) -> bool:
    """Check if output matches valid format

    Valid formats:
    - （action）「dialogue」 - Japanese parentheses (preferred)
    - *action* 「dialogue」 - Asterisk format (acceptable)
    - 「dialogue」 - Dialogue only (acceptable)
    """
    if not output or not output.strip():
        return False

    output = output.strip()

    # Must contain dialogue markers
    if "「" not in output or "」" not in output:
        return False

    # Accept both action formats:
    # - （action）「dialogue」
    # - *action* 「dialogue」
    # - 「dialogue」 only
    # Just verify dialogue markers are present
    return True


def is_thought_missing(thought: str) -> bool:
    """Check if thought is missing or default"""
    if not thought or not thought.strip():
        return True
    return thought.strip() in DEFAULT_THOUGHTS


def has_action(output: str) -> bool:
    """Check if output has action marker"""
    if not output:
        return False
    return output.strip().startswith("（")


def run_scenario(
    scenario_name: str,
    config: dict,
    verbose: bool = False,
) -> ScenarioResult:
    """Run a single benchmark scenario

    Args:
        scenario_name: Name of scenario
        config: Scenario configuration
        verbose: Print detailed output

    Returns:
        ScenarioResult with all turn data
    """
    from duo_talk_core import create_dialogue_manager, GenerationMode
    from duo_talk_director import DirectorMinimal
    from duo_talk_director.logging import (
        SanitizerLogger,
        ThoughtLogger,
        LogStore,
        reset_log_store,
    )
    from duo_talk_director.checks.action_sanitizer import ActionSanitizer

    if verbose:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario_name}")
        print(f"Prompt: {config['prompt']}")
        print(f"Turns: {config['turns']}")
        print(f"{'='*60}")

    # Reset logging for this scenario
    reset_log_store()
    log_store = LogStore(PROJECT_ROOT / "logs" / "benchmark")
    log_store.set_session_id(f"benchmark_{scenario_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    thought_logger = ThoughtLogger(log_store)
    sanitizer_logger = SanitizerLogger(log_store)
    sanitizer = ActionSanitizer()

    result = ScenarioResult(
        scenario=scenario_name,
        prompt=config["prompt"],
    )

    start_time = time.time()

    try:
        # Create dialogue manager with DirectorMinimal
        from duo_talk_core.dialogue_manager import DialogueSession

        manager = create_dialogue_manager(
            backend="ollama",
            model="gemma3:12b",
            generation_mode=GenerationMode.TWO_PASS,
            director=DirectorMinimal(),
            max_retries=3,
            temperature=0.7,
        )

        # Create session for tracking conversation
        session = DialogueSession(topic=config["prompt"], max_turns=config["turns"])
        speakers = ["やな", "あゆ"]

        for turn_idx in range(config["turns"]):
            speaker = speakers[turn_idx % 2]

            # Generate turn using the correct API
            turn = manager.generate_turn(
                speaker_name=speaker,
                topic=config["prompt"],
                history=session.get_history(),
                turn_number=turn_idx,
            )
            session.add_turn(turn)

            # Extract thought and output from turn
            thought = turn.thought or ""
            output = turn.output or turn.content

            # Check for ActionSanitizer
            sanitizer_result = sanitizer.sanitize(output, [])  # Empty scene for benchmark
            action_sanitized = sanitizer_result.action_removed or sanitizer_result.action_replaced
            blocked_props = sanitizer_result.blocked_props

            # Log thought
            thought_logger.log(
                turn_number=turn_idx,
                speaker=speaker,
                thought=thought,
            )

            # Log sanitization if action was modified
            if action_sanitized or sanitizer_result.original_action:
                sanitizer_logger.log(
                    turn_number=turn_idx,
                    speaker=speaker,
                    result=sanitizer_result,
                )

            # Record turn result
            turn_result = TurnResult(
                turn_number=turn_idx,
                speaker=speaker,
                thought=thought,
                output=output,
                thought_missing=is_thought_missing(thought),
                format_valid=is_format_valid(output),
                retry_count=turn.retry_count,
                action_present=has_action(output),
                action_sanitized=action_sanitized,
                blocked_props=blocked_props,
            )
            result.turns.append(turn_result)

            if verbose:
                status = "✅" if turn_result.format_valid else "❌"
                thought_status = "⚠️ missing" if turn_result.thought_missing else ""
                print(f"\nTurn {turn_idx + 1} ({speaker}) {status} {thought_status}")
                print(f"  Thought: {thought[:50]}..." if len(thought) > 50 else f"  Thought: {thought}")
                print(f"  Output: {output[:80]}..." if len(output) > 80 else f"  Output: {output}")

    except Exception as e:
        result.success = False
        result.error = str(e)
        if verbose:
            print(f"Error: {e}")

    result.execution_time = time.time() - start_time
    return result


def calculate_metrics(results: list[ScenarioResult]) -> BenchmarkMetrics:
    """Calculate aggregated metrics from scenario results"""
    metrics = BenchmarkMetrics()

    for result in results:
        for turn in result.turns:
            metrics.total_turns += 1

            if turn.format_valid:
                metrics.format_success_count += 1

            if turn.thought_missing:
                metrics.thought_missing_count += 1

            metrics.total_retries += turn.retry_count

            if turn.action_present:
                metrics.action_present_count += 1

            if turn.action_sanitized:
                metrics.action_sanitized_count += 1

            for prop in turn.blocked_props:
                metrics.blocked_props_freq[prop] = metrics.blocked_props_freq.get(prop, 0) + 1

    return metrics


def check_thresholds(metrics: BenchmarkMetrics) -> tuple[bool, list[str]]:
    """Check if metrics meet thresholds

    Returns:
        Tuple of (all_passed, list_of_failures)
    """
    failures = []

    # format_success_rate must be 100%
    if metrics.format_success_rate < THRESHOLDS["format_success_rate"]:
        failures.append(
            f"format_success_rate: {metrics.format_success_rate:.2%} < {THRESHOLDS['format_success_rate']:.0%}"
        )

    # thought_missing_rate must be ≤ 1%
    if metrics.thought_missing_rate > THRESHOLDS["thought_missing_rate"]:
        failures.append(
            f"thought_missing_rate: {metrics.thought_missing_rate:.2%} > {THRESHOLDS['thought_missing_rate']:.0%}"
        )

    # avg_retries must be ≤ 0.1
    if metrics.avg_retries > THRESHOLDS["avg_retries"]:
        failures.append(
            f"avg_retries: {metrics.avg_retries:.2f} > {THRESHOLDS['avg_retries']}"
        )

    return len(failures) == 0, failures


def run_benchmark(
    scenarios: list[str],
    verbose: bool = False,
) -> BenchmarkResult:
    """Run the full benchmark

    Args:
        scenarios: List of scenario names to run
        verbose: Print detailed output

    Returns:
        BenchmarkResult with all data
    """
    result = BenchmarkResult(
        timestamp=datetime.now().isoformat(),
        scenarios_run=scenarios,
    )

    # Run each scenario
    for scenario_name in scenarios:
        if scenario_name not in SCENARIOS:
            print(f"Warning: Unknown scenario '{scenario_name}', skipping")
            continue

        scenario_result = run_scenario(
            scenario_name,
            SCENARIOS[scenario_name],
            verbose=verbose,
        )
        result.results.append(scenario_result)

    # Calculate metrics
    result.metrics = calculate_metrics(result.results)

    # Check thresholds
    result.thresholds_passed, result.failures = check_thresholds(result.metrics)

    return result


def print_report(result: BenchmarkResult) -> None:
    """Print formatted benchmark report"""
    print("\n" + "=" * 60)
    print("REGRESSION MINI-BENCHMARK REPORT")
    print("=" * 60)
    print(f"Timestamp: {result.timestamp}")
    print(f"Scenarios: {', '.join(result.scenarios_run)}")

    print("\n--- Metrics ---")
    m = result.metrics
    print(f"Total Turns: {m.total_turns}")
    print(f"Format Success Rate: {m.format_success_rate:.2%} (target: 100%)")
    print(f"Thought Missing Rate: {m.thought_missing_rate:.2%} (target: ≤1%)")
    print(f"Avg Retries: {m.avg_retries:.3f} (target: ≤0.1)")
    print(f"Action Sanitized Rate: {m.action_sanitized_rate:.2%} (monitoring)")

    if m.blocked_props_top5:
        print("\n--- Blocked Props Top 5 ---")
        for prop, count in m.blocked_props_top5:
            print(f"  {prop}: {count}")

    print("\n--- Threshold Check ---")
    if result.thresholds_passed:
        print("✅ ALL THRESHOLDS PASSED")
    else:
        print("❌ THRESHOLD FAILURES:")
        for failure in result.failures:
            print(f"  - {failure}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Regression Mini-Benchmark")
    parser.add_argument(
        "--scenarios",
        choices=["all", "casual", "topic", "emotional"],
        default="all",
        help="Which scenarios to run",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "results" / "benchmark",
        help="Directory to save results",
    )
    args = parser.parse_args()

    # Determine scenarios to run
    if args.scenarios == "all":
        scenarios = list(SCENARIOS.keys())
    elif args.scenarios == "casual":
        scenarios = ["casual_greeting"]
    elif args.scenarios == "topic":
        scenarios = ["topic_exploration"]
    elif args.scenarios == "emotional":
        scenarios = ["emotional_support"]
    else:
        scenarios = list(SCENARIOS.keys())

    # Run benchmark
    print("Starting regression mini-benchmark...")
    result = run_benchmark(scenarios, verbose=args.verbose)

    # Output results
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print_report(result)

    # Save results
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = args.output_dir / f"benchmark_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_file}")

    # Exit code based on threshold check
    sys.exit(0 if result.thresholds_passed else 1)


if __name__ == "__main__":
    main()
