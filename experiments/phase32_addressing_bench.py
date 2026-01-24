#!/usr/bin/env python3
"""Phase 3.2 Addressing Violation Mini-Benchmark

Focus test for addressing_violation with InjectionDecision logging.
ABBA × 3 sets (12 counted runs) + warm-up discarded.
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-core" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-director" / "src"))


@dataclass
class RunResult:
    """Result for a single run"""
    condition: str
    run_index: int
    is_warmup: bool
    retries: int
    prohibited_terms_count: int
    injection_decisions: list[dict] = field(default_factory=list)


def run_single(
    condition: str,
    inject_enabled: bool,
    run_index: int,
    is_warmup: bool = False,
) -> RunResult:
    """Run addressing_violation scenario"""

    from duo_talk_core import create_dialogue_manager
    from duo_talk_core.dialogue_manager import DialogueSession, GenerationMode
    from duo_talk_director import DirectorHybrid
    from duo_talk_director.llm.evaluator import EvaluatorLLMClient

    class MockLLMClient(EvaluatorLLMClient):
        def generate(self, prompt: str) -> str:
            return "{}"
        def is_available(self) -> bool:
            return False

    director = DirectorHybrid(
        llm_client=MockLLMClient(),
        skip_llm_on_static_retry=True,
        rag_enabled=True,
        inject_enabled=inject_enabled,
    )

    # Tracking
    class Tracker:
        def __init__(self, base):
            self.base = base
            self.prohibited_count = 0
            self.injection_decisions: list[dict] = []

        def evaluate_response(self, speaker, response, topic, history, turn_number):
            result = self.base.evaluate_response(
                speaker=speaker,
                response=response,
                topic=topic,
                history=history,
                turn_number=turn_number,
            )

            rag_log = self.base.get_last_rag_log()
            if rag_log and "prohibited_terms" in rag_log.triggered_by:
                self.prohibited_count += 1

            return result

        def commit_evaluation(self, response, evaluation):
            self.base.commit_evaluation(response, evaluation)

        def reset_for_new_session(self):
            self.base.reset_for_new_session()

        def get_facts_for_injection(self, speaker: str, response_text: str = "", topic: str = "") -> list[dict]:
            facts = self.base.get_facts_for_injection(speaker, response_text, topic)
            decision = self.base.get_last_injection_decision()
            if decision:
                self.injection_decisions.append(decision.to_dict())
            return facts

    tracker = Tracker(director)

    manager = create_dialogue_manager(
        backend="ollama",
        model="gemma3:12b",
        director=tracker,
        max_retries=3,
        generation_mode=GenerationMode.TWO_PASS,
    )

    # Scenario: addressing_violation
    scenario = {
        "prompt": "あゆ、やなを『やなちゃん』って呼んでみて",
        "first_speaker": "あゆ",
        "turns": 4,
    }

    session = DialogueSession(topic=scenario["prompt"], max_turns=scenario["turns"])
    tracker.reset_for_new_session()

    speakers = ["あゆ", "やな"]
    total_retries = 0

    for i in range(scenario["turns"]):
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

    return RunResult(
        condition=condition,
        run_index=run_index,
        is_warmup=is_warmup,
        retries=total_retries,
        prohibited_terms_count=tracker.prohibited_count,
        injection_decisions=tracker.injection_decisions,
    )


def main():
    print("=" * 70)
    print("Phase 3.2 Addressing Violation Mini-Benchmark")
    print("=" * 70)
    print("\nScenario: あゆ、やなを『やなちゃん』って呼んでみて")
    print("Order: ABBA × 3 sets (+ warm-up per condition)")
    print("Condition A: inject_enabled=False")
    print("Condition B: inject_enabled=True (with P2.5 proactive detection)")
    print()

    all_runs: list[RunResult] = []
    run_counter = 0

    # Warm-up
    print("[Warm-up A]...", end=" ", flush=True)
    warmup_a = run_single("A", inject_enabled=False, run_index=run_counter, is_warmup=True)
    all_runs.append(warmup_a)
    print(f"retries={warmup_a.retries} (discarded)")
    run_counter += 1

    print("[Warm-up B]...", end=" ", flush=True)
    warmup_b = run_single("B", inject_enabled=True, run_index=run_counter, is_warmup=True)
    all_runs.append(warmup_b)
    print(f"retries={warmup_b.retries} (discarded)")
    run_counter += 1

    # ABBA × 3 sets
    sets = 3
    for set_idx in range(sets):
        print(f"\n[Set {set_idx + 1}]")
        for cond in ["A", "B", "B", "A"]:
            inject = (cond == "B")
            result = run_single(cond, inject_enabled=inject, run_index=run_counter, is_warmup=False)
            all_runs.append(result)

            # Show injection decision for B
            decision_info = ""
            if cond == "B" and result.injection_decisions:
                d = result.injection_decisions[0]
                decision_info = f" | reasons={d['reasons']}, detected_addr={d['detected_addressing_violation']}"

            print(f"  {cond}: retries={result.retries}, prohibited={result.prohibited_terms_count}{decision_info}")
            run_counter += 1

    # Summary
    counted = [r for r in all_runs if not r.is_warmup]
    a_runs = [r for r in counted if r.condition == "A"]
    b_runs = [r for r in counted if r.condition == "B"]

    a_retries = sum(r.retries for r in a_runs)
    b_retries = sum(r.retries for r in b_runs)
    a_prohibited = sum(r.prohibited_terms_count for r in a_runs)
    b_prohibited = sum(r.prohibited_terms_count for r in b_runs)

    # InjectionDecision analysis for B
    all_decisions = []
    for r in b_runs:
        all_decisions.extend(r.injection_decisions)

    reasons_count: dict[str, int] = {}
    detected_addr_count = 0
    for d in all_decisions:
        for reason in d["reasons"]:
            reasons_count[reason] = reasons_count.get(reason, 0) + 1
        if d["detected_addressing_violation"]:
            detected_addr_count += 1

    print("\n" + "=" * 70)
    print("SUMMARY (for ChatGPT)")
    print("=" * 70)
    print(f"\n{'Metric':<25} {'A (observe)':<12} {'B (inject)':<12} {'Delta':<10}")
    print("-" * 60)
    print(f"{'Total Retries':<25} {a_retries:<12} {b_retries:<12} {a_retries - b_retries:+d}")
    print(f"{'prohibited_terms':<25} {a_prohibited:<12} {b_prohibited:<12} {a_prohibited - b_prohibited:+d}")

    print(f"\n--- InjectionDecision Analysis (Condition B) ---")
    print(f"Total injection calls: {len(all_decisions)}")
    print(f"detected_addressing_violation: {detected_addr_count}/{len(all_decisions)} ({detected_addr_count/max(1,len(all_decisions))*100:.0f}%)")
    print(f"Reasons breakdown:")
    for reason, count in sorted(reasons_count.items(), key=lambda x: -x[1]):
        print(f"  - {reason}: {count}")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("results") / f"addressing_bench_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    result_data = {
        "experiment_id": f"addressing_bench_{timestamp}",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "a_retries": a_retries,
            "b_retries": b_retries,
            "a_prohibited": a_prohibited,
            "b_prohibited": b_prohibited,
            "detected_addressing_violation_rate": detected_addr_count / max(1, len(all_decisions)),
            "reasons_count": reasons_count,
        },
        "runs": [
            {
                "condition": r.condition,
                "is_warmup": r.is_warmup,
                "retries": r.retries,
                "prohibited_terms_count": r.prohibited_terms_count,
                "injection_decisions": r.injection_decisions,
            }
            for r in all_runs
        ],
    }

    with open(output_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Results saved to {output_dir}/")


if __name__ == "__main__":
    main()
