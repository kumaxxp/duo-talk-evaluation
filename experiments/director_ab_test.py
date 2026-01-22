#!/usr/bin/env python3
"""Director A/B Test: Compare dialogue quality with and without Director

This experiment compares:
- Condition A: duo-talk-core without Director
- Condition B: duo-talk-core with DirectorMinimal

Metrics measured:
- character_consistency: キャラクター一貫性
- topic_novelty: 話題新規性
- relationship_quality: 姉妹関係性
- naturalness: 対話自然さ
- concreteness: 情報具体性
- retry_rate: リトライ率（Director有効時のみ）
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
class DialogueResult:
    """Single dialogue result"""
    condition: str  # "without_director" or "with_director"
    scenario: str
    conversation: list[dict]
    success: bool
    execution_time: float
    total_retries: int = 0
    error: Optional[str] = None
    metrics: Optional[dict] = None


@dataclass
class ExperimentResult:
    """Complete experiment result"""
    experiment_id: str
    timestamp: str
    conditions: list[str]
    scenarios: list[dict]
    results: list[DialogueResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "conditions": self.conditions,
            "scenarios": self.scenarios,
            "results": [asdict(r) for r in self.results],
            "summary": self.summary,
        }


class DirectorABTest:
    """Director A/B Test Runner"""

    def __init__(
        self,
        backend: str = "ollama",
        model: str = "gemma3:12b",
        runs_per_scenario: int = 3,
        output_dir: Path = Path("results"),
    ):
        self.backend = backend
        self.model = model
        self.runs_per_scenario = runs_per_scenario
        self.output_dir = output_dir
        self.evaluator = None

        # Default scenarios
        self.scenarios = [
            {
                "name": "casual_greeting",
                "initial_prompt": "おはよう、二人とも",
                "turns": 5,
            },
            {
                "name": "topic_exploration",
                "initial_prompt": "最近のAI技術について話して",
                "turns": 6,
            },
            {
                "name": "emotional_support",
                "initial_prompt": "最近疲れてるんだ...",
                "turns": 5,
            },
        ]

    def setup(self) -> bool:
        """Setup experiment components"""
        try:
            # Import duo-talk-core
            from duo_talk_core import create_dialogue_manager
            self.create_dialogue_manager = create_dialogue_manager

            # Import duo-talk-director
            from duo_talk_director import DirectorMinimal
            self.DirectorMinimal = DirectorMinimal

            # Setup evaluator (optional)
            try:
                from evaluation.local_evaluator import LocalLLMEvaluator
                evaluator = LocalLLMEvaluator()
                if evaluator.is_available():
                    self.evaluator = evaluator
                    print("✓ Evaluator available (KoboldCPP)")
                else:
                    print("⚠ Evaluator not available, skipping metrics")
            except ImportError:
                print("⚠ LocalLLMEvaluator not found, skipping metrics")

            # Check backend availability
            manager = self.create_dialogue_manager(
                backend=self.backend,
                model=self.model,
            )
            if not manager.llm_client.is_available():
                print(f"✗ Backend not available: {self.backend}")
                return False

            print(f"✓ Backend available: {self.backend} / {self.model}")
            return True

        except ImportError as e:
            print(f"✗ Import error: {e}")
            return False

    def run(self) -> ExperimentResult:
        """Run the A/B test experiment"""
        print("\n" + "=" * 60)
        print("Director A/B Test")
        print("=" * 60)

        experiment_id = f"director_ab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = ExperimentResult(
            experiment_id=experiment_id,
            timestamp=datetime.now().isoformat(),
            conditions=["without_director", "with_director"],
            scenarios=self.scenarios,
        )

        # Run each scenario with each condition
        for scenario in self.scenarios:
            print(f"\n--- Scenario: {scenario['name']} ---")
            print(f"Prompt: {scenario['initial_prompt']}")
            print(f"Turns: {scenario['turns']}")

            for run_num in range(self.runs_per_scenario):
                print(f"\n  Run {run_num + 1}/{self.runs_per_scenario}")

                # Condition A: Without Director
                print("    [A] Without Director...", end=" ", flush=True)
                result_a = self._run_dialogue(
                    scenario=scenario,
                    with_director=False,
                )
                result.results.append(result_a)
                self._print_result_summary(result_a)

                # Condition B: With Director
                print("    [B] With Director...", end=" ", flush=True)
                result_b = self._run_dialogue(
                    scenario=scenario,
                    with_director=True,
                )
                result.results.append(result_b)
                self._print_result_summary(result_b)

        # Compute summary
        result.summary = self._compute_summary(result)

        # Save results
        self._save_result(result)

        return result

    def _run_dialogue(
        self,
        scenario: dict,
        with_director: bool,
    ) -> DialogueResult:
        """Run a single dialogue"""
        condition = "with_director" if with_director else "without_director"
        start_time = time.time()

        try:
            # Create manager with or without director
            if with_director:
                director = self.DirectorMinimal()
                manager = self.create_dialogue_manager(
                    backend=self.backend,
                    model=self.model,
                    director=director,
                    max_retries=3,
                )
            else:
                manager = self.create_dialogue_manager(
                    backend=self.backend,
                    model=self.model,
                )

            # Run dialogue session
            session = manager.run_session(
                topic=scenario["initial_prompt"],
                turns=scenario["turns"],
            )

            # Extract conversation
            conversation = [
                {"speaker": turn.speaker, "content": turn.output or turn.content}
                for turn in session.turns
            ]

            # Count retries
            total_retries = sum(turn.retry_count for turn in session.turns)

            # Evaluate if available
            metrics = None
            if self.evaluator:
                try:
                    metrics_obj = self.evaluator.evaluate_conversation(conversation)
                    metrics = metrics_obj.to_dict() if hasattr(metrics_obj, "to_dict") else None
                except Exception as e:
                    print(f"(eval failed: {e})", end=" ")

            return DialogueResult(
                condition=condition,
                scenario=scenario["name"],
                conversation=conversation,
                success=True,
                execution_time=time.time() - start_time,
                total_retries=total_retries,
                metrics=metrics,
            )

        except Exception as e:
            return DialogueResult(
                condition=condition,
                scenario=scenario["name"],
                conversation=[],
                success=False,
                execution_time=time.time() - start_time,
                error=str(e),
            )

    def _print_result_summary(self, result: DialogueResult):
        """Print a short summary of the result"""
        if result.success:
            retries = f", retries={result.total_retries}" if result.total_retries else ""
            score = ""
            if result.metrics and "overall_score" in result.metrics:
                score = f", score={result.metrics['overall_score']:.2f}"
            print(f"OK ({result.execution_time:.1f}s{retries}{score})")
        else:
            print(f"FAILED: {result.error}")

    def _compute_summary(self, result: ExperimentResult) -> dict:
        """Compute experiment summary"""
        summary = {
            "total_runs": len(result.results),
            "successful_runs": sum(1 for r in result.results if r.success),
            "by_condition": {},
            "comparison": {},
        }

        # By condition
        for condition in result.conditions:
            cond_results = [r for r in result.results if r.condition == condition and r.success]

            # Scores
            scores = [r.metrics.get("overall_score", 0) for r in cond_results if r.metrics]

            # Individual metrics
            metric_names = ["character_consistency", "topic_novelty", "relationship_quality", "naturalness", "concreteness"]
            metric_avgs = {}
            for metric in metric_names:
                values = [r.metrics.get(metric, 0) for r in cond_results if r.metrics]
                metric_avgs[metric] = sum(values) / len(values) if values else None

            # Retries (only for with_director)
            retries = [r.total_retries for r in cond_results]

            summary["by_condition"][condition] = {
                "total": len([r for r in result.results if r.condition == condition]),
                "successful": len(cond_results),
                "avg_overall_score": sum(scores) / len(scores) if scores else None,
                "avg_retries": sum(retries) / len(retries) if retries else 0,
                "metrics": metric_avgs,
            }

        # Comparison
        without = summary["by_condition"].get("without_director", {})
        with_dir = summary["by_condition"].get("with_director", {})

        if without.get("avg_overall_score") and with_dir.get("avg_overall_score"):
            score_diff = with_dir["avg_overall_score"] - without["avg_overall_score"]
            score_pct = (score_diff / without["avg_overall_score"]) * 100 if without["avg_overall_score"] else 0

            summary["comparison"] = {
                "score_difference": score_diff,
                "score_improvement_percent": score_pct,
                "avg_retries_with_director": with_dir.get("avg_retries", 0),
            }

            # Per-metric comparison
            if without.get("metrics") and with_dir.get("metrics"):
                metric_comparison = {}
                for metric in ["character_consistency", "topic_novelty", "relationship_quality", "naturalness", "concreteness"]:
                    w = without["metrics"].get(metric)
                    d = with_dir["metrics"].get(metric)
                    if w is not None and d is not None:
                        diff = d - w
                        pct = (diff / w) * 100 if w else 0
                        metric_comparison[metric] = {
                            "without": w,
                            "with": d,
                            "difference": diff,
                            "improvement_percent": pct,
                        }
                summary["comparison"]["by_metric"] = metric_comparison

        return summary

    def _save_result(self, result: ExperimentResult):
        """Save experiment results"""
        exp_dir = self.output_dir / result.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)

        # JSON result
        result_path = exp_dir / "result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        # Markdown report
        report_path = exp_dir / "REPORT.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self._generate_report(result))

        print(f"\n✓ Results saved to {exp_dir}/")

    def _generate_report(self, result: ExperimentResult) -> str:
        """Generate markdown report"""
        lines = [
            "# Director A/B Test Report",
            "",
            f"**Experiment ID**: {result.experiment_id}",
            f"**Timestamp**: {result.timestamp}",
            "",
            "## 実験概要",
            "",
            "| 項目 | 値 |",
            "|------|-----|",
            f"| Backend | {self.backend} |",
            f"| Model | {self.model} |",
            f"| Runs per scenario | {self.runs_per_scenario} |",
            f"| Total runs | {result.summary.get('total_runs', 0)} |",
            f"| Successful runs | {result.summary.get('successful_runs', 0)} |",
            "",
            "## 条件比較",
            "",
        ]

        # Condition comparison table
        without = result.summary.get("by_condition", {}).get("without_director", {})
        with_dir = result.summary.get("by_condition", {}).get("with_director", {})
        comparison = result.summary.get("comparison", {})

        lines.extend([
            "| メトリクス | Director無し | Director有り | 差分 | 改善率 |",
            "|------------|-------------|-------------|------|--------|",
        ])

        w_score = without.get("avg_overall_score")
        d_score = with_dir.get("avg_overall_score")
        if w_score is not None and d_score is not None:
            diff = comparison.get("score_difference", 0)
            pct = comparison.get("score_improvement_percent", 0)
            lines.append(f"| **Overall** | {w_score:.3f} | {d_score:.3f} | {diff:+.3f} | {pct:+.1f}% |")

        # Per-metric comparison
        by_metric = comparison.get("by_metric", {})
        for metric, data in by_metric.items():
            w = data.get("without", 0)
            d = data.get("with", 0)
            diff = data.get("difference", 0)
            pct = data.get("improvement_percent", 0)
            lines.append(f"| {metric} | {w:.3f} | {d:.3f} | {diff:+.3f} | {pct:+.1f}% |")

        # Retry stats
        lines.extend([
            "",
            "## Director統計",
            "",
            f"- 平均リトライ回数: {with_dir.get('avg_retries', 0):.2f}回/セッション",
            "",
        ])

        # Sample conversations
        lines.extend([
            "## サンプル会話",
            "",
        ])

        # Show one sample from each condition for each scenario
        shown = set()
        for r in result.results:
            key = (r.scenario, r.condition)
            if key not in shown and r.success and r.conversation:
                shown.add(key)
                condition_jp = "Director無し" if r.condition == "without_director" else "Director有り"
                lines.append(f"### {r.scenario} ({condition_jp})")
                lines.append("")
                for turn in r.conversation[:5]:  # Show first 5 turns
                    lines.append(f"**{turn['speaker']}**: {turn['content']}")
                    lines.append("")
                if r.metrics:
                    lines.append(f"*Score: {r.metrics.get('overall_score', 'N/A')}*")
                lines.append("")

        # Conclusion
        lines.extend([
            "## 結論",
            "",
        ])

        if comparison.get("score_improvement_percent"):
            pct = comparison["score_improvement_percent"]
            if pct > 5:
                lines.append(f"Director有効化により、全体スコアが **{pct:+.1f}%** 改善しました。")
            elif pct < -5:
                lines.append(f"Director有効化により、全体スコアが **{pct:+.1f}%** 低下しました。")
            else:
                lines.append(f"Director有効化による影響は軽微でした（{pct:+.1f}%）。")
        else:
            lines.append("評価スコアが取得できなかったため、定量的な比較ができませんでした。")

        lines.append("")

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Director A/B Test")
    parser.add_argument("--backend", default="ollama", help="LLM backend (ollama or koboldcpp)")
    parser.add_argument("--model", default="gemma3:12b", help="Model name")
    parser.add_argument("--runs", type=int, default=2, help="Runs per scenario")
    parser.add_argument("--output", default="results", help="Output directory")
    args = parser.parse_args()

    runner = DirectorABTest(
        backend=args.backend,
        model=args.model,
        runs_per_scenario=args.runs,
        output_dir=Path(args.output),
    )

    if not runner.setup():
        print("\n✗ Setup failed, exiting")
        sys.exit(1)

    result = runner.run()

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    comparison = result.summary.get("comparison", {})
    if comparison.get("score_improvement_percent"):
        print(f"Score improvement: {comparison['score_improvement_percent']:+.1f}%")
        print(f"Avg retries with Director: {comparison.get('avg_retries_with_director', 0):.2f}")
    else:
        print("No score comparison available (evaluator may not be running)")


if __name__ == "__main__":
    main()
