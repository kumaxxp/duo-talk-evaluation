#!/usr/bin/env python3
"""Phase 3.2 ABBA Test: RAG Injection with Bias Mitigation

P1 implementation:
- ABBA order: A → B → B → A per set
- Warm-up run discarded for each condition
- 2 sets (8 total runs, 4 counted per condition)

Metrics:
- total retries (合計)
- prohibited_terms count
- blocked_props count
- latency p95
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
class RunResult:
    """Result for a single run"""
    condition: str  # "A" or "B"
    scenario_name: str
    run_index: int
    is_warmup: bool
    retries: int
    prohibited_terms_count: int
    blocked_props_count: int
    latency_ms: float
    violations: int
    fact_ids: list[str] = field(default_factory=list)


@dataclass
class ABBAResult:
    """Complete ABBA test result"""
    experiment_id: str
    timestamp: str
    runs: list[RunResult]
    summary: dict


def run_single(
    scenario: dict,
    condition: str,
    inject_enabled: bool,
    run_index: int,
    is_warmup: bool = False,
) -> RunResult:
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

    # Create Director
    director = DirectorHybrid(
        llm_client=MockLLMClient(),
        skip_llm_on_static_retry=True,
        rag_enabled=True,
        inject_enabled=inject_enabled,
    )

    # Add blocked props for prop_violation scenario
    if scenario["name"] == "prop_violation":
        director.rag_manager.add_blocked_prop("グラス")

    # Tracking
    class Tracker:
        def __init__(self, base):
            self.base = base
            self.prohibited_count = 0
            self.blocked_count = 0
            self.fact_ids: list[str] = []
            self.latencies: list[float] = []

        def evaluate_response(self, speaker, response, topic, history, turn_number):
            start = time.time()
            result = self.base.evaluate_response(
                speaker=speaker,
                response=response,
                topic=topic,
                history=history,
                turn_number=turn_number,
            )
            self.latencies.append((time.time() - start) * 1000)

            rag_log = self.base.get_last_rag_log()
            if rag_log:
                if "prohibited_terms" in rag_log.triggered_by:
                    self.prohibited_count += 1
                if "blocked_props" in rag_log.triggered_by:
                    self.blocked_count += 1
                for fact in rag_log.facts:
                    self.fact_ids.append(fact.fact_id)

            return result

        def commit_evaluation(self, response, evaluation):
            self.base.commit_evaluation(response, evaluation)

        def reset_for_new_session(self):
            self.base.reset_for_new_session()

        def get_facts_for_injection(self, speaker: str, response_text: str = "", topic: str = "") -> list[dict]:
            return self.base.get_facts_for_injection(speaker, response_text, topic)

    tracker = Tracker(director)

    # Create manager
    manager = create_dialogue_manager(
        backend="ollama",
        model="gemma3:12b",
        director=tracker,
        max_retries=3,
        generation_mode=GenerationMode.TWO_PASS,
    )

    # Run
    num_turns = scenario.get("turns", 4)
    session = DialogueSession(topic=scenario["prompt"], max_turns=num_turns)
    tracker.reset_for_new_session()

    speakers = ["やな", "あゆ"]
    first_speaker = scenario.get("first_speaker", "やな")
    if first_speaker == "あゆ":
        speakers = ["あゆ", "やな"]

    total_retries = 0
    total_violations = 0

    for i in range(num_turns):
        speaker = speakers[i % 2]
        tracker.base.clear_rag_attempts()

        turn = manager.generate_turn(
            speaker_name=speaker,
            topic=scenario["prompt"],
            history=session.get_history(),
            turn_number=i,
        )
        session.add_turn(turn)
        total_retries += turn.retry_count

        # Count violations
        output = turn.output or turn.content
        if speaker == "やな" and re.search(r"です。|ます。|ました。", output):
            total_violations += 1
        if speaker == "あゆ" and re.search(r"やなちゃん|姉ちゃん", output):
            total_violations += 1

    # Calculate p95 latency
    latencies = tracker.latencies
    p95_latency = 0.0
    if latencies:
        sorted_lat = sorted(latencies)
        idx = int(len(sorted_lat) * 0.95)
        p95_latency = sorted_lat[min(idx, len(sorted_lat) - 1)]

    return RunResult(
        condition=condition,
        scenario_name=scenario["name"],
        run_index=run_index,
        is_warmup=is_warmup,
        retries=total_retries,
        prohibited_terms_count=tracker.prohibited_count,
        blocked_props_count=tracker.blocked_count,
        latency_ms=p95_latency,
        violations=total_violations,
        fact_ids=tracker.fact_ids,
    )


def run_abba_test(scenarios: list[dict], sets: int = 2) -> ABBAResult:
    """Run ABBA test with warm-up discarding"""

    print("=" * 70)
    print("Phase 3.2 ABBA Test: RAG Injection with Bias Mitigation")
    print("=" * 70)
    print(f"\nOrder: ABBA x {sets} sets (+ warm-up for each)")
    print("Condition A: inject_enabled=False (observe only)")
    print("Condition B: inject_enabled=True (injection active)")
    print()

    all_runs: list[RunResult] = []
    run_counter = 0

    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario['name']}")
        print(f"Prompt: {scenario['prompt']}")
        print(f"{'='*60}")

        # Warm-up for A
        print("\n[Warm-up A]...", end=" ", flush=True)
        warmup_a = run_single(scenario, "A", inject_enabled=False, run_index=run_counter, is_warmup=True)
        all_runs.append(warmup_a)
        print(f"retries={warmup_a.retries} (discarded)")
        run_counter += 1

        # Warm-up for B
        print("[Warm-up B]...", end=" ", flush=True)
        warmup_b = run_single(scenario, "B", inject_enabled=True, run_index=run_counter, is_warmup=True)
        all_runs.append(warmup_b)
        print(f"retries={warmup_b.retries} (discarded)")
        run_counter += 1

        # ABBA sets
        for set_idx in range(sets):
            print(f"\n[Set {set_idx + 1}]")

            # A → B → B → A
            for cond in ["A", "B", "B", "A"]:
                inject = (cond == "B")
                result = run_single(scenario, cond, inject_enabled=inject, run_index=run_counter, is_warmup=False)
                all_runs.append(result)
                print(f"  {cond}: retries={result.retries}, prohibited={result.prohibited_terms_count}, blocked={result.blocked_props_count}")
                run_counter += 1

    # Calculate summary
    counted_runs = [r for r in all_runs if not r.is_warmup]
    a_runs = [r for r in counted_runs if r.condition == "A"]
    b_runs = [r for r in counted_runs if r.condition == "B"]

    summary = {
        "total_runs": len(counted_runs),
        "condition_a": {
            "runs": len(a_runs),
            "total_retries": sum(r.retries for r in a_runs),
            "prohibited_terms": sum(r.prohibited_terms_count for r in a_runs),
            "blocked_props": sum(r.blocked_props_count for r in a_runs),
            "violations": sum(r.violations for r in a_runs),
            "p95_latency_ms": max(r.latency_ms for r in a_runs) if a_runs else 0,
        },
        "condition_b": {
            "runs": len(b_runs),
            "total_retries": sum(r.retries for r in b_runs),
            "prohibited_terms": sum(r.prohibited_terms_count for r in b_runs),
            "blocked_props": sum(r.blocked_props_count for r in b_runs),
            "violations": sum(r.violations for r in b_runs),
            "p95_latency_ms": max(r.latency_ms for r in b_runs) if b_runs else 0,
        },
        "delta": {
            "retries": sum(r.retries for r in a_runs) - sum(r.retries for r in b_runs),
            "prohibited_terms": sum(r.prohibited_terms_count for r in a_runs) - sum(r.prohibited_terms_count for r in b_runs),
            "blocked_props": sum(r.blocked_props_count for r in a_runs) - sum(r.blocked_props_count for r in b_runs),
            "violations": sum(r.violations for r in a_runs) - sum(r.violations for r in b_runs),
        },
    }

    # Top fact_ids
    fact_counter: dict[str, int] = {}
    for r in b_runs:
        for fid in r.fact_ids:
            fact_counter[fid] = fact_counter.get(fid, 0) + 1
    summary["top_fact_ids"] = sorted(fact_counter.items(), key=lambda x: -x[1])[:5]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ABBAResult(
        experiment_id=f"phase32_abba_{timestamp}",
        timestamp=datetime.now().isoformat(),
        runs=all_runs,
        summary=summary,
    )


def save_results(result: ABBAResult, output_dir: Path = Path("results")):
    """Save ABBA test results"""
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


def generate_report(result: ABBAResult) -> str:
    """Generate markdown report"""
    s = result.summary

    lines = [
        "# Phase 3.2 ABBA Test Report",
        "",
        f"**Experiment ID**: {result.experiment_id}",
        f"**Timestamp**: {result.timestamp}",
        "",
        "## Method",
        "",
        "- Order: ABBA per scenario",
        "- Warm-up: 1 run discarded per condition",
        "- Sets: 2 (8 counted runs total per scenario)",
        "",
        "---",
        "",
        "## Summary (ChatGPT requested format)",
        "",
        "| Metric | A (observe) | B (inject) | Delta |",
        "|--------|:-----------:|:----------:|:-----:|",
        f"| **Total Retries** | {s['condition_a']['total_retries']} | {s['condition_b']['total_retries']} | {s['delta']['retries']:+d} |",
        f"| prohibited_terms | {s['condition_a']['prohibited_terms']} | {s['condition_b']['prohibited_terms']} | {s['delta']['prohibited_terms']:+d} |",
        f"| blocked_props | {s['condition_a']['blocked_props']} | {s['condition_b']['blocked_props']} | {s['delta']['blocked_props']:+d} |",
        f"| Violations | {s['condition_a']['violations']} | {s['condition_b']['violations']} | {s['delta']['violations']:+d} |",
        f"| P95 Latency | {s['condition_a']['p95_latency_ms']:.1f}ms | {s['condition_b']['p95_latency_ms']:.1f}ms | - |",
        "",
        "---",
        "",
        "## Top Fact IDs (Condition B)",
        "",
    ]

    if s.get("top_fact_ids"):
        lines.append("| Fact ID | Count |")
        lines.append("|---------|:-----:|")
        for fid, count in s["top_fact_ids"]:
            lines.append(f"| `{fid[:40]}...` | {count} |")
    else:
        lines.append("No facts injected.")

    lines.extend([
        "",
        "---",
        "",
        "## Recommendation",
        "",
    ])

    delta_ret = s['delta']['retries']
    delta_vio = s['delta']['violations']

    if delta_ret > 0 or delta_vio > 0:
        lines.append("✅ **Injection effective**: Reduced retries or violations.")
    elif delta_ret == 0 and delta_vio == 0:
        lines.append("➖ **No significant difference**: Consider more test runs.")
    else:
        lines.append("⚠️ **Injection increased retries**: Review fact selection.")

    lines.extend([
        "",
        "---",
        "",
        "*Report generated by Phase 3.2 ABBA Test*",
    ])

    return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3.2 ABBA Test")
    parser.add_argument("--sets", type=int, default=2, help="Number of ABBA sets")
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

    result = run_abba_test(scenarios, sets=args.sets)
    save_results(result, Path(args.output))

    # Print summary
    s = result.summary
    print("\n" + "=" * 70)
    print("SUMMARY (for ChatGPT)")
    print("=" * 70)
    print(f"\n{'Metric':<20} {'A (observe)':<12} {'B (inject)':<12} {'Delta':<10}")
    print("-" * 54)
    print(f"{'Total Retries':<20} {s['condition_a']['total_retries']:<12} {s['condition_b']['total_retries']:<12} {s['delta']['retries']:+d}")
    print(f"{'prohibited_terms':<20} {s['condition_a']['prohibited_terms']:<12} {s['condition_b']['prohibited_terms']:<12} {s['delta']['prohibited_terms']:+d}")
    print(f"{'blocked_props':<20} {s['condition_a']['blocked_props']:<12} {s['condition_b']['blocked_props']:<12} {s['delta']['blocked_props']:+d}")
    print(f"{'Violations':<20} {s['condition_a']['violations']:<12} {s['condition_b']['violations']:<12} {s['delta']['violations']:+d}")
    print(f"{'P95 Latency':<20} {s['condition_a']['p95_latency_ms']:.1f}ms{'':<8} {s['condition_b']['p95_latency_ms']:.1f}ms")

    if s.get("top_fact_ids"):
        print("\nTop 3 Fact IDs (B):")
        for fid, count in s["top_fact_ids"][:3]:
            print(f"  {fid[:50]}... ({count})")


if __name__ == "__main__":
    main()
