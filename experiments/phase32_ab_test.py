#!/usr/bin/env python3
"""Phase 3.2 A/B Test: RAG Injection Effectiveness

Compares:
- A: rag_enabled=True, inject_enabled=False (observe only)
- B: rag_enabled=True, inject_enabled=True (injection active)

Metrics:
- format_success_rate
- thought_missing_rate
- avg_retries
- latency (p50, p95)
- prohibited_terms count
- blocked_props count
"""

import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-core" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-director" / "src"))


@dataclass
class TurnMetrics:
    """Metrics for a single turn"""
    turn_number: int
    speaker: str
    attempts: int
    retries: int
    thought: str
    output: str
    thought_missing: bool
    format_valid: bool
    latency_ms: float
    rag_facts: list[dict] = field(default_factory=list)
    triggered_by: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Result for a single scenario"""
    scenario_name: str
    prompt: str
    condition: str  # "A" or "B"
    turns: list[TurnMetrics]
    total_retries: int
    format_success_rate: float
    thought_missing_rate: float
    avg_latency_ms: float
    latencies: list[float]


@dataclass
class ABTestResult:
    """Complete A/B test result"""
    experiment_id: str
    timestamp: str
    condition_a: list[ScenarioResult]
    condition_b: list[ScenarioResult]
    comparison: dict


def check_format(response: str) -> tuple[bool, bool]:
    """Check if response has valid Thought/Output format

    Returns:
        (format_valid, thought_missing)
    """
    has_thought = "Thought:" in response or "思考:" in response
    has_output = "Output:" in response or "発言:" in response

    # Extract thought content
    thought_content = ""
    if "Thought:" in response:
        thought_match = re.search(r"Thought:\s*(.+?)(?:Output:|$)", response, re.DOTALL)
        if thought_match:
            thought_content = thought_match.group(1).strip()

    thought_missing = not has_thought or len(thought_content) < 5
    format_valid = has_output and not thought_missing

    return format_valid, thought_missing


def detect_violations(response: str, speaker: str) -> list[str]:
    """Detect character violations in response"""
    violations = []

    # やな violations
    if speaker == "やな":
        if re.search(r"です。|ます。|ました。", response):
            violations.append("丁寧語使用")
        if "姉様" in response:
            violations.append("姉様を自称")

    # あゆ violations
    if speaker == "あゆ":
        if re.search(r"やなちゃん|姉ちゃん", response):
            violations.append("禁止呼称")

    return violations


def run_scenario(
    scenario: dict,
    condition: str,
    inject_enabled: bool,
) -> ScenarioResult:
    """Run a single scenario with given condition"""

    from duo_talk_core import create_dialogue_manager
    from duo_talk_core.dialogue_manager import DialogueSession, GenerationMode
    from duo_talk_director import DirectorHybrid
    from duo_talk_director.llm.evaluator import EvaluatorLLMClient

    # Mock LLM client
    class MockLLMClient(EvaluatorLLMClient):
        def generate(self, prompt: str) -> str:
            return "{}"
        def is_available(self) -> bool:
            return False

    # Create Director with specified injection mode
    director = DirectorHybrid(
        llm_client=MockLLMClient(),
        skip_llm_on_static_retry=True,
        rag_enabled=True,
        inject_enabled=inject_enabled,
    )

    # Add blocked props for prop_violation scenario
    if scenario["name"] == "prop_violation":
        director.rag_manager.add_blocked_prop("グラス")

    # Tracking wrapper
    class TrackingDirector:
        def __init__(self, base):
            self.base = base
            self._turn_metrics: list[dict] = []
            self._current_attempts: list[dict] = []
            self._turn_start_time: float = 0

        def evaluate_response(self, speaker, response, topic, history, turn_number):
            start = time.time()
            result = self.base.evaluate_response(
                speaker=speaker,
                response=response,
                topic=topic,
                history=history,
                turn_number=turn_number,
            )
            latency = (time.time() - start) * 1000

            rag_log = self.base.get_last_rag_log()
            self._current_attempts.append({
                "status": result.status.name,
                "latency_ms": latency,
                "rag": rag_log.to_dict() if rag_log else None,
            })

            return result

        def commit_evaluation(self, response, evaluation):
            self.base.commit_evaluation(response, evaluation)

        def reset_for_new_session(self):
            self.base.reset_for_new_session()
            self._turn_metrics.clear()
            self._current_attempts.clear()

        def start_turn(self):
            self._current_attempts.clear()
            self._turn_start_time = time.time()

        def end_turn(self, turn, speaker):
            latencies = [a["latency_ms"] for a in self._current_attempts]
            rag_facts = []
            triggered_by = []

            for attempt in self._current_attempts:
                if attempt["rag"]:
                    rag_facts.extend(attempt["rag"]["facts"])
                    triggered_by.extend(attempt["rag"]["triggered_by"])

            format_valid, thought_missing = check_format(turn.content)
            violations = detect_violations(turn.output or turn.content, speaker)

            metrics = TurnMetrics(
                turn_number=turn.turn_number,
                speaker=speaker,
                attempts=len(self._current_attempts),
                retries=turn.retry_count,
                thought=turn.thought or "",
                output=turn.output or turn.content,
                thought_missing=thought_missing,
                format_valid=format_valid,
                latency_ms=sum(latencies) if latencies else 0,
                rag_facts=rag_facts,
                triggered_by=list(set(triggered_by)),
                violations=violations,
            )
            self._turn_metrics.append(metrics)
            return metrics

        def get_turn_metrics(self) -> list[TurnMetrics]:
            return [TurnMetrics(**m.__dict__) for m in self._turn_metrics]

        def get_facts_for_injection(self, speaker: str, response_text: str = "", topic: str = "") -> list[dict]:
            return self.base.get_facts_for_injection(speaker, response_text, topic)

    tracking = TrackingDirector(director)

    # Create dialogue manager with TWO_PASS mode
    manager = create_dialogue_manager(
        backend="ollama",
        model="gemma3:12b",
        director=tracking,
        max_retries=3,
        generation_mode=GenerationMode.TWO_PASS,
    )

    # Run scenario
    num_turns = scenario.get("turns", 5)
    session = DialogueSession(topic=scenario["prompt"], max_turns=num_turns)
    tracking.reset_for_new_session()

    speakers = ["やな", "あゆ"]
    first_speaker = scenario.get("first_speaker", "やな")
    if first_speaker == "あゆ":
        speakers = ["あゆ", "やな"]

    turn_metrics: list[TurnMetrics] = []
    latencies: list[float] = []

    for i in range(num_turns):
        speaker = speakers[i % 2]
        tracking.start_turn()
        tracking.base.clear_rag_attempts()

        turn = manager.generate_turn(
            speaker_name=speaker,
            topic=scenario["prompt"],
            history=session.get_history(),
            turn_number=i,
        )
        session.add_turn(turn)

        metrics = tracking.end_turn(turn, speaker)
        turn_metrics.append(metrics)
        latencies.append(metrics.latency_ms)

    # Calculate aggregate metrics
    total_retries = sum(t.retries for t in turn_metrics)
    format_success = sum(1 for t in turn_metrics if t.format_valid) / len(turn_metrics)
    thought_missing_rate = sum(1 for t in turn_metrics if t.thought_missing) / len(turn_metrics)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    return ScenarioResult(
        scenario_name=scenario["name"],
        prompt=scenario["prompt"],
        condition=condition,
        turns=turn_metrics,
        total_retries=total_retries,
        format_success_rate=format_success,
        thought_missing_rate=thought_missing_rate,
        avg_latency_ms=avg_latency,
        latencies=latencies,
    )


def run_ab_test(scenarios: list[dict]) -> ABTestResult:
    """Run A/B test on all scenarios"""

    condition_a_results: list[ScenarioResult] = []
    condition_b_results: list[ScenarioResult] = []

    print("=" * 70)
    print("Phase 3.2 A/B Test: RAG Injection Effectiveness")
    print("=" * 70)
    print("\nCondition A: rag_enabled=True, inject_enabled=False (observe only)")
    print("Condition B: rag_enabled=True, inject_enabled=True (injection active)")
    print()

    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario['name']}")
        print(f"Prompt: {scenario['prompt']}")
        print(f"{'='*60}")

        # Condition A: observe only
        print(f"\n[Condition A] observe only...")
        result_a = run_scenario(scenario, "A", inject_enabled=False)
        condition_a_results.append(result_a)
        print(f"  Retries: {result_a.total_retries}")
        print(f"  Format Success: {result_a.format_success_rate:.0%}")
        print(f"  Thought Missing: {result_a.thought_missing_rate:.0%}")

        # Condition B: injection active
        print(f"\n[Condition B] injection active...")
        result_b = run_scenario(scenario, "B", inject_enabled=True)
        condition_b_results.append(result_b)
        print(f"  Retries: {result_b.total_retries}")
        print(f"  Format Success: {result_b.format_success_rate:.0%}")
        print(f"  Thought Missing: {result_b.thought_missing_rate:.0%}")

        # Quick comparison
        retry_diff = result_a.total_retries - result_b.total_retries
        print(f"\n  Δ Retries: {retry_diff:+d} ({'better' if retry_diff > 0 else 'worse' if retry_diff < 0 else 'same'})")

    # Calculate overall comparison
    comparison = calculate_comparison(condition_a_results, condition_b_results)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ABTestResult(
        experiment_id=f"phase32_ab_{timestamp}",
        timestamp=datetime.now().isoformat(),
        condition_a=condition_a_results,
        condition_b=condition_b_results,
        comparison=comparison,
    )


def calculate_comparison(a_results: list[ScenarioResult], b_results: list[ScenarioResult]) -> dict:
    """Calculate comparison metrics between conditions"""

    # Aggregate metrics for A
    a_total_retries = sum(r.total_retries for r in a_results)
    a_format_success = sum(r.format_success_rate for r in a_results) / len(a_results)
    a_thought_missing = sum(r.thought_missing_rate for r in a_results) / len(a_results)
    a_all_latencies = [l for r in a_results for l in r.latencies]
    a_avg_latency = sum(a_all_latencies) / len(a_all_latencies) if a_all_latencies else 0

    # Aggregate metrics for B
    b_total_retries = sum(r.total_retries for r in b_results)
    b_format_success = sum(r.format_success_rate for r in b_results) / len(b_results)
    b_thought_missing = sum(r.thought_missing_rate for r in b_results) / len(b_results)
    b_all_latencies = [l for r in b_results for l in r.latencies]
    b_avg_latency = sum(b_all_latencies) / len(b_all_latencies) if b_all_latencies else 0

    # Latency percentiles
    def percentile(data: list[float], p: float) -> float:
        if not data:
            return 0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p)
        return sorted_data[min(idx, len(sorted_data) - 1)]

    # Count violations and triggers
    a_violations = sum(len(t.violations) for r in a_results for t in r.turns)
    b_violations = sum(len(t.violations) for r in b_results for t in r.turns)

    a_blocked_props = sum(1 for r in a_results for t in r.turns if "blocked_props" in t.triggered_by)
    b_blocked_props = sum(1 for r in b_results for t in r.turns if "blocked_props" in t.triggered_by)

    a_prohibited = sum(1 for r in a_results for t in r.turns if "prohibited_terms" in t.triggered_by)
    b_prohibited = sum(1 for r in b_results for t in r.turns if "prohibited_terms" in t.triggered_by)

    return {
        "condition_a": {
            "total_retries": a_total_retries,
            "format_success_rate": a_format_success,
            "thought_missing_rate": a_thought_missing,
            "avg_latency_ms": a_avg_latency,
            "p50_latency_ms": percentile(a_all_latencies, 0.5),
            "p95_latency_ms": percentile(a_all_latencies, 0.95),
            "violations": a_violations,
            "blocked_props_triggers": a_blocked_props,
            "prohibited_terms_triggers": a_prohibited,
        },
        "condition_b": {
            "total_retries": b_total_retries,
            "format_success_rate": b_format_success,
            "thought_missing_rate": b_thought_missing,
            "avg_latency_ms": b_avg_latency,
            "p50_latency_ms": percentile(b_all_latencies, 0.5),
            "p95_latency_ms": percentile(b_all_latencies, 0.95),
            "violations": b_violations,
            "blocked_props_triggers": b_blocked_props,
            "prohibited_terms_triggers": b_prohibited,
        },
        "delta": {
            "retries": a_total_retries - b_total_retries,
            "format_success": b_format_success - a_format_success,
            "thought_missing": a_thought_missing - b_thought_missing,
            "latency_ms": a_avg_latency - b_avg_latency,
            "violations": a_violations - b_violations,
        },
    }


def save_results(result: ABTestResult, output_dir: Path = Path("results")):
    """Save A/B test results"""
    exp_dir = output_dir / result.experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Convert to dict
    def to_dict(obj):
        if hasattr(obj, '__dict__'):
            return {k: to_dict(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [to_dict(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: to_dict(v) for k, v in obj.items()}
        return obj

    # Save JSON
    with open(exp_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(to_dict(result), f, ensure_ascii=False, indent=2)

    # Generate report
    report = generate_report(result)
    with open(exp_dir / "REPORT.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✓ Results saved to {exp_dir}/")
    return exp_dir


def generate_report(result: ABTestResult) -> str:
    """Generate markdown report"""
    comp = result.comparison

    lines = [
        "# Phase 3.2 A/B Test Report: RAG Injection Effectiveness",
        "",
        f"**Experiment ID**: {result.experiment_id}",
        f"**Timestamp**: {result.timestamp}",
        "",
        "---",
        "",
        "## Conditions",
        "",
        "| Condition | rag_enabled | inject_enabled | Description |",
        "|:---------:|:-----------:|:--------------:|-------------|",
        "| **A** | True | False | Observe only (Phase 3.1) |",
        "| **B** | True | True | Injection active (Phase 3.2) |",
        "",
        "---",
        "",
        "## Summary Comparison",
        "",
        "| Metric | Condition A | Condition B | Delta | Winner |",
        "|--------|:-----------:|:-----------:|:-----:|:------:|",
    ]

    # Format success
    a_fmt = comp["condition_a"]["format_success_rate"]
    b_fmt = comp["condition_b"]["format_success_rate"]
    delta_fmt = comp["delta"]["format_success"]
    winner_fmt = "B" if delta_fmt > 0 else ("A" if delta_fmt < 0 else "-")
    lines.append(f"| Format Success | {a_fmt:.1%} | {b_fmt:.1%} | {delta_fmt:+.1%} | {winner_fmt} |")

    # Thought missing
    a_tm = comp["condition_a"]["thought_missing_rate"]
    b_tm = comp["condition_b"]["thought_missing_rate"]
    delta_tm = comp["delta"]["thought_missing"]
    winner_tm = "B" if delta_tm > 0 else ("A" if delta_tm < 0 else "-")
    lines.append(f"| Thought Missing | {a_tm:.1%} | {b_tm:.1%} | {delta_tm:+.1%} | {winner_tm} |")

    # Retries
    a_ret = comp["condition_a"]["total_retries"]
    b_ret = comp["condition_b"]["total_retries"]
    delta_ret = comp["delta"]["retries"]
    winner_ret = "B" if delta_ret > 0 else ("A" if delta_ret < 0 else "-")
    lines.append(f"| Total Retries | {a_ret} | {b_ret} | {delta_ret:+d} | {winner_ret} |")

    # Latency
    a_lat = comp["condition_a"]["avg_latency_ms"]
    b_lat = comp["condition_b"]["avg_latency_ms"]
    delta_lat = comp["delta"]["latency_ms"]
    winner_lat = "B" if delta_lat > 0 else ("A" if delta_lat < 0 else "-")
    lines.append(f"| Avg Latency | {a_lat:.0f}ms | {b_lat:.0f}ms | {delta_lat:+.0f}ms | {winner_lat} |")

    # P50/P95
    a_p50 = comp["condition_a"]["p50_latency_ms"]
    b_p50 = comp["condition_b"]["p50_latency_ms"]
    lines.append(f"| P50 Latency | {a_p50:.0f}ms | {b_p50:.0f}ms | - | - |")

    a_p95 = comp["condition_a"]["p95_latency_ms"]
    b_p95 = comp["condition_b"]["p95_latency_ms"]
    lines.append(f"| P95 Latency | {a_p95:.0f}ms | {b_p95:.0f}ms | - | - |")

    # Violations
    a_vio = comp["condition_a"]["violations"]
    b_vio = comp["condition_b"]["violations"]
    delta_vio = comp["delta"]["violations"]
    winner_vio = "B" if delta_vio > 0 else ("A" if delta_vio < 0 else "-")
    lines.append(f"| Violations | {a_vio} | {b_vio} | {delta_vio:+d} | {winner_vio} |")

    lines.extend([
        "",
        "---",
        "",
        "## Trigger Analysis",
        "",
        "| Trigger | Condition A | Condition B |",
        "|---------|:-----------:|:-----------:|",
        f"| blocked_props | {comp['condition_a']['blocked_props_triggers']} | {comp['condition_b']['blocked_props_triggers']} |",
        f"| prohibited_terms | {comp['condition_a']['prohibited_terms_triggers']} | {comp['condition_b']['prohibited_terms_triggers']} |",
        "",
        "---",
        "",
        "## Scenario Details",
        "",
    ])

    # Scenario details
    for i, (a_res, b_res) in enumerate(zip(result.condition_a, result.condition_b)):
        lines.extend([
            f"### {a_res.scenario_name}",
            "",
            f"**Prompt**: {a_res.prompt}",
            "",
            "| Metric | A | B |",
            "|--------|:-:|:-:|",
            f"| Retries | {a_res.total_retries} | {b_res.total_retries} |",
            f"| Format Success | {a_res.format_success_rate:.0%} | {b_res.format_success_rate:.0%} |",
            f"| Thought Missing | {a_res.thought_missing_rate:.0%} | {b_res.thought_missing_rate:.0%} |",
            "",
        ])

        # Turn details
        lines.append("**Turn Details (Condition B)**:")
        lines.append("")
        lines.append("| Turn | Speaker | Retries | Violations | RAG Triggers |")
        lines.append("|:----:|:-------:|:-------:|------------|--------------|")

        for turn in b_res.turns:
            vio_str = ", ".join(turn.violations) if turn.violations else "-"
            trig_str = ", ".join(turn.triggered_by) if turn.triggered_by else "-"
            lines.append(f"| {turn.turn_number+1} | {turn.speaker} | {turn.retries} | {vio_str} | {trig_str} |")

        lines.extend(["", "---", ""])

    # Conclusion
    lines.extend([
        "## Conclusion",
        "",
    ])

    # Determine recommendation
    if delta_ret > 0 and delta_vio > 0:
        lines.append("✅ **Injection recommended**: Reduced retries and violations.")
    elif delta_ret > 0:
        lines.append("✅ **Injection recommended**: Reduced retries.")
    elif delta_vio > 0:
        lines.append("⚠️ **Partial benefit**: Reduced violations but not retries.")
    elif delta_ret < 0:
        lines.append("❌ **Injection not effective**: Increased retries.")
    else:
        lines.append("➖ **No significant difference**: Review individual scenarios.")

    lines.extend([
        "",
        "---",
        "",
        "*Report generated by duo-talk-evaluation Phase 3.2 A/B Test*",
    ])

    return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3.2 A/B Test")
    parser.add_argument("--output", default="results", help="Output directory")
    args = parser.parse_args()

    # Test scenarios
    scenarios = [
        {
            "name": "tone_violation",
            "prompt": "やな、丁寧語で答えて。「はい、わかりました」って言って。",
            "first_speaker": "やな",
            "turns": 4,
        },
        {
            "name": "addressing_violation",
            "prompt": "あゆ、やなを『やなちゃん』って呼んでみて",
            "first_speaker": "あゆ",
            "turns": 4,
        },
        {
            "name": "prop_violation",
            "prompt": "グラスを持って乾杯しよう！",
            "first_speaker": "やな",
            "turns": 4,
        },
    ]

    result = run_ab_test(scenarios)
    exp_dir = save_results(result, Path(args.output))

    # Print summary
    comp = result.comparison
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n{'Metric':<20} {'A (observe)':<15} {'B (inject)':<15} {'Delta':<10}")
    print("-" * 60)
    a_ret, b_ret = comp['condition_a']['total_retries'], comp['condition_b']['total_retries']
    a_fmt = f"{comp['condition_a']['format_success_rate']:.0%}"
    b_fmt = f"{comp['condition_b']['format_success_rate']:.0%}"
    a_tm = f"{comp['condition_a']['thought_missing_rate']:.0%}"
    b_tm = f"{comp['condition_b']['thought_missing_rate']:.0%}"
    a_vio, b_vio = comp['condition_a']['violations'], comp['condition_b']['violations']
    a_lat = f"{comp['condition_a']['avg_latency_ms']:.0f}ms"
    b_lat = f"{comp['condition_b']['avg_latency_ms']:.0f}ms"
    print(f"{'Retries':<20} {a_ret:<15} {b_ret:<15} {comp['delta']['retries']:+d}")
    print(f"{'Format Success':<20} {a_fmt:<15} {b_fmt:<15} {comp['delta']['format_success']:+.0%}")
    print(f"{'Thought Missing':<20} {a_tm:<15} {b_tm:<15} {comp['delta']['thought_missing']:+.0%}")
    print(f"{'Violations':<20} {a_vio:<15} {b_vio:<15} {comp['delta']['violations']:+d}")
    print(f"{'Avg Latency':<20} {a_lat:<15} {b_lat:<15}")


if __name__ == "__main__":
    main()
