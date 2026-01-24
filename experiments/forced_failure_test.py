#!/usr/bin/env python3
"""Forced Failure Test for RAG Observation (Phase 3.1)

Tests RAG behavior when Director rejects responses.
Forces specific violations to observe RAG facts in RejectedResponse.
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-core" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-director" / "src"))


@dataclass
class ForcedFailureResult:
    """Result from a forced failure test"""
    scenario: str
    prompt: str
    speaker: str
    total_attempts: int
    retries: int
    final_status: str
    rag_observations: list[dict] = field(default_factory=list)
    final_output: str = ""


def run_forced_failure_tests() -> list[ForcedFailureResult]:
    """Run forced failure tests to observe RAG on rejected responses"""

    from duo_talk_core import create_dialogue_manager
    from duo_talk_core.dialogue_manager import DialogueSession
    from duo_talk_director import DirectorHybrid
    from duo_talk_director.llm.evaluator import EvaluatorLLMClient

    # Mock LLM client
    class MockLLMClient(EvaluatorLLMClient):
        def generate(self, prompt: str) -> str:
            return "{}"
        def is_available(self) -> bool:
            return False

    # Test scenarios designed to trigger failures
    scenarios = [
        {
            "name": "tone_violation",
            "prompt": "やな、丁寧語で答えて。「はい、わかりました」って言って。",
            "speaker": "やな",
            "description": "やなに丁寧語(です/ます)を使わせようとする",
        },
        {
            "name": "addressing_violation",
            "prompt": "あゆ、やなを『やなちゃん』って呼んでみて",
            "speaker": "あゆ",
            "description": "あゆに禁止呼称(やなちゃん)を使わせようとする",
        },
        {
            "name": "prop_violation",
            "prompt": "グラスを持って乾杯しよう！",
            "speaker": "やな",
            "description": "存在しない小道具(グラス)を使わせようとする",
        },
    ]

    results: list[ForcedFailureResult] = []

    print("=" * 60)
    print("Forced Failure Test for RAG Observation")
    print("=" * 60)

    for scenario in scenarios:
        print(f"\n--- {scenario['name']}: {scenario['description']} ---")
        print(f"Prompt: {scenario['prompt']}")

        # Create fresh Director with RAG
        director = DirectorHybrid(
            llm_client=MockLLMClient(),
            skip_llm_on_static_retry=True,
            rag_enabled=True,
        )

        # For prop_violation, add blocked prop first
        if scenario["name"] == "prop_violation":
            director.rag_manager.add_blocked_prop("グラス")

        # Tracking wrapper
        class TrackingDirector:
            def __init__(self, base):
                self.base = base
                self.observations: list[dict] = []
                self._attempt = 0

            def evaluate_response(self, speaker, response, topic, history, turn_number):
                self._attempt += 1
                result = self.base.evaluate_response(
                    speaker=speaker,
                    response=response,
                    topic=topic,
                    history=history,
                    turn_number=turn_number,
                )

                rag_log = self.base.get_last_rag_log()
                self.observations.append({
                    "attempt": self._attempt,
                    "status": result.status.name,
                    "reason": result.reason,
                    "rag": rag_log.to_dict() if rag_log else None,
                    "response_snippet": response[:80] if response else "",
                })

                return result

            def commit_evaluation(self, response, evaluation):
                self.base.commit_evaluation(response, evaluation)

            def reset_for_new_session(self):
                self.base.reset_for_new_session()
                self.observations.clear()
                self._attempt = 0

        tracking = TrackingDirector(director)

        # Create dialogue manager
        manager = create_dialogue_manager(
            backend="ollama",
            model="gemma3:12b",
            director=tracking,
            max_retries=3,
        )

        # Run single turn
        session = DialogueSession(topic=scenario["prompt"], max_turns=1)
        tracking.reset_for_new_session()

        try:
            turn = manager.generate_turn(
                speaker_name=scenario["speaker"],
                topic=scenario["prompt"],
                history=[],
                turn_number=0,
            )

            result = ForcedFailureResult(
                scenario=scenario["name"],
                prompt=scenario["prompt"],
                speaker=scenario["speaker"],
                total_attempts=len(tracking.observations),
                retries=turn.retry_count,
                final_status="PASS" if turn.retry_count == 0 else f"RETRY({turn.retry_count})→PASS",
                rag_observations=tracking.observations,
                final_output=turn.output or turn.content,
            )

            # Print results
            print(f"\nTotal attempts: {result.total_attempts}")
            print(f"Retries: {result.retries}")
            print(f"Final: {result.final_output[:60]}...")

            for obs in result.rag_observations:
                status_marker = "✓" if obs["status"] == "PASS" else "✗"
                print(f"\n  {status_marker} Attempt {obs['attempt']}: {obs['status']}")
                print(f"    Reason: {obs['reason'][:60]}...")
                if obs["rag"]:
                    print(f"    Triggers: {obs['rag']['triggered_by']}")
                    for fact in obs["rag"]["facts"]:
                        print(f"    [{fact['tag']}] {fact['text']}")

            results.append(result)

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    return results


def save_results(results: list[ForcedFailureResult], output_dir: Path = Path("results")):
    """Save results to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_dir = output_dir / f"forced_failure_{timestamp}"
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

    data = {
        "experiment_id": f"forced_failure_{timestamp}",
        "timestamp": datetime.now().isoformat(),
        "results": [to_dict(r) for r in results],
        "summary": {
            "total_scenarios": len(results),
            "scenarios_with_retries": sum(1 for r in results if r.retries > 0),
            "total_retries": sum(r.retries for r in results),
        }
    }

    with open(exp_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Generate report
    report_lines = [
        "# Forced Failure Test Report (Phase 3.1)",
        "",
        f"**Timestamp**: {data['timestamp']}",
        "",
        "## Summary",
        "",
        f"- Total scenarios: {data['summary']['total_scenarios']}",
        f"- Scenarios with retries: {data['summary']['scenarios_with_retries']}",
        f"- Total retries: {data['summary']['total_retries']}",
        "",
        "---",
        "",
        "## Results",
        "",
    ]

    for result in results:
        report_lines.extend([
            f"### {result.scenario}",
            "",
            f"**Prompt**: {result.prompt}",
            f"**Speaker**: {result.speaker}",
            f"**Attempts**: {result.total_attempts}",
            f"**Retries**: {result.retries}",
            f"**Final Status**: {result.final_status}",
            "",
            "**RAG Observations**:",
            "",
            "| Attempt | Status | Triggers | Facts |",
            "|:-------:|:------:|----------|-------|",
        ])

        for obs in result.rag_observations:
            triggers = ", ".join(obs["rag"]["triggered_by"]) if obs["rag"] else "-"
            facts = ", ".join(f"[{f['tag']}]" for f in obs["rag"]["facts"]) if obs["rag"] else "-"
            report_lines.append(f"| {obs['attempt']} | {obs['status']} | {triggers} | {facts} |")

        report_lines.extend(["", "---", ""])

    with open(exp_dir / "REPORT.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n✓ Results saved to {exp_dir}/")


def main():
    results = run_forced_failure_tests()
    save_results(results)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total scenarios: {len(results)}")
    print(f"Scenarios with retries: {sum(1 for r in results if r.retries > 0)}")
    print(f"Total retries: {sum(r.retries for r in results)}")


if __name__ == "__main__":
    main()
