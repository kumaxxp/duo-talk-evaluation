#!/usr/bin/env python3
"""RAG Observation Test (Phase 3.1)

Runs dialogue with RAG enabled (observe-only) and collects:
- RAG latency (p50/p95)
- Facts per turn
- Rejected responses with RAG facts
"""

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project roots to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-core" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-director" / "src"))


@dataclass
class RAGObservation:
    """RAG observation for a single evaluation"""
    turn_number: int
    speaker: str
    attempt: int
    status: str  # PASS, WARN, RETRY
    rag_enabled: bool
    latency_ms: float
    facts_count: int
    facts: list[dict]
    triggered_by: list[str]
    response_snippet: str  # First 50 chars


@dataclass
class TurnResult:
    """Result for a single turn"""
    turn_number: int
    speaker: str
    final_status: str
    retry_count: int
    observations: list[RAGObservation] = field(default_factory=list)
    final_thought: str = ""
    final_output: str = ""


@dataclass
class ObservationResult:
    """Complete observation result"""
    experiment_id: str
    timestamp: str
    scenario: str
    turns: list[TurnResult]
    latency_stats: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


def run_observation(
    scenario_name: str = "casual_greeting",
    initial_prompt: str = "おはよう、二人とも",
    num_turns: int = 6,
    backend: str = "ollama",
    model: str = "gemma3:12b",
) -> ObservationResult:
    """Run a single observation session with RAG enabled"""

    from duo_talk_core import create_dialogue_manager
    from duo_talk_core.dialogue_manager import DialogueSession
    from duo_talk_director import DirectorHybrid
    from duo_talk_director.llm.evaluator import EvaluatorLLMClient

    # Mock LLM client (skip LLM evaluation, focus on static + RAG)
    class MockLLMClient(EvaluatorLLMClient):
        def generate(self, prompt: str) -> str:
            return "{}"
        def is_available(self) -> bool:
            return False

    # Create DirectorHybrid with RAG enabled
    director = DirectorHybrid(
        llm_client=MockLLMClient(),
        skip_llm_on_static_retry=True,
        rag_enabled=True,
    )

    # Wrap for logging
    class RAGLoggingDirector:
        def __init__(self, base_director):
            self.base = base_director
            self.observations: list[RAGObservation] = []
            self._attempt = 0

        def evaluate_response(self, speaker, response, topic, history, turn_number):
            self._attempt += 1

            eval_result = self.base.evaluate_response(
                speaker=speaker,
                response=response,
                topic=topic,
                history=history,
                turn_number=turn_number,
            )

            # Capture RAG log
            rag_log = self.base.get_last_rag_log()

            obs = RAGObservation(
                turn_number=turn_number,
                speaker=speaker,
                attempt=self._attempt,
                status=eval_result.status.name,
                rag_enabled=rag_log is not None,
                latency_ms=rag_log.latency_ms if rag_log else 0,
                facts_count=len(rag_log.facts) if rag_log else 0,
                facts=[f.__dict__ for f in rag_log.facts] if rag_log else [],
                triggered_by=rag_log.triggered_by if rag_log else [],
                response_snippet=response[:50] if response else "",
            )
            self.observations.append(obs)

            return eval_result

        def commit_evaluation(self, response, evaluation):
            self.base.commit_evaluation(response, evaluation)

        def reset_for_new_session(self):
            self.base.reset_for_new_session()
            self.observations.clear()
            self._attempt = 0

        def reset_for_new_turn(self):
            self._attempt = 0
            self.base.clear_rag_attempts()

        def get_turn_observations(self) -> list[RAGObservation]:
            obs = self.observations.copy()
            self.observations.clear()
            return obs

    logging_director = RAGLoggingDirector(director)

    # Create dialogue manager
    manager = create_dialogue_manager(
        backend=backend,
        model=model,
        director=logging_director,
        max_retries=3,
    )

    # Run session
    session = DialogueSession(topic=initial_prompt, max_turns=num_turns)
    logging_director.reset_for_new_session()

    speakers = ["やな", "あゆ"]
    turn_results: list[TurnResult] = []
    all_latencies: list[float] = []

    print(f"\n{'='*60}")
    print(f"RAG Observation Test: {scenario_name}")
    print(f"Prompt: {initial_prompt}")
    print(f"{'='*60}\n")

    for i in range(num_turns):
        speaker = speakers[i % 2]
        logging_director.reset_for_new_turn()

        print(f"Turn {i+1} ({speaker})...", end=" ", flush=True)

        turn = manager.generate_turn(
            speaker_name=speaker,
            topic=initial_prompt,
            history=session.get_history(),
            turn_number=i,
        )
        session.add_turn(turn)

        # Get observations for this turn
        obs = logging_director.get_turn_observations()

        turn_result = TurnResult(
            turn_number=i,
            speaker=speaker,
            final_status="PASS" if turn.retry_count == 0 else "RETRY→PASS",
            retry_count=turn.retry_count,
            observations=obs,
            final_thought=turn.thought or "",
            final_output=turn.output or turn.content,
        )
        turn_results.append(turn_result)

        # Collect latencies
        for o in obs:
            if o.latency_ms > 0:
                all_latencies.append(o.latency_ms)

        # Print summary
        retries = f" (retries: {turn.retry_count})" if turn.retry_count > 0 else ""
        facts_info = f", facts: {obs[-1].facts_count}" if obs else ""
        latency_info = f", latency: {obs[-1].latency_ms:.1f}ms" if obs and obs[-1].latency_ms > 0 else ""
        print(f"OK{retries}{facts_info}{latency_info}")

        # Show facts for this turn
        if obs:
            for o in obs:
                if o.facts:
                    status_marker = "✓" if o.status == "PASS" else "✗"
                    print(f"    {status_marker} Attempt {o.attempt}: {o.status}")
                    for fact in o.facts:
                        print(f"      [{fact['tag']}] {fact['text']}")

    # Compute latency stats
    latency_stats = {}
    if all_latencies:
        sorted_lat = sorted(all_latencies)
        latency_stats = {
            "count": len(all_latencies),
            "min_ms": min(all_latencies),
            "max_ms": max(all_latencies),
            "p50_ms": sorted_lat[len(sorted_lat) // 2],
            "p95_ms": sorted_lat[int(len(sorted_lat) * 0.95)] if len(sorted_lat) >= 2 else sorted_lat[-1],
            "avg_ms": sum(all_latencies) / len(all_latencies),
        }

    # Summary
    total_obs = sum(len(t.observations) for t in turn_results)
    retry_count = sum(t.retry_count for t in turn_results)

    summary = {
        "total_turns": num_turns,
        "total_observations": total_obs,
        "total_retries": retry_count,
        "avg_facts_per_turn": sum(o.facts_count for t in turn_results for o in t.observations) / total_obs if total_obs > 0 else 0,
    }

    # Print summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"Total turns: {num_turns}")
    print(f"Total retries: {retry_count}")
    print(f"Total RAG observations: {total_obs}")
    if latency_stats:
        print(f"Latency p50: {latency_stats['p50_ms']:.2f}ms")
        print(f"Latency p95: {latency_stats['p95_ms']:.2f}ms")
        print(f"Latency avg: {latency_stats['avg_ms']:.2f}ms")

    experiment_id = f"rag_observation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    result = ObservationResult(
        experiment_id=experiment_id,
        timestamp=datetime.now().isoformat(),
        scenario=scenario_name,
        turns=turn_results,
        latency_stats=latency_stats,
        summary=summary,
    )

    return result


def save_result(result: ObservationResult, output_dir: Path = Path("results")):
    """Save observation result"""
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

    result_dict = to_dict(result)

    # Save JSON
    with open(exp_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    # Generate report
    report = generate_report(result)
    with open(exp_dir / "REPORT.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✓ Results saved to {exp_dir}/")


def generate_report(result: ObservationResult) -> str:
    """Generate markdown report"""
    lines = [
        "# RAG Observation Report (Phase 3.1)",
        "",
        f"**Experiment ID**: {result.experiment_id}",
        f"**Timestamp**: {result.timestamp}",
        f"**Scenario**: {result.scenario}",
        "",
        "---",
        "",
        "## 1. Latency Statistics",
        "",
    ]

    if result.latency_stats:
        lines.extend([
            "| Metric | Value |",
            "|--------|-------|",
            f"| Count | {result.latency_stats.get('count', 0)} |",
            f"| Min | {result.latency_stats.get('min_ms', 0):.2f}ms |",
            f"| Max | {result.latency_stats.get('max_ms', 0):.2f}ms |",
            f"| **p50** | **{result.latency_stats.get('p50_ms', 0):.2f}ms** |",
            f"| **p95** | **{result.latency_stats.get('p95_ms', 0):.2f}ms** |",
            f"| Avg | {result.latency_stats.get('avg_ms', 0):.2f}ms |",
            "",
        ])
    else:
        lines.append("No latency data collected.\n")

    lines.extend([
        "---",
        "",
        "## 2. Turn Details",
        "",
    ])

    for turn in result.turns:
        lines.append(f"### Turn {turn.turn_number + 1} ({turn.speaker})")
        lines.append("")
        lines.append(f"**Status**: {turn.final_status} (retries: {turn.retry_count})")
        lines.append("")

        if turn.final_thought:
            lines.append(f"**Thought**: {turn.final_thought[:100]}...")
        lines.append(f"**Output**: {turn.final_output[:100]}...")
        lines.append("")

        if turn.observations:
            lines.append("**RAG Facts**:")
            lines.append("")
            lines.append("| Attempt | Status | Facts |")
            lines.append("|:-------:|:------:|-------|")

            for obs in turn.observations:
                facts_str = ", ".join(f"[{f['tag']}] {f['text'][:30]}..." for f in obs.facts) if obs.facts else "-"
                lines.append(f"| {obs.attempt} | {obs.status} | {facts_str} |")

            lines.append("")

        lines.append("---")
        lines.append("")

    lines.extend([
        "## 3. Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Turns | {result.summary.get('total_turns', 0)} |",
        f"| Total Retries | {result.summary.get('total_retries', 0)} |",
        f"| Total Observations | {result.summary.get('total_observations', 0)} |",
        f"| Avg Facts/Turn | {result.summary.get('avg_facts_per_turn', 0):.2f} |",
        "",
        "---",
        "",
        "*Report generated by duo-talk-evaluation RAG observation test*",
    ])

    return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG Observation Test (Phase 3.1)")
    parser.add_argument("--backend", default="ollama", help="LLM backend")
    parser.add_argument("--model", default="gemma3:12b", help="Model name")
    parser.add_argument("--turns", type=int, default=6, help="Number of turns")
    parser.add_argument("--scenario", default="casual_greeting", help="Scenario name")
    parser.add_argument("--prompt", default="おはよう、二人とも", help="Initial prompt")
    parser.add_argument("--output", default="results", help="Output directory")
    args = parser.parse_args()

    result = run_observation(
        scenario_name=args.scenario,
        initial_prompt=args.prompt,
        num_turns=args.turns,
        backend=args.backend,
        model=args.model,
    )

    save_result(result, Path(args.output))


if __name__ == "__main__":
    main()
