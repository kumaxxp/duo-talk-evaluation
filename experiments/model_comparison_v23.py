#!/usr/bin/env python3
"""Model Comparison Experiment (v2.3)

This experiment compares different LLMs to solve the Empty Thought problem.

Models tested:
- gemma3:12b (baseline)
- llama3.1:8b (benchmark)
- qwen2.5:14b (production candidate)

Success criteria (v2.3):
- Thought presence: 100%
- Empty Thought: < 5%
- Avg retries: < 1.0
"""

import json
import re
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
class ThoughtMetrics:
    """Metrics for Thought generation quality"""
    total_responses: int = 0
    thought_present: int = 0
    thought_missing: int = 0
    thought_empty: int = 0
    thought_with_content: int = 0

    @property
    def presence_rate(self) -> float:
        if self.total_responses == 0:
            return 0.0
        return self.thought_present / self.total_responses

    @property
    def content_rate(self) -> float:
        if self.total_responses == 0:
            return 0.0
        return self.thought_with_content / self.total_responses

    @property
    def empty_rate(self) -> float:
        if self.thought_present == 0:
            return 0.0
        return self.thought_empty / self.thought_present


@dataclass
class TurnResult:
    """Result of a single turn"""
    turn_number: int
    speaker: str
    raw_response: str
    thought: Optional[str]
    output: Optional[str]
    thought_status: str  # "present", "missing", "empty"
    retry_count: int
    generation_time: float


@dataclass
class ModelResult:
    """Result for a single model"""
    model_name: str
    thought_metrics: ThoughtMetrics
    avg_retries: float
    total_rejections: int
    avg_generation_time: float
    turns: list[TurnResult] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

    def meets_v23_criteria(self) -> bool:
        """Check if model meets v2.3 success criteria"""
        return (
            self.thought_metrics.presence_rate >= 1.0 and
            self.thought_metrics.empty_rate < 0.05 and
            self.avg_retries < 1.0
        )


@dataclass
class ComparisonResult:
    """Complete comparison result"""
    experiment_id: str
    timestamp: str
    models: list[str]
    scenario: dict
    results: dict[str, ModelResult] = field(default_factory=dict)
    winner: Optional[str] = None
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "models": self.models,
            "scenario": self.scenario,
            "results": {
                name: {
                    "model_name": r.model_name,
                    "thought_metrics": asdict(r.thought_metrics),
                    "avg_retries": r.avg_retries,
                    "total_rejections": r.total_rejections,
                    "avg_generation_time": r.avg_generation_time,
                    "turns": [asdict(t) for t in r.turns],
                    "success": r.success,
                    "error": r.error,
                    "meets_v23_criteria": r.meets_v23_criteria(),
                }
                for name, r in self.results.items()
            },
            "winner": self.winner,
            "summary": self.summary,
        }


class ThoughtAnalyzer:
    """Analyze Thought content in responses"""

    # Pattern to extract Thought content
    THOUGHT_PATTERN = re.compile(
        r"Thought:\s*(.+?)(?=\nOutput:|$)",
        re.DOTALL | re.IGNORECASE
    )

    # Patterns indicating empty Thought
    EMPTY_PATTERNS = [
        r"^\s*\(\s*$",           # Just "("
        r"^\s*\(\s*\)\s*$",      # "()"
        r"^\s*$",                # Empty
        r"^\s*\.\.\.\s*$",       # Just "..."
        r"^\s*…\s*$",            # Just "…"
        r"^\s*\(\s*\.\.\.\s*\)\s*$",  # "(... )"
    ]

    @classmethod
    def analyze(cls, response: str) -> tuple[str, Optional[str]]:
        """Analyze Thought in response

        Returns:
            (status, thought_content)
            status: "present", "missing", "empty"
        """
        # Check for Thought marker
        if "thought:" not in response.lower():
            return ("missing", None)

        # Extract Thought content
        match = cls.THOUGHT_PATTERN.search(response)
        if not match:
            return ("empty", "")

        thought_content = match.group(1).strip()

        # Check for empty patterns
        for pattern in cls.EMPTY_PATTERNS:
            if re.match(pattern, thought_content):
                return ("empty", thought_content)

        # Check minimum content (after removing parentheses)
        cleaned = thought_content.strip("() ")
        if len(cleaned) < 3:
            return ("empty", thought_content)

        return ("present", thought_content)


class ModelComparisonExperiment:
    """Model comparison experiment runner"""

    def __init__(
        self,
        models: list[str],
        backend: str = "ollama",
        turns: int = 5,
        output_dir: Path = Path("results"),
    ):
        self.models = models
        self.backend = backend
        self.turns = turns
        self.output_dir = output_dir

        self.scenario = {
            "name": "casual_greeting",
            "initial_prompt": "おはよう、二人とも",
            "turns": turns,
        }

    def check_model_availability(self, model: str) -> bool:
        """Check if a model is available"""
        try:
            from duo_talk_core.llm_client import create_client
            client = create_client(backend=self.backend, model=model)
            return client.is_available()
        except Exception as e:
            print(f"  Error checking {model}: {e}")
            return False

    def setup(self) -> list[str]:
        """Setup and return list of available models"""
        print("Checking model availability...")
        available = []

        for model in self.models:
            print(f"  {model}: ", end="", flush=True)
            if self.check_model_availability(model):
                print("OK")
                available.append(model)
            else:
                print("NOT AVAILABLE")

        return available

    def run(self) -> ComparisonResult:
        """Run the comparison experiment"""
        print("\n" + "=" * 60)
        print("Model Comparison Experiment (v2.3)")
        print("=" * 60)

        available_models = self.setup()

        if not available_models:
            print("\nNo models available. Exiting.")
            sys.exit(1)

        experiment_id = f"model_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = ComparisonResult(
            experiment_id=experiment_id,
            timestamp=datetime.now().isoformat(),
            models=available_models,
            scenario=self.scenario,
        )

        # Run each model
        for model in available_models:
            print(f"\n--- Testing: {model} ---")
            model_result = self._run_model(model)
            result.results[model] = model_result

            # Print summary
            metrics = model_result.thought_metrics
            print(f"  Thought presence: {metrics.presence_rate * 100:.1f}%")
            print(f"  Thought empty: {metrics.empty_rate * 100:.1f}%")
            print(f"  Avg retries: {model_result.avg_retries:.2f}")
            print(f"  Meets v2.3: {'YES' if model_result.meets_v23_criteria() else 'NO'}")

        # Determine winner
        result.winner = self._determine_winner(result)
        result.summary = self._compute_summary(result)

        # Save results
        self._save_result(result)

        return result

    def _run_model(self, model: str) -> ModelResult:
        """Run experiment for a single model"""
        try:
            from duo_talk_core import create_dialogue_manager
            from duo_talk_director import DirectorMinimal

            # Create manager with Director
            director = DirectorMinimal()
            manager = create_dialogue_manager(
                backend=self.backend,
                model=model,
                director=director,
                max_retries=3,
            )

            # Track metrics
            metrics = ThoughtMetrics()
            turns: list[TurnResult] = []
            total_retries = 0
            total_time = 0.0

            # Run dialogue
            speakers = ["やな", "あゆ"]
            history: list[dict] = []

            for i in range(self.scenario["turns"]):
                speaker = speakers[i % 2]
                start_time = time.time()

                turn = manager.generate_turn(
                    speaker_name=speaker,
                    topic=self.scenario["initial_prompt"],
                    history=history,
                    turn_number=i,
                )

                gen_time = time.time() - start_time
                total_time += gen_time

                # Analyze Thought
                status, thought_content = ThoughtAnalyzer.analyze(turn.content)

                # Update metrics
                metrics.total_responses += 1
                if status == "present":
                    metrics.thought_present += 1
                    metrics.thought_with_content += 1
                elif status == "empty":
                    metrics.thought_present += 1
                    metrics.thought_empty += 1
                else:  # missing
                    metrics.thought_missing += 1

                # Track retries
                total_retries += turn.retry_count

                # Record turn
                turn_result = TurnResult(
                    turn_number=i,
                    speaker=speaker,
                    raw_response=turn.content,
                    thought=thought_content,
                    output=turn.output,
                    thought_status=status,
                    retry_count=turn.retry_count,
                    generation_time=gen_time,
                )
                turns.append(turn_result)

                # Update history
                history.append({
                    "speaker": speaker,
                    "content": turn.output or turn.content,
                })

                print(f"  Turn {i + 1}: {status} (retry={turn.retry_count})")

            return ModelResult(
                model_name=model,
                thought_metrics=metrics,
                avg_retries=total_retries / self.scenario["turns"],
                total_rejections=total_retries,
                avg_generation_time=total_time / self.scenario["turns"],
                turns=turns,
                success=True,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return ModelResult(
                model_name=model,
                thought_metrics=ThoughtMetrics(),
                avg_retries=0.0,
                total_rejections=0,
                avg_generation_time=0.0,
                success=False,
                error=str(e),
            )

    def _determine_winner(self, result: ComparisonResult) -> Optional[str]:
        """Determine which model best meets v2.3 criteria"""
        candidates = [
            (name, r)
            for name, r in result.results.items()
            if r.success and r.meets_v23_criteria()
        ]

        if not candidates:
            return None

        # Sort by: lowest empty rate, then lowest retries, then fastest
        candidates.sort(key=lambda x: (
            x[1].thought_metrics.empty_rate,
            x[1].avg_retries,
            x[1].avg_generation_time,
        ))

        return candidates[0][0]

    def _compute_summary(self, result: ComparisonResult) -> dict:
        """Compute experiment summary"""
        summary = {
            "total_models_tested": len(result.results),
            "models_meeting_v23": [],
            "models_failing_v23": [],
            "comparison_table": [],
        }

        for name, r in result.results.items():
            row = {
                "model": name,
                "presence_rate": f"{r.thought_metrics.presence_rate * 100:.1f}%",
                "empty_rate": f"{r.thought_metrics.empty_rate * 100:.1f}%",
                "avg_retries": f"{r.avg_retries:.2f}",
                "meets_v23": r.meets_v23_criteria(),
            }
            summary["comparison_table"].append(row)

            if r.meets_v23_criteria():
                summary["models_meeting_v23"].append(name)
            else:
                summary["models_failing_v23"].append(name)

        summary["winner"] = result.winner

        return summary

    def _save_result(self, result: ComparisonResult):
        """Save experiment results"""
        exp_dir = self.output_dir / result.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)

        # JSON result
        result_path = exp_dir / "result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        # Markdown report
        report_path = exp_dir / "MODEL_COMPARISON_REPORT.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self._generate_report(result))

        print(f"\n✓ Results saved to {exp_dir}/")

    def _generate_report(self, result: ComparisonResult) -> str:
        """Generate markdown report"""
        lines = [
            "# Model Comparison Report (v2.3)",
            "",
            f"**Experiment ID**: {result.experiment_id}",
            f"**Timestamp**: {result.timestamp}",
            "",
            "---",
            "",
            "## 1. 実験諸元",
            "",
            "| 項目 | 値 |",
            "|------|-----|",
            f"| バックエンド | {self.backend} |",
            f"| 比較モデル | {', '.join(result.models)} |",
            "| プロンプト構造 | Layered (v3.8.1) |",
            "| RAG | 無効 |",
            f"| ターン数 | {self.scenario['turns']} |",
            "| Director | DirectorMinimal (v2.2 relaxed) |",
            "| max_retries | 3 |",
            "",
            "### v2.3 成功基準",
            "",
            "| 指標 | 目標 |",
            "|------|------|",
            "| Thought presence | 100% |",
            "| Thought empty | < 5% |",
            "| Avg retries | < 1.0 |",
            "",
            "---",
            "",
            "## 2. 比較結果",
            "",
            "| モデル | Presence | Empty Rate | Avg Retries | v2.3達成 |",
            "|--------|----------|------------|-------------|---------|",
        ]

        for name, r in result.results.items():
            if r.success:
                status = "✅" if r.meets_v23_criteria() else "❌"
                lines.append(
                    f"| {name} | "
                    f"{r.thought_metrics.presence_rate * 100:.1f}% | "
                    f"{r.thought_metrics.empty_rate * 100:.1f}% | "
                    f"{r.avg_retries:.2f} | "
                    f"{status} |"
                )
            else:
                lines.append(f"| {name} | - | - | - | ❌ (Error) |")

        lines.extend([
            "",
            f"**推奨モデル**: {result.winner or '該当なし'}",
            "",
            "---",
            "",
            "## 3. 各モデルの会話サンプル",
            "",
        ])

        for name, r in result.results.items():
            if not r.success:
                lines.append(f"### {name} (Error)")
                lines.append(f"Error: {r.error}")
                lines.append("")
                continue

            lines.append(f"### {name}")
            lines.append("")
            lines.append(f"- Thought presence: {r.thought_metrics.presence_rate * 100:.1f}%")
            lines.append(f"- Empty rate: {r.thought_metrics.empty_rate * 100:.1f}%")
            lines.append(f"- Avg retries: {r.avg_retries:.2f}")
            lines.append(f"- Avg generation time: {r.avg_generation_time:.2f}s")
            lines.append("")

            for turn in r.turns:
                lines.append(f"#### Turn {turn.turn_number + 1}: {turn.speaker}")
                lines.append("")
                status_icon = {
                    "present": "✅",
                    "empty": "⚠️",
                    "missing": "❌",
                }[turn.thought_status]
                lines.append(f"**Thought Status**: {status_icon} {turn.thought_status}")
                if turn.thought:
                    lines.append(f"**Thought**: {turn.thought}")
                lines.append(f"**Output**: {turn.output or '(no output)'}")
                if turn.retry_count > 0:
                    lines.append(f"**Retries**: {turn.retry_count}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Conclusion
        lines.extend([
            "## 4. 結論",
            "",
        ])

        if result.winner:
            winner_result = result.results[result.winner]
            lines.extend([
                f"**{result.winner}** がv2.3基準を満たし、推奨モデルとして選定されました。",
                "",
                "### 推奨構成",
                "",
                "```python",
                "# duo-talk-core設定",
                f'model = "{result.winner}"',
                "backend = \"ollama\"",
                "director = DirectorMinimal()  # v2.2 relaxed mode",
                "```",
            ])
        else:
            lines.extend([
                "テストした全モデルがv2.3基準を満たしませんでした。",
                "",
                "### 次のステップ",
                "",
                "1. プロンプト改善によるThought生成率向上",
                "2. より大きなモデル（gemma3:27b等）の検証",
                "3. 他のモデルファミリーの検討",
            ])

        lines.extend([
            "",
            "---",
            "",
            "*Report generated by duo-talk-evaluation v2.3 model comparison*",
        ])

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Model Comparison Experiment (v2.3)")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemma3:12b", "llama3.1:8b", "qwen2.5:14b"],
        help="Models to compare",
    )
    parser.add_argument("--backend", default="ollama", help="LLM backend")
    parser.add_argument("--turns", type=int, default=5, help="Turns per model")
    parser.add_argument("--output", default="results", help="Output directory")
    args = parser.parse_args()

    runner = ModelComparisonExperiment(
        models=args.models,
        backend=args.backend,
        turns=args.turns,
        output_dir=Path(args.output),
    )

    result = runner.run()

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    print("\nComparison Table:")
    print("-" * 60)
    print(f"{'Model':<20} {'Presence':<12} {'Empty':<12} {'Retries':<10} {'v2.3'}")
    print("-" * 60)

    for name, r in result.results.items():
        if r.success:
            v23 = "YES" if r.meets_v23_criteria() else "NO"
            print(
                f"{name:<20} "
                f"{r.thought_metrics.presence_rate * 100:>8.1f}% "
                f"{r.thought_metrics.empty_rate * 100:>10.1f}% "
                f"{r.avg_retries:>9.2f} "
                f"{v23}"
            )
        else:
            print(f"{name:<20} {'ERROR':<12}")

    print("-" * 60)
    print(f"\nRecommended model: {result.winner or 'None'}")


if __name__ == "__main__":
    main()
