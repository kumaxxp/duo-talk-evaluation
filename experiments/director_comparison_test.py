#!/usr/bin/env python3
"""Director Comparison Test: Compare DirectorMinimal vs DirectorHybrid

This experiment compares:
- Condition A: DirectorMinimal (static checks only)
- Condition B: DirectorHybrid (static + LLM evaluation)

Records:
- All prompts used in testing
- Thought and Output for each turn
- All rejected responses with rejection reasons
- LLM evaluation scores for DirectorHybrid
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
    director_reason: Optional[str] = None  # Director's full reason
    llm_scores: Optional[dict] = None  # LLM evaluation scores (for Hybrid)
    rejected_responses: list[RejectedResponse] = field(default_factory=list)


@dataclass
class DialogueResult:
    """Single dialogue result with full details"""
    condition: str  # "minimal" or "hybrid"
    scenario: str
    conversation: list[dict]
    turn_details: list[TurnDetail] = field(default_factory=list)
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
    prompts: dict = field(default_factory=dict)
    results: list[DialogueResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "timestamp": self.timestamp,
            "conditions": self.conditions,
            "scenarios": self.scenarios,
            "prompts": self.prompts,
            "results": [asdict(r) for r in self.results],
            "summary": self.summary,
        }


class LoggingDirector:
    """Director wrapper that logs all evaluations for analysis"""

    def __init__(self, base_director, name: str):
        self.base_director = base_director
        self.name = name
        self.rejection_log: list[RejectedResponse] = []
        self._current_attempt = 0
        self._last_reason = None
        self._last_llm_scores = None

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

        self._last_reason = evaluation.reason

        # Extract LLM scores if available (DirectorHybrid)
        if hasattr(evaluation, 'llm_score') and evaluation.llm_score:
            self._last_llm_scores = {
                'character_consistency': evaluation.llm_score.character_consistency,
                'topic_novelty': evaluation.llm_score.topic_novelty,
                'relationship_quality': evaluation.llm_score.relationship_quality,
                'naturalness': evaluation.llm_score.naturalness,
                'concreteness': evaluation.llm_score.concreteness,
                'overall_score': evaluation.llm_score.overall_score,
            }
        else:
            self._last_llm_scores = None

        # Log if rejected
        if evaluation.status.name == "RETRY":
            checker = "Unknown"
            if evaluation.checks_failed:
                checker = evaluation.checks_failed[0]

            rejection = RejectedResponse(
                attempt=self._current_attempt,
                response=response,
                thought=None,
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
        self._last_reason = None
        self._last_llm_scores = None

    def reset_for_new_turn(self) -> None:
        """Reset for a new turn"""
        self._current_attempt = 0
        self._last_reason = None
        self._last_llm_scores = None

    def get_rejections_for_turn(self) -> list[RejectedResponse]:
        """Get rejections for current turn and clear"""
        rejections = self.rejection_log.copy()
        self.rejection_log = []
        self._current_attempt = 0
        return rejections

    def get_last_reason(self) -> Optional[str]:
        return self._last_reason

    def get_last_llm_scores(self) -> Optional[dict]:
        return self._last_llm_scores


class DirectorComparisonTest:
    """Compare DirectorMinimal vs DirectorHybrid"""

    def __init__(
        self,
        backend: str = "ollama",
        model: str = "gemma3:12b",
        runs_per_scenario: int = 2,
        output_dir: Path = Path("results"),
    ):
        self.backend = backend
        self.model = model
        self.runs_per_scenario = runs_per_scenario
        self.output_dir = output_dir
        self.evaluator = None
        self.system_prompt_sample = None
        self.llm_client = None

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
            from duo_talk_core.llm_client import create_client
            self.create_dialogue_manager = create_dialogue_manager

            # Import duo-talk-director
            from duo_talk_director import DirectorMinimal, DirectorHybrid
            self.DirectorMinimal = DirectorMinimal
            self.DirectorHybrid = DirectorHybrid

            # Create LLM client for DirectorHybrid
            self.llm_client = create_client(backend=self.backend, model=self.model)

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
                if self.backend == "ollama":
                    from evaluation.ollama_evaluator import OllamaEvaluator
                    evaluator = OllamaEvaluator(model=self.model)
                    if evaluator.is_available():
                        self.evaluator = evaluator
                        print(f"✓ Evaluator available (Ollama / {self.model})")
                    else:
                        print("⚠ Ollama evaluator not available, skipping metrics")
            except ImportError as e:
                print(f"⚠ Evaluator not found: {e}, skipping metrics")

            # Check backend availability
            if not self.llm_client.is_available():
                print(f"✗ Backend not available: {self.backend}")
                return False

            print(f"✓ Backend available: {self.backend} / {self.model}")
            return True

        except ImportError as e:
            print(f"✗ Import error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run(self) -> ExperimentResult:
        """Run the comparison experiment"""
        print("\n" + "=" * 60)
        print("Director Comparison: Minimal vs Hybrid")
        print("=" * 60)

        experiment_id = f"director_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = ExperimentResult(
            experiment_id=experiment_id,
            timestamp=datetime.now().isoformat(),
            conditions=["minimal", "hybrid"],
            scenarios=self.scenarios,
            prompts={
                "system_prompt_sample": self.system_prompt_sample,
                "user_prompts": {s["name"]: s["initial_prompt"] for s in self.scenarios},
            },
        )

        # Run each scenario
        for scenario in self.scenarios:
            print(f"\n--- Scenario: {scenario['name']} ---")
            print(f"Prompt: {scenario['initial_prompt']}")
            print(f"Turns: {scenario['turns']}")

            for run_num in range(self.runs_per_scenario):
                print(f"\n  Run {run_num + 1}/{self.runs_per_scenario}")

                # Condition A: DirectorMinimal
                print("    [A] DirectorMinimal...", end=" ", flush=True)
                result_a = self._run_dialogue(
                    scenario=scenario,
                    director_type="minimal",
                )
                result.results.append(result_a)
                self._print_result_summary(result_a)

                # Condition B: DirectorHybrid
                print("    [B] DirectorHybrid...", end=" ", flush=True)
                result_b = self._run_dialogue(
                    scenario=scenario,
                    director_type="hybrid",
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
        director_type: str,
    ) -> DialogueResult:
        """Run a single dialogue"""
        start_time = time.time()

        try:
            # Create director based on type
            if director_type == "minimal":
                base_director = self.DirectorMinimal()
            else:  # hybrid
                base_director = self.DirectorHybrid(llm_client=self.llm_client)

            logging_director = LoggingDirector(base_director, director_type)

            manager = self.create_dialogue_manager(
                backend=self.backend,
                model=self.model,
                director=logging_director,
                max_retries=3,
            )

            # Run dialogue session
            from duo_talk_core.dialogue_manager import DialogueSession
            session = DialogueSession(topic=scenario["initial_prompt"], max_turns=scenario["turns"])
            logging_director.reset_for_new_session()

            speakers = ["やな", "あゆ"]
            turn_details: list[TurnDetail] = []

            for i in range(scenario["turns"]):
                speaker = speakers[i % 2]
                logging_director.reset_for_new_turn()

                turn = manager.generate_turn(
                    speaker_name=speaker,
                    topic=scenario["initial_prompt"],
                    history=session.get_history(),
                    turn_number=i,
                )
                session.add_turn(turn)

                # Capture details
                rejected = logging_director.get_rejections_for_turn()

                detail = TurnDetail(
                    turn_number=i,
                    speaker=speaker,
                    thought=turn.thought,
                    output=turn.output or turn.content,
                    final_content=turn.content,
                    retry_count=turn.retry_count,
                    director_reason=logging_director.get_last_reason(),
                    llm_scores=logging_director.get_last_llm_scores(),
                    rejected_responses=rejected,
                )
                turn_details.append(detail)

            # Extract conversation
            conversation = [
                {"speaker": turn.speaker, "content": turn.output or turn.content}
                for turn in session.turns
            ]

            total_retries = sum(turn.retry_count for turn in session.turns)

            # Evaluate if available
            metrics = None
            if self.evaluator:
                try:
                    metrics_obj = self.evaluator.evaluate_conversation(conversation)
                    metrics = metrics_obj.to_dict() if hasattr(metrics_obj, "to_dict") else None
                except Exception as e:
                    print(f"(eval: {e})", end=" ")

            return DialogueResult(
                condition=director_type,
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
                condition=director_type,
                scenario=scenario["name"],
                conversation=[],
                success=False,
                execution_time=time.time() - start_time,
                error=str(e),
            )

    def _print_result_summary(self, result: DialogueResult):
        """Print short summary"""
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

        for condition in result.conditions:
            cond_results = [r for r in result.results if r.condition == condition and r.success]

            scores = [r.metrics.get("overall_score", 0) for r in cond_results if r.metrics]
            retries = [r.total_retries for r in cond_results]

            # Collect LLM scores for hybrid
            llm_scores_avg = {}
            if condition == "hybrid":
                llm_metric_names = ["character_consistency", "topic_novelty", "relationship_quality", "naturalness", "concreteness", "overall_score"]
                for metric in llm_metric_names:
                    values = []
                    for r in cond_results:
                        for td in r.turn_details:
                            if td.llm_scores and metric in td.llm_scores:
                                values.append(td.llm_scores[metric])
                    llm_scores_avg[metric] = sum(values) / len(values) if values else None

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
                "llm_scores_avg": llm_scores_avg if llm_scores_avg else None,
            }

        # Comparison
        minimal = summary["by_condition"].get("minimal", {})
        hybrid = summary["by_condition"].get("hybrid", {})

        summary["comparison"] = {
            "retry_difference": hybrid.get("avg_retries", 0) - minimal.get("avg_retries", 0),
            "rejection_difference": hybrid.get("total_rejections", 0) - minimal.get("total_rejections", 0),
        }

        if minimal.get("avg_overall_score") and hybrid.get("avg_overall_score"):
            summary["comparison"]["score_difference"] = hybrid["avg_overall_score"] - minimal["avg_overall_score"]

        return summary

    def _escape_markdown(self, text: str) -> str:
        """Escape markdown special characters for display"""
        if not text:
            return "-"
        # Escape pipe for tables, keep newlines for readability
        text = text.replace("|", "\\|")
        return text

    def _format_turn(self, turn_num: int, speaker: str, thought: str, output: str,
                     director_status: str, llm_score: str = None, rejected: bool = False) -> list[str]:
        """Format a single turn for display"""
        lines = []
        prefix = "~~" if rejected else ""
        suffix = "~~" if rejected else ""

        lines.append(f"#### Turn {turn_num}: {speaker} {'❌' if rejected else '✅'}")
        lines.append("")
        lines.append(f"**Director**: `{director_status}`" + (f" | **LLM Score**: {llm_score}" if llm_score else ""))
        lines.append("")
        lines.append(f"**Thought**:")
        lines.append(f"> {prefix}{self._escape_markdown(thought or '-')}{suffix}")
        lines.append("")
        lines.append(f"**Output**:")
        lines.append(f"> {prefix}{self._escape_markdown(output)}{suffix}")
        lines.append("")
        return lines

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
            "# Director Comparison Test Report",
            "",
            "**比較対象**: DirectorMinimal vs DirectorHybrid (LLM評価付き)",
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
            "| プロンプト構造 | Layered (v3.8.1) |",
            "| RAG | 無効 |",
            "| Temperature | 0.7 |",
            "| max_tokens | 300 |",
            "| max_retries | 3 |",
            f"| 実行回数/シナリオ | {self.runs_per_scenario} |",
            f"| 総実行数 | {result.summary.get('total_runs', 0)} |",
            f"| 成功実行数 | {result.summary.get('successful_runs', 0)} |",
            "",
            "### Director構成",
            "",
            "| 条件 | Director | 説明 |",
            "|------|----------|------|",
            "| A: Minimal | DirectorMinimal | 静的チェックのみ（tone, praise, setting, format, thought, context） |",
            "| B: Hybrid | DirectorHybrid | 静的チェック + LLM 5軸評価 |",
            "",
            "---",
            "",
            "## 2. 条件比較サマリー",
            "",
        ]

        minimal = result.summary.get("by_condition", {}).get("minimal", {})
        hybrid = result.summary.get("by_condition", {}).get("hybrid", {})
        comparison = result.summary.get("comparison", {})

        lines.extend([
            "| メトリクス | Minimal | Hybrid | 差分 |",
            "|------------|---------|--------|------|",
            f"| 成功数 | {minimal.get('successful', 0)} | {hybrid.get('successful', 0)} | - |",
            f"| 平均リトライ数 | {minimal.get('avg_retries', 0):.2f} | {hybrid.get('avg_retries', 0):.2f} | {comparison.get('retry_difference', 0):+.2f} |",
            f"| 総不採用数 | {minimal.get('total_rejections', 0)} | {hybrid.get('total_rejections', 0)} | {comparison.get('rejection_difference', 0):+d} |",
        ])

        if minimal.get("avg_overall_score") and hybrid.get("avg_overall_score"):
            lines.append(f"| 評価スコア | {minimal['avg_overall_score']:.2f} | {hybrid['avg_overall_score']:.2f} | {comparison.get('score_difference', 0):+.2f} |")

        # LLM Scores for Hybrid
        if hybrid.get("llm_scores_avg"):
            lines.extend([
                "",
                "### DirectorHybrid 内部LLM評価スコア（平均）",
                "",
                "| 軸 | 平均スコア |",
                "|-----|----------|",
            ])
            for key, val in hybrid["llm_scores_avg"].items():
                if val is not None:
                    lines.append(f"| {key} | {val:.3f} |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. 全会話サンプル",
            "",
            "### 凡例",
            "",
            "| Director値 | 意味 |",
            "|:----------:|------|",
            "| `PASS` | 採用 |",
            "| `WARN` | 警告付き採用 |",
            "| **`RETRY`** | 不採用（取り消し線で表示） |",
            "",
        ])

        # Group by scenario
        scenarios_runs: dict[str, list] = {}
        for r in result.results:
            if not r.success:
                continue
            if r.scenario not in scenarios_runs:
                scenarios_runs[r.scenario] = []
            scenarios_runs[r.scenario].append(r)

        for scenario_name, results_list in scenarios_runs.items():
            minimal_results = [r for r in results_list if r.condition == "minimal"]
            hybrid_results = [r for r in results_list if r.condition == "hybrid"]

            for run_idx, (mi, hy) in enumerate(zip(minimal_results, hybrid_results), 1):
                lines.append(f"### {scenario_name} - Run {run_idx}")
                lines.append("")

                # Minimal section
                lines.append(f"**DirectorMinimal** (リトライ: {mi.total_retries}回)")
                lines.append("")

                for td in mi.turn_details:
                    # Show rejected responses first
                    for rej in td.rejected_responses:
                        lines.extend(self._format_turn(
                            td.turn_number + 1, td.speaker,
                            rej.thought, rej.output,
                            "RETRY", rejected=True
                        ))

                    # Show accepted response
                    lines.extend(self._format_turn(
                        td.turn_number + 1, td.speaker,
                        td.thought, td.output,
                        "PASS"
                    ))

                # Hybrid section
                lines.append(f"**DirectorHybrid** (リトライ: {hy.total_retries}回)")
                lines.append("")

                for td in hy.turn_details:
                    # Show rejected responses first
                    for rej in td.rejected_responses:
                        lines.extend(self._format_turn(
                            td.turn_number + 1, td.speaker,
                            rej.thought, rej.output,
                            "RETRY", rejected=True
                        ))

                    # Show accepted response with LLM score
                    llm_score = None
                    if td.llm_scores and "overall_score" in td.llm_scores:
                        llm_score = f"{td.llm_scores['overall_score']:.2f}"
                    lines.extend(self._format_turn(
                        td.turn_number + 1, td.speaker,
                        td.thought, td.output,
                        "PASS", llm_score=llm_score
                    ))

                lines.append("")
                lines.append("---")
                lines.append("")

        # Conclusion
        lines.extend([
            "## 4. 分析と結論",
            "",
        ])

        retry_diff = comparison.get("retry_difference", 0)
        if retry_diff > 0:
            lines.append(f"- DirectorHybridはMinimalより平均 **{retry_diff:.2f}回** 多くリトライを要求")
            lines.append("- LLM評価によりより厳格な品質管理が行われている")
        elif retry_diff < 0:
            lines.append(f"- DirectorHybridはMinimalより平均 **{abs(retry_diff):.2f}回** 少ないリトライ")
        else:
            lines.append("- 両Director間でリトライ回数に差はなかった")

        lines.extend([
            "",
            "### 推奨事項",
            "",
            "- **品質重視**: DirectorHybrid（LLM評価で5軸の品質保証）",
            "- **速度重視**: DirectorMinimal（静的チェックのみで高速）",
            "",
            "---",
            "",
            "*Report generated by duo-talk-evaluation comparison test framework*",
        ])

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Director Comparison Test")
    parser.add_argument("--backend", default="ollama", help="LLM backend")
    parser.add_argument("--model", default="gemma3:12b", help="Model name")
    parser.add_argument("--runs", type=int, default=2, help="Runs per scenario")
    parser.add_argument("--output", default="results", help="Output directory")
    args = parser.parse_args()

    runner = DirectorComparisonTest(
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

    minimal = result.summary.get("by_condition", {}).get("minimal", {})
    hybrid = result.summary.get("by_condition", {}).get("hybrid", {})

    print(f"DirectorMinimal - Avg retries: {minimal.get('avg_retries', 0):.2f}, Rejections: {minimal.get('total_rejections', 0)}")
    print(f"DirectorHybrid  - Avg retries: {hybrid.get('avg_retries', 0):.2f}, Rejections: {hybrid.get('total_rejections', 0)}")


if __name__ == "__main__":
    main()
