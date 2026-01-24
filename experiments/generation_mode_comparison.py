"""TWO_PASS vs Two-Phase Engine Comparison Experiment

Compares the two generation modes:
- TWO_PASS (v2.4): Uses TwoPassGenerator with cumulative improvements
- Two-Phase Engine (v4.0): Minimal prompt approach to avoid Instruction saturation

Evaluation axes:
1. Format success rate (Thought/Output structure)
2. Retry count (Director rejections)
3. Quality scores (5-axis evaluation)
4. Thought reusability (cross-turn coherence, state extractability)

Usage:
    python experiments/generation_mode_comparison.py --runs 2
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from duo_talk_core import create_dialogue_manager, GenerationMode
from duo_talk_core.two_phase_engine import TwoPhaseEngine
from duo_talk_core.llm_client import create_client, GenerationConfig
from duo_talk_core.character import get_character
from duo_talk_director import DirectorMinimal


@dataclass
class TurnResult:
    """Single turn result"""
    speaker: str
    thought: str
    output: str
    raw_response: str
    retries: int = 0
    format_valid: bool = True
    thought_tokens: int = 0


@dataclass
class SessionResult:
    """Session result"""
    mode: str
    scenario: str
    turns: list[TurnResult] = field(default_factory=list)
    total_retries: int = 0
    format_success_rate: float = 0.0
    thought_reusability: dict = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Full experiment result"""
    timestamp: str
    parameters: dict
    two_pass_results: list[SessionResult] = field(default_factory=list)
    two_phase_results: list[SessionResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class GenerationModeComparison:
    """Comparison experiment runner"""

    SCENARIOS = [
        {
            "name": "casual_greeting",
            "topic": "おはよう、二人とも",
            "turns": 4,
            "description": "挨拶からの自然な会話展開",
        },
        {
            "name": "topic_exploration",
            "topic": "最近のAI技術について話して",
            "turns": 4,
            "description": "話題の深掘りと情報交換",
        },
    ]

    def __init__(
        self,
        model: str = "gemma3:12b",
        temperature: float = 0.7,
        runs_per_scenario: int = 2,
    ):
        self.model = model
        self.temperature = temperature
        self.runs_per_scenario = runs_per_scenario

        # Create clients
        self.llm_client = create_client(backend="ollama", model=model)
        self.director = DirectorMinimal()

        # Characters
        self.yana = get_character("やな")
        self.ayu = get_character("あゆ")

    def run(self) -> ExperimentResult:
        """Run full comparison experiment"""
        print("=" * 60)
        print("TWO_PASS vs Two-Phase Engine Comparison")
        print("=" * 60)

        result = ExperimentResult(
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
            parameters={
                "model": self.model,
                "temperature": self.temperature,
                "runs_per_scenario": self.runs_per_scenario,
                "scenarios": [s["name"] for s in self.SCENARIOS],
            },
        )

        for scenario in self.SCENARIOS:
            print(f"\n--- Scenario: {scenario['name']} ---")

            for run in range(self.runs_per_scenario):
                print(f"\n  Run {run + 1}/{self.runs_per_scenario}")

                # TWO_PASS mode
                print("    [TWO_PASS]", end=" ", flush=True)
                two_pass_result = self._run_two_pass(scenario)
                result.two_pass_results.append(two_pass_result)
                print(f"retries={two_pass_result.total_retries}")

                # Two-Phase Engine mode
                print("    [Two-Phase]", end=" ", flush=True)
                two_phase_result = self._run_two_phase(scenario)
                result.two_phase_results.append(two_phase_result)
                print(f"retries={two_phase_result.total_retries}")

        # Calculate summary
        result.summary = self._calculate_summary(result)
        return result

    def _run_two_pass(self, scenario: dict) -> SessionResult:
        """Run scenario with TWO_PASS mode"""
        manager = create_dialogue_manager(
            backend="ollama",
            model=self.model,
            temperature=self.temperature,
            director=self.director,
            max_retries=3,
            generation_mode=GenerationMode.TWO_PASS,
        )

        session_result = SessionResult(
            mode="TWO_PASS",
            scenario=scenario["name"],
        )

        history = []
        speakers = ["やな", "あゆ"]

        for turn_num in range(scenario["turns"]):
            speaker = speakers[turn_num % 2]

            turn = manager.generate_turn(
                speaker_name=speaker,
                topic=scenario["topic"],
                history=history,
                turn_number=turn_num,
            )

            turn_result = TurnResult(
                speaker=speaker,
                thought=turn.thought or "",
                output=turn.output or "",
                raw_response=turn.content,
                format_valid=bool(turn.thought and turn.output),
                thought_tokens=len(turn.thought) if turn.thought else 0,
            )
            session_result.turns.append(turn_result)

            history.append({
                "speaker": speaker,
                "content": turn.output or turn.content,
            })

        # Calculate metrics
        session_result.format_success_rate = sum(
            1 for t in session_result.turns if t.format_valid
        ) / len(session_result.turns)

        # Calculate Thought reusability
        session_result.thought_reusability = self._evaluate_thought_reusability(
            session_result.turns
        )

        return session_result

    def _run_two_phase(self, scenario: dict) -> SessionResult:
        """Run scenario with Two-Phase Engine"""
        engine = TwoPhaseEngine(max_thought_tokens=80)

        session_result = SessionResult(
            mode="Two-Phase",
            scenario=scenario["name"],
        )

        history = []
        speakers = [self.yana, self.ayu]

        for turn_num in range(scenario["turns"]):
            character = speakers[turn_num % 2]

            # Phase 1: Thought generation
            phase1_prompt = engine.build_phase1_prompt(
                character=character,
                topic=scenario["topic"],
                history=history,
            )

            thought = self.llm_client.generate(
                prompt=phase1_prompt,
                config=GenerationConfig(
                    max_tokens=80,
                    temperature=self.temperature,
                ),
            )

            # Phase 2: Speech generation
            phase2_prompt = engine.build_phase2_prompt(
                character=character,
                thought=thought,
                topic=scenario["topic"],
                history=history,
            )

            speech = self.llm_client.generate(
                prompt=phase2_prompt,
                config=GenerationConfig(
                    max_tokens=200,
                    temperature=self.temperature,
                ),
            )

            turn_result = TurnResult(
                speaker=character.name,
                thought=thought,
                output=speech,
                raw_response=f"Thought: {thought}\nOutput: {speech}",
                format_valid=bool(thought.strip() and speech.strip()),
                thought_tokens=len(thought),
            )
            session_result.turns.append(turn_result)

            history.append({
                "speaker": character.name,
                "content": speech,
            })

        # Calculate metrics
        session_result.format_success_rate = sum(
            1 for t in session_result.turns if t.format_valid
        ) / len(session_result.turns)

        # Calculate Thought reusability
        session_result.thought_reusability = self._evaluate_thought_reusability(
            session_result.turns
        )

        return session_result

    def _evaluate_thought_reusability(self, turns: list[TurnResult]) -> dict:
        """Evaluate Thought reusability across turns

        Metrics:
        - cross_turn_coherence: Do thoughts reference previous context?
        - state_extractability: Can we extract emotional/topic state from thought?
        - emotion_continuity: Is there emotional thread across thoughts?
        """
        if len(turns) < 2:
            return {
                "cross_turn_coherence": 0.0,
                "state_extractability": 0.0,
                "emotion_continuity": 0.0,
                "avg_thought_length": 0,
            }

        # Simple heuristics for now (can be enhanced with LLM evaluation)
        coherence_signals = ["姉様", "あゆ", "さっき", "続き", "それ", "これ"]
        state_signals = ["嬉しい", "心配", "楽しい", "困る", "面白い", "不安"]

        coherence_count = 0
        state_count = 0
        total_length = 0

        for i, turn in enumerate(turns):
            thought = turn.thought

            # Cross-turn coherence: references to conversation context
            if i > 0 and any(sig in thought for sig in coherence_signals):
                coherence_count += 1

            # State extractability: emotional/cognitive state
            if any(sig in thought for sig in state_signals):
                state_count += 1

            total_length += len(thought)

        num_turns = len(turns)
        return {
            "cross_turn_coherence": coherence_count / max(num_turns - 1, 1),
            "state_extractability": state_count / num_turns,
            "emotion_continuity": 0.0,  # Requires LLM evaluation
            "avg_thought_length": total_length / num_turns,
        }

    def _calculate_summary(self, result: ExperimentResult) -> dict:
        """Calculate summary statistics"""
        def avg(values):
            return sum(values) / len(values) if values else 0.0

        two_pass_retries = [r.total_retries for r in result.two_pass_results]
        two_phase_retries = [r.total_retries for r in result.two_phase_results]

        two_pass_format = [r.format_success_rate for r in result.two_pass_results]
        two_phase_format = [r.format_success_rate for r in result.two_phase_results]

        two_pass_coherence = [
            r.thought_reusability.get("cross_turn_coherence", 0)
            for r in result.two_pass_results
        ]
        two_phase_coherence = [
            r.thought_reusability.get("cross_turn_coherence", 0)
            for r in result.two_phase_results
        ]

        return {
            "TWO_PASS": {
                "avg_retries": avg(two_pass_retries),
                "avg_format_success": avg(two_pass_format),
                "avg_coherence": avg(two_pass_coherence),
            },
            "Two-Phase": {
                "avg_retries": avg(two_phase_retries),
                "avg_format_success": avg(two_phase_format),
                "avg_coherence": avg(two_phase_coherence),
            },
            "comparison": {
                "retry_diff": avg(two_pass_retries) - avg(two_phase_retries),
                "format_diff": avg(two_pass_format) - avg(two_phase_format),
                "coherence_diff": avg(two_pass_coherence) - avg(two_phase_coherence),
            },
        }


def save_results(result: ExperimentResult, output_dir: Path):
    """Save experiment results"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    json_path = output_dir / "result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, ensure_ascii=False, indent=2)

    # Generate report
    report_path = output_dir / "REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(generate_report(result))

    print(f"\nResults saved to: {output_dir}")


def generate_report(result: ExperimentResult) -> str:
    """Generate markdown report"""
    lines = [
        "# TWO_PASS vs Two-Phase Engine 比較実験レポート",
        "",
        f"**実行日時**: {result.timestamp}",
        f"**モデル**: {result.parameters['model']}",
        f"**温度**: {result.parameters['temperature']}",
        f"**実行回数/シナリオ**: {result.parameters['runs_per_scenario']}",
        "",
        "---",
        "",
        "## サマリー",
        "",
        "| 指標 | TWO_PASS | Two-Phase | 差分 |",
        "|------|----------|-----------|------|",
    ]

    summary = result.summary
    lines.append(
        f"| 平均リトライ | {summary['TWO_PASS']['avg_retries']:.2f} | "
        f"{summary['Two-Phase']['avg_retries']:.2f} | "
        f"{summary['comparison']['retry_diff']:+.2f} |"
    )
    lines.append(
        f"| フォーマット成功率 | {summary['TWO_PASS']['avg_format_success']:.1%} | "
        f"{summary['Two-Phase']['avg_format_success']:.1%} | "
        f"{summary['comparison']['format_diff']:+.1%} |"
    )
    lines.append(
        f"| Thought一貫性 | {summary['TWO_PASS']['avg_coherence']:.2f} | "
        f"{summary['Two-Phase']['avg_coherence']:.2f} | "
        f"{summary['comparison']['coherence_diff']:+.2f} |"
    )

    lines.extend([
        "",
        "---",
        "",
        "## Thought再利用性評価",
        "",
        "| モード | cross_turn_coherence | state_extractability | avg_thought_length |",
        "|--------|---------------------|---------------------|-------------------|",
    ])

    for mode, results in [("TWO_PASS", result.two_pass_results), ("Two-Phase", result.two_phase_results)]:
        avg_coherence = sum(r.thought_reusability.get("cross_turn_coherence", 0) for r in results) / len(results)
        avg_state = sum(r.thought_reusability.get("state_extractability", 0) for r in results) / len(results)
        avg_length = sum(r.thought_reusability.get("avg_thought_length", 0) for r in results) / len(results)
        lines.append(f"| {mode} | {avg_coherence:.2f} | {avg_state:.2f} | {avg_length:.0f} |")

    lines.extend([
        "",
        "---",
        "",
        "## 会話サンプル",
        "",
    ])

    # Show first session of each mode
    for mode, results in [("TWO_PASS", result.two_pass_results), ("Two-Phase", result.two_phase_results)]:
        if results:
            session = results[0]
            lines.extend([
                f"### {mode} - {session.scenario}",
                "",
            ])
            for i, turn in enumerate(session.turns):
                lines.extend([
                    f"**Turn {i+1} ({turn.speaker})**",
                    f"- Thought: {turn.thought[:100]}..." if len(turn.thought) > 100 else f"- Thought: {turn.thought}",
                    f"- Output: {turn.output[:100]}..." if len(turn.output) > 100 else f"- Output: {turn.output}",
                    "",
                ])

    lines.extend([
        "---",
        "",
        "*Generated by generation_mode_comparison.py*",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TWO_PASS vs Two-Phase Engine Comparison")
    parser.add_argument("--model", default="gemma3:12b", help="Model name")
    parser.add_argument("--temperature", type=float, default=0.7, help="Temperature")
    parser.add_argument("--runs", type=int, default=2, help="Runs per scenario")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    # Run experiment
    runner = GenerationModeComparison(
        model=args.model,
        temperature=args.temperature,
        runs_per_scenario=args.runs,
    )
    result = runner.run()

    # Save results
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(__file__).parent.parent / "results" / f"generation_mode_{result.timestamp}"

    save_results(result, output_dir)

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"TWO_PASS:   retries={result.summary['TWO_PASS']['avg_retries']:.2f}, "
          f"format={result.summary['TWO_PASS']['avg_format_success']:.1%}")
    print(f"Two-Phase:  retries={result.summary['Two-Phase']['avg_retries']:.2f}, "
          f"format={result.summary['Two-Phase']['avg_format_success']:.1%}")


if __name__ == "__main__":
    main()
