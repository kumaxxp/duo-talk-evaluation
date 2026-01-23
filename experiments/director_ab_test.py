#!/usr/bin/env python3
"""Director A/B Test: Compare dialogue quality with and without Director

This experiment compares:
- Condition A: duo-talk-core without Director
- Condition B: duo-talk-core with DirectorMinimal

Records:
- All prompts used in testing
- Thought and Output for each turn
- All rejected responses with rejection reasons
- Retry counts per turn
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
class RejectedResponse:
    """A rejected response with reason"""
    attempt: int
    response: str
    thought: Optional[str]
    output: Optional[str]
    status: str  # "RETRY", "WARN", etc.
    reason: str
    checker: str  # Which checker rejected it


@dataclass
class TurnDetail:
    """Detailed turn information including retries"""
    turn_number: int
    speaker: str
    thought: Optional[str]
    output: str
    final_content: str
    retry_count: int
    rejected_responses: list[RejectedResponse] = field(default_factory=list)


@dataclass
class DialogueResult:
    """Single dialogue result with full details"""
    condition: str  # "without_director" or "with_director"
    scenario: str
    conversation: list[dict]  # Legacy format for compatibility
    turn_details: list[TurnDetail] = field(default_factory=list)  # Detailed format
    success: bool = True
    execution_time: float = 0.0
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
    prompts: dict = field(default_factory=dict)  # System prompts used
    results: list[DialogueResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        def convert_result(r: DialogueResult) -> dict:
            d = asdict(r)
            # Convert rejected_responses in turn_details
            return d

        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "conditions": self.conditions,
            "scenarios": self.scenarios,
            "prompts": self.prompts,
            "results": [convert_result(r) for r in self.results],
            "summary": self.summary,
        }


class LoggingDirectorMinimal:
    """Director that logs all rejections for analysis"""

    def __init__(self, base_director):
        self.base_director = base_director
        self.rejection_log: list[RejectedResponse] = []
        self._current_attempt = 0

    def evaluate_response(
        self,
        speaker: str,
        response: str,
        topic: str,
        history: list[dict],
        turn_number: int,
    ):
        """Evaluate and log rejections"""
        self._current_attempt += 1

        evaluation = self.base_director.evaluate_response(
            speaker=speaker,
            response=response,
            topic=topic,
            history=history,
            turn_number=turn_number,
        )

        # Log if rejected
        if evaluation.status.name == "RETRY":
            # Determine which checker failed
            checker = "Unknown"
            if evaluation.checks_failed:
                checker = evaluation.checks_failed[0]

            rejection = RejectedResponse(
                attempt=self._current_attempt,
                response=response,
                thought=None,  # Will be filled by caller
                output=response,
                status=evaluation.status.name,
                reason=evaluation.reason,
                checker=checker,
            )
            self.rejection_log.append(rejection)

        return evaluation

    def commit_evaluation(self, response: str, evaluation) -> None:
        self.base_director.commit_evaluation(response, evaluation)

    def reset_for_new_session(self) -> None:
        self.base_director.reset_for_new_session()
        self.rejection_log = []
        self._current_attempt = 0

    def reset_for_new_turn(self) -> None:
        """Reset for a new turn (keep session, reset turn data)"""
        self._current_attempt = 0

    def get_rejections_for_turn(self) -> list[RejectedResponse]:
        """Get rejections for current turn and clear"""
        rejections = self.rejection_log.copy()
        self.rejection_log = []
        self._current_attempt = 0
        return rejections


class DirectorABTest:
    """Director A/B Test Runner with detailed logging"""

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
        self.system_prompt_sample = None
        self.fewshot_sample = None

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
            from duo_talk_core.prompt_engine import PromptEngine
            from duo_talk_core.character import get_character
            self.create_dialogue_manager = create_dialogue_manager

            # Import duo-talk-director
            from duo_talk_director import DirectorMinimal
            self.DirectorMinimal = DirectorMinimal

            # Capture sample prompts
            engine = PromptEngine()
            yana = get_character("やな")
            self.system_prompt_sample = engine.build_dialogue_prompt(
                character=yana,
                topic="サンプルトピック",
                history=[],
            )

            # Setup evaluator (optional)
            try:
                # Try Ollama evaluator first (matches our backend)
                if self.backend == "ollama":
                    from evaluation.ollama_evaluator import OllamaEvaluator
                    evaluator = OllamaEvaluator(model=self.model)
                    if evaluator.is_available():
                        self.evaluator = evaluator
                        print(f"✓ Evaluator available (Ollama / {self.model})")
                    else:
                        print("⚠ Ollama evaluator not available, skipping metrics")
                else:
                    # Fall back to KoboldCPP evaluator
                    from evaluation.local_evaluator import LocalLLMEvaluator
                    evaluator = LocalLLMEvaluator()
                    if evaluator.is_available():
                        self.evaluator = evaluator
                        print("✓ Evaluator available (KoboldCPP)")
                    else:
                        print("⚠ KoboldCPP evaluator not available, skipping metrics")
            except ImportError as e:
                print(f"⚠ Evaluator not found: {e}, skipping metrics")

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
        print("Director A/B Test (Detailed Logging)")
        print("=" * 60)

        experiment_id = f"director_ab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = ExperimentResult(
            experiment_id=experiment_id,
            timestamp=datetime.now().isoformat(),
            conditions=["without_director", "with_director"],
            scenarios=self.scenarios,
            prompts={
                "system_prompt_sample": self.system_prompt_sample,
                "user_prompts": {s["name"]: s["initial_prompt"] for s in self.scenarios},
            },
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
        """Run a single dialogue with detailed logging"""
        condition = "with_director" if with_director else "without_director"
        start_time = time.time()

        try:
            logging_director = None

            # Create manager with or without director
            if with_director:
                base_director = self.DirectorMinimal()
                logging_director = LoggingDirectorMinimal(base_director)
                manager = self.create_dialogue_manager(
                    backend=self.backend,
                    model=self.model,
                    director=logging_director,
                    max_retries=3,
                )
            else:
                manager = self.create_dialogue_manager(
                    backend=self.backend,
                    model=self.model,
                )

            # Run dialogue session manually to capture details
            from duo_talk_core.dialogue_manager import DialogueSession

            session = DialogueSession(topic=scenario["initial_prompt"], max_turns=scenario["turns"])

            if logging_director:
                logging_director.reset_for_new_session()

            speakers = ["やな", "あゆ"]
            turn_details: list[TurnDetail] = []

            for i in range(scenario["turns"]):
                speaker = speakers[i % 2]

                if logging_director:
                    logging_director.reset_for_new_turn()

                turn = manager.generate_turn(
                    speaker_name=speaker,
                    topic=scenario["initial_prompt"],
                    history=session.get_history(),
                    turn_number=i,
                )
                session.add_turn(turn)

                # Capture rejections if using director
                rejected = []
                if logging_director:
                    rejected = logging_director.get_rejections_for_turn()

                detail = TurnDetail(
                    turn_number=i,
                    speaker=speaker,
                    thought=turn.thought,
                    output=turn.output or turn.content,
                    final_content=turn.content,
                    retry_count=turn.retry_count,
                    rejected_responses=rejected,
                )
                turn_details.append(detail)

            # Extract conversation (legacy format)
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
                turn_details=turn_details,
                success=True,
                execution_time=time.time() - start_time,
                total_retries=total_retries,
                metrics=metrics,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
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

            # Retries
            retries = [r.total_retries for r in cond_results]

            # Count total rejections
            total_rejections = sum(
                len(td.rejected_responses)
                for r in cond_results
                for td in r.turn_details
            )

            summary["by_condition"][condition] = {
                "total": len([r for r in result.results if r.condition == condition]),
                "successful": len(cond_results),
                "avg_overall_score": sum(scores) / len(scores) if scores else None,
                "avg_retries": sum(retries) / len(retries) if retries else 0,
                "total_rejections": total_rejections,
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
        """Generate detailed markdown report"""
        lines = [
            "# Director A/B Test Report",
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
            f"| LLM | {self.model} |",
            f"| プロンプト構造 | Layered (v3.8.1) |",
            f"| RAG | 無効 |",
            f"| Few-shot数 | 2 |",
            f"| Temperature | 0.7 |",
            f"| max_tokens | 300 |",
            f"| max_retries | 3 |",
            f"| 実行回数/シナリオ | {self.runs_per_scenario} |",
            f"| 総実行数 | {result.summary.get('total_runs', 0)} |",
            f"| 成功実行数 | {result.summary.get('successful_runs', 0)} |",
            "",
            "---",
            "",
            "## 2. 使用プロンプト",
            "",
            "### システムプロンプト（サンプル：やな）",
            "",
            "```",
        ]

        if result.prompts.get("system_prompt_sample"):
            lines.append(result.prompts["system_prompt_sample"])
        else:
            lines.append("[プロンプト取得失敗]")

        lines.extend([
            "```",
            "",
            "### ユーザープロンプト（シナリオ別）",
            "",
            "| シナリオ | プロンプト | ターン数 |",
            "|----------|----------|---------|",
        ])

        for s in self.scenarios:
            lines.append(f"| {s['name']} | {s['initial_prompt']} | {s['turns']} |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. 条件比較サマリー",
            "",
        ])

        # Condition comparison table
        without = result.summary.get("by_condition", {}).get("without_director", {})
        with_dir = result.summary.get("by_condition", {}).get("with_director", {})

        lines.extend([
            "| メトリクス | Director無し | Director有り | 差分 |",
            "|------------|-------------|-------------|------|",
            f"| 成功数 | {without.get('successful', 0)} | {with_dir.get('successful', 0)} | - |",
            f"| 平均リトライ数 | {without.get('avg_retries', 0):.2f} | {with_dir.get('avg_retries', 0):.2f} | +{with_dir.get('avg_retries', 0) - without.get('avg_retries', 0):.2f} |",
            f"| 総不採用数 | {without.get('total_rejections', 0)} | {with_dir.get('total_rejections', 0)} | +{with_dir.get('total_rejections', 0)} |",
        ])

        lines.extend([
            "",
            "---",
            "",
            "## 4. 全会話サンプル（詳細版）",
            "",
        ])

        # Show all conversations with full details
        for r in result.results:
            if not r.success:
                continue

            condition_jp = "Director無し" if r.condition == "without_director" else "Director有り"
            lines.append(f"### {r.scenario} ({condition_jp})")
            lines.append("")

            if r.condition == "with_director":
                lines.append(f"**総リトライ数**: {r.total_retries}回")
                lines.append("")

            for td in r.turn_details:
                lines.append(f"#### Turn {td.turn_number + 1}: {td.speaker}")
                lines.append("")

                # Show rejected responses first (if any)
                if td.rejected_responses:
                    lines.append("**不採用応答:**")
                    lines.append("")
                    for rej in td.rejected_responses:
                        lines.append(f"- **Attempt {rej.attempt}** ❌")
                        lines.append(f"  - Response: {rej.output[:100]}..." if len(rej.output) > 100 else f"  - Response: {rej.output}")
                        lines.append(f"  - Status: `{rej.status}`")
                        lines.append(f"  - Checker: `{rej.checker}`")
                        lines.append(f"  - Reason: {rej.reason}")
                        lines.append("")

                # Show final accepted response
                lines.append("**採用応答:** ✅")
                lines.append("")
                if td.thought:
                    lines.append(f"- **Thought**: {td.thought}")
                lines.append(f"- **Output**: {td.output}")
                if td.retry_count > 0:
                    lines.append(f"- **リトライ回数**: {td.retry_count}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Summary and conclusion
        lines.extend([
            "## 5. 結論",
            "",
        ])

        comparison = result.summary.get("comparison", {})
        if comparison.get("score_improvement_percent"):
            pct = comparison["score_improvement_percent"]
            if pct > 5:
                lines.append(f"Director有効化により、全体スコアが **{pct:+.1f}%** 改善しました。")
            elif pct < -5:
                lines.append(f"Director有効化により、全体スコアが **{pct:+.1f}%** 低下しました。")
            else:
                lines.append(f"Director有効化による影響は軽微でした（{pct:+.1f}%）。")
        else:
            avg_retries = with_dir.get("avg_retries", 0)
            total_rejections = with_dir.get("total_rejections", 0)
            lines.extend([
                "### 定量的結果",
                "",
                f"- Director有効時の平均リトライ数: **{avg_retries:.2f}回/セッション**",
                f"- Director有効時の総不採用数: **{total_rejections}件**",
                "",
                "### 定性的評価",
                "",
                "評価スコアが取得できなかったため、会話サンプルに基づく定性的な分析が必要です。",
                "",
                "上記の会話サンプルを参照し、以下の観点で比較してください：",
                "",
                "1. **キャラクター一貫性**: 口調マーカーの出現頻度",
                "2. **話題展開**: 会話の深さと多様性",
                "3. **姉妹関係**: 自然な掛け合い",
                "4. **不採用理由の妥当性**: Directorの判断は適切か",
            ])

        lines.extend([
            "",
            "---",
            "",
            "*Report generated by duo-talk-evaluation A/B test framework*",
        ])

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Director A/B Test (Detailed)")
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

    with_dir = result.summary.get("by_condition", {}).get("with_director", {})
    print(f"Avg retries with Director: {with_dir.get('avg_retries', 0):.2f}")
    print(f"Total rejections: {with_dir.get('total_rejections', 0)}")


if __name__ == "__main__":
    main()
