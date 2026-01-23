#!/usr/bin/env python3
"""Two-Pass Architecture Comparison Experiment (v2.4)

Compares One-Pass (v3.8.1) vs Two-Pass (v2.4) generation modes
to validate the Two-Pass Architecture's effectiveness in solving
the empty Thought problem.
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-core" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "duo-talk-director" / "src"))

from duo_talk_core import create_dialogue_manager, GenerationMode
from duo_talk_director import DirectorMinimal


@dataclass
class TurnResult:
    """Result for a single turn"""
    speaker: str
    thought: str
    output: str
    is_thought_empty: bool
    retry_count: int = 0


@dataclass
class ScenarioResult:
    """Result for a single scenario run"""
    scenario: str
    mode: str
    turns: list[TurnResult] = field(default_factory=list)
    total_retries: int = 0
    empty_thought_count: int = 0

    @property
    def empty_thought_rate(self) -> float:
        if not self.turns:
            return 0.0
        return self.empty_thought_count / len(self.turns)


@dataclass
class ExperimentResult:
    """Complete experiment result"""
    model: str
    timestamp: str
    scenarios: list[ScenarioResult] = field(default_factory=list)

    def get_summary(self, mode: str) -> dict:
        """Get summary for a specific mode"""
        mode_results = [s for s in self.scenarios if s.mode == mode]
        if not mode_results:
            return {}

        total_turns = sum(len(s.turns) for s in mode_results)
        total_empty = sum(s.empty_thought_count for s in mode_results)
        total_retries = sum(s.total_retries for s in mode_results)

        return {
            "mode": mode,
            "total_turns": total_turns,
            "empty_thought_count": total_empty,
            "empty_thought_rate": total_empty / total_turns if total_turns > 0 else 0,
            "total_retries": total_retries,
            "avg_retries": total_retries / len(mode_results) if mode_results else 0,
        }


def is_thought_empty(thought: str | None) -> bool:
    """Check if thought is empty or effectively empty"""
    if thought is None:
        return True
    stripped = thought.strip()
    if not stripped:
        return True
    # Check for empty marker patterns
    if stripped in ["(", "()", "（", "（）"]:
        return True
    return False


def run_scenario(
    manager,
    scenario_name: str,
    initial_prompt: str,
    turns: int,
    mode_name: str,
    director=None,
) -> ScenarioResult:
    """Run a single scenario"""
    print(f"  Running {scenario_name} ({mode_name})...")

    session = manager.run_session(
        topic=initial_prompt,
        turns=turns,
        first_speaker="やな",
    )

    result = ScenarioResult(
        scenario=scenario_name,
        mode=mode_name,
    )

    for turn in session.turns:
        empty = is_thought_empty(turn.thought)
        turn_result = TurnResult(
            speaker=turn.speaker,
            thought=turn.thought or "",
            output=turn.output or "",
            is_thought_empty=empty,
            retry_count=turn.retry_count,
        )
        result.turns.append(turn_result)
        result.total_retries += turn.retry_count
        if empty:
            result.empty_thought_count += 1

    return result


def run_experiment(model: str = "gemma3:12b") -> ExperimentResult:
    """Run the full Two-Pass comparison experiment"""
    print(f"\n{'='*60}")
    print(f"Two-Pass Architecture Comparison Experiment")
    print(f"Model: {model}")
    print(f"{'='*60}\n")

    # Scenarios
    scenarios = [
        ("casual_greeting", "おはよう、二人とも", 5),
        ("topic_exploration", "最近のAI技術について話して", 6),
        ("emotional_support", "最近疲れてるんだ...", 5),
    ]

    result = ExperimentResult(
        model=model,
        timestamp=datetime.now().isoformat(),
    )

    # Create Director for both modes
    director = DirectorMinimal()

    # Run with One-Pass mode
    print("Running ONE_PASS mode (v3.8.1)...")
    manager_one_pass = create_dialogue_manager(
        model=model,
        generation_mode=GenerationMode.ONE_PASS,
        director=director,
        max_retries=3,
    )

    for scenario_name, prompt, turns in scenarios:
        director.reset_for_new_session()
        scenario_result = run_scenario(
            manager_one_pass,
            scenario_name,
            prompt,
            turns,
            "ONE_PASS",
            director,
        )
        result.scenarios.append(scenario_result)

    # Run with Two-Pass mode
    print("\nRunning TWO_PASS mode (v2.4)...")
    manager_two_pass = create_dialogue_manager(
        model=model,
        generation_mode=GenerationMode.TWO_PASS,
        director=director,
        max_retries=3,
    )

    for scenario_name, prompt, turns in scenarios:
        director.reset_for_new_session()
        scenario_result = run_scenario(
            manager_two_pass,
            scenario_name,
            prompt,
            turns,
            "TWO_PASS",
            director,
        )
        result.scenarios.append(scenario_result)

    return result


def generate_report(result: ExperimentResult, output_dir: Path) -> Path:
    """Generate markdown report"""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"two_pass_comparison_{timestamp}.md"

    one_pass_summary = result.get_summary("ONE_PASS")
    two_pass_summary = result.get_summary("TWO_PASS")

    # Build report
    lines = [
        "# Two-Pass Architecture Comparison Report (v2.4)",
        "",
        f"**Timestamp**: {result.timestamp}",
        f"**Model**: {result.model}",
        "",
        "---",
        "",
        "## 1. 実験諸元",
        "",
        "| 項目 | 値 |",
        "|------|-----|",
        f"| バックエンド | Ollama |",
        f"| LLM | {result.model} |",
        "| 比較モード | ONE_PASS (v3.8.1) vs TWO_PASS (v2.4) |",
        "| Director | DirectorMinimal (v2.2 relaxed) |",
        "| max_retries | 3 |",
        "| シナリオ数 | 3 |",
        "",
        "---",
        "",
        "## 2. 比較サマリー",
        "",
        "### 2.1 空Thought発生率",
        "",
        "| モード | 空Thought数 | 総ターン数 | 空Thought率 | 改善 |",
        "|--------|------------|----------|------------|------|",
    ]

    one_rate = one_pass_summary.get("empty_thought_rate", 0) * 100
    two_rate = two_pass_summary.get("empty_thought_rate", 0) * 100
    improvement = one_rate - two_rate

    lines.extend([
        f"| ONE_PASS (v3.8.1) | {one_pass_summary.get('empty_thought_count', 0)} | {one_pass_summary.get('total_turns', 0)} | **{one_rate:.1f}%** | - |",
        f"| TWO_PASS (v2.4) | {two_pass_summary.get('empty_thought_count', 0)} | {two_pass_summary.get('total_turns', 0)} | **{two_rate:.1f}%** | **-{improvement:.1f}%** |",
        "",
        "### 2.2 リトライ数",
        "",
        "| モード | 総リトライ数 | 平均リトライ数 |",
        "|--------|-------------|--------------|",
        f"| ONE_PASS (v3.8.1) | {one_pass_summary.get('total_retries', 0)} | {one_pass_summary.get('avg_retries', 0):.2f} |",
        f"| TWO_PASS (v2.4) | {two_pass_summary.get('total_retries', 0)} | {two_pass_summary.get('avg_retries', 0):.2f} |",
        "",
        "---",
        "",
        "## 3. 仮説検証",
        "",
        "| 仮説 | 目標 | ONE_PASS | TWO_PASS | 結果 |",
        "|------|------|----------|----------|------|",
    ])

    one_pass_ok = "✅" if one_rate < 5 else "❌"
    two_pass_ok = "✅" if two_rate < 5 else "❌"
    verdict = "✅ 達成" if two_rate < 5 else "❌ 未達成"

    lines.extend([
        f"| 空Thought率 < 5% | < 5% | {one_rate:.1f}% {one_pass_ok} | {two_rate:.1f}% {two_pass_ok} | {verdict} |",
        "",
        "---",
        "",
        "## 4. 全会話サンプル",
        "",
    ])

    # Group scenarios by mode
    one_pass_scenarios = [s for s in result.scenarios if s.mode == "ONE_PASS"]
    two_pass_scenarios = [s for s in result.scenarios if s.mode == "TWO_PASS"]

    for mode_name, mode_scenarios in [("ONE_PASS (v3.8.1)", one_pass_scenarios), ("TWO_PASS (v2.4)", two_pass_scenarios)]:
        lines.extend([
            f"### {mode_name}",
            "",
        ])

        for scenario in mode_scenarios:
            lines.extend([
                f"#### {scenario.scenario}",
                "",
                f"**空Thought数**: {scenario.empty_thought_count} / {len(scenario.turns)}",
                f"**リトライ数**: {scenario.total_retries}",
                "",
            ])

            for i, turn in enumerate(scenario.turns, 1):
                empty_marker = " ⚠️ EMPTY" if turn.is_thought_empty else ""
                lines.extend([
                    f"**Turn {i}: {turn.speaker}**{empty_marker}",
                    "",
                    f"- **Thought**: {turn.thought}",
                    f"- **Output**: {turn.output}",
                    "",
                ])

            lines.append("---")
            lines.append("")

    # Conclusion
    lines.extend([
        "## 5. 結論",
        "",
    ])

    if two_rate == 0:
        lines.extend([
            "**Two-Pass Architecture (v2.4) により空Thought問題が完全に解決されました。**",
            "",
            "- ONE_PASS: 空Thoughtが発生",
            "- TWO_PASS: 空Thought率 **0%**",
            "",
            "Two-Pass Architectureは、思考生成と発話生成を物理的に分離することで、",
            "フォーマット遵守率100%をシステム的に保証します。",
        ])
    elif two_rate < one_rate:
        lines.extend([
            f"**Two-Pass Architecture (v2.4) により空Thought率が改善されました。**",
            "",
            f"- ONE_PASS: {one_rate:.1f}%",
            f"- TWO_PASS: {two_rate:.1f}% (**{improvement:.1f}%改善**)",
        ])
    else:
        lines.extend([
            "**Two-Pass Architectureの効果は限定的でした。**",
            "",
            "追加の調査が必要です。",
        ])

    lines.extend([
        "",
        "---",
        "",
        "*Report generated by duo-talk-evaluation v2.4 Two-Pass comparison*",
    ])

    # Write report
    report_path.write_text("\n".join(lines), encoding="utf-8")

    # Also save raw JSON
    json_path = output_dir / f"two_pass_comparison_{timestamp}.json"
    json_data = {
        "model": result.model,
        "timestamp": result.timestamp,
        "one_pass_summary": one_pass_summary,
        "two_pass_summary": two_pass_summary,
        "scenarios": [
            {
                "scenario": s.scenario,
                "mode": s.mode,
                "empty_thought_count": s.empty_thought_count,
                "empty_thought_rate": s.empty_thought_rate,
                "total_retries": s.total_retries,
                "turns": [
                    {
                        "speaker": t.speaker,
                        "thought": t.thought,
                        "output": t.output,
                        "is_thought_empty": t.is_thought_empty,
                        "retry_count": t.retry_count,
                    }
                    for t in s.turns
                ],
            }
            for s in result.scenarios
        ],
    }
    json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return report_path


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Two-Pass Architecture Comparison")
    parser.add_argument("--model", default="gemma3:12b", help="Model to use")
    args = parser.parse_args()

    # Run experiment
    result = run_experiment(model=args.model)

    # Generate report
    output_dir = Path(__file__).parent.parent / "results" / "v24_two_pass"
    report_path = generate_report(result, output_dir)

    # Print summary
    print(f"\n{'='*60}")
    print("Experiment Complete!")
    print(f"{'='*60}")

    one_pass = result.get_summary("ONE_PASS")
    two_pass = result.get_summary("TWO_PASS")

    print(f"\nONE_PASS (v3.8.1):")
    print(f"  空Thought率: {one_pass.get('empty_thought_rate', 0)*100:.1f}%")
    print(f"  リトライ数: {one_pass.get('total_retries', 0)}")

    print(f"\nTWO_PASS (v2.4):")
    print(f"  空Thought率: {two_pass.get('empty_thought_rate', 0)*100:.1f}%")
    print(f"  リトライ数: {two_pass.get('total_retries', 0)}")

    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
