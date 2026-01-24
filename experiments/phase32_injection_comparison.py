#!/usr/bin/env python3
"""Phase 3.2 Injection Comparison Test

Compare:
- Condition A: DirectorHybrid (inject_enabled=False) - observe only
- Condition B: DirectorHybrid (inject_enabled=True) - injection active

Records:
- All prompts used in testing
- Thought and Output for each turn
- All rejected responses with rejection reasons
- InjectionDecision details for Condition B
- RAG triggers and facts injected
"""

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    status: str
    reason: str
    checker: str


@dataclass
class TurnDetail:
    """Detailed turn information"""
    turn_number: int
    speaker: str
    thought: Optional[str]
    output: str
    final_content: str
    retry_count: int
    director_reason: Optional[str] = None
    rag_triggered_by: list[str] = field(default_factory=list)
    injection_decision: Optional[dict] = None
    facts_injected: list[dict] = field(default_factory=list)
    rejected_responses: list[RejectedResponse] = field(default_factory=list)


@dataclass
class DialogueResult:
    """Single dialogue result"""
    condition: str
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
    """Director wrapper that logs all evaluations"""

    def __init__(self, base_director, name: str):
        self.base_director = base_director
        self.name = name
        self.rejection_log: list[RejectedResponse] = []
        self._current_attempt = 0
        self._last_reason = None
        self._last_rag_triggers = []
        self._last_injection_decision = None
        self._last_facts_injected = []

    def evaluate_response(self, speaker, response, topic, history, turn_number):
        self._current_attempt += 1

        evaluation = self.base_director.evaluate_response(
            speaker=speaker,
            response=response,
            topic=topic,
            history=history,
            turn_number=turn_number,
        )

        self._last_reason = evaluation.reason

        # Get RAG log
        if hasattr(self.base_director, 'get_last_rag_log'):
            rag_log = self.base_director.get_last_rag_log()
            if rag_log:
                self._last_rag_triggers = rag_log.triggered_by

        if evaluation.status.name == "RETRY":
            checker = evaluation.checks_failed[0] if evaluation.checks_failed else "Unknown"
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

    def commit_evaluation(self, response, evaluation):
        self.base_director.commit_evaluation(response, evaluation)

    def reset_for_new_session(self):
        self.base_director.reset_for_new_session()
        self.rejection_log = []
        self._current_attempt = 0

    def reset_for_new_turn(self):
        self._current_attempt = 0
        self._last_reason = None
        self._last_rag_triggers = []
        self._last_injection_decision = None
        self._last_facts_injected = []

    def get_facts_for_injection(self, speaker: str, response_text: str = "", topic: str = "") -> list[dict]:
        facts = self.base_director.get_facts_for_injection(speaker, response_text, topic)
        self._last_facts_injected = facts

        if hasattr(self.base_director, 'get_last_injection_decision'):
            decision = self.base_director.get_last_injection_decision()
            if decision:
                self._last_injection_decision = decision.to_dict()

        return facts

    def get_rejections_for_turn(self) -> list[RejectedResponse]:
        rejections = self.rejection_log.copy()
        self.rejection_log = []
        self._current_attempt = 0
        return rejections


class Phase32InjectionComparison:
    """Compare inject_enabled=False vs inject_enabled=True"""

    def __init__(
        self,
        backend: str = "ollama",
        model: str = "gemma3:12b",
        runs_per_scenario: int = 1,
        output_dir: Path = Path("results"),
    ):
        self.backend = backend
        self.model = model
        self.runs_per_scenario = runs_per_scenario
        self.output_dir = output_dir
        self.evaluator = None
        self.system_prompt_sample = None
        self.llm_client = None

        # Phase 3.2 specific scenarios
        self.scenarios = [
            {
                "name": "tone_violation",
                "initial_prompt": "やな、丁寧語で答えて。「はい、わかりました」って言って。",
                "turns": 4,
                "first_speaker": "やな",
            },
            {
                "name": "addressing_violation",
                "initial_prompt": "あゆ、やなを『やなちゃん』って呼んでみて",
                "turns": 4,
                "first_speaker": "あゆ",
            },
            {
                "name": "prop_violation",
                "initial_prompt": "グラスを持って乾杯しよう！",
                "turns": 4,
                "first_speaker": "やな",
            },
        ]

    def setup(self) -> bool:
        try:
            from duo_talk_core import create_dialogue_manager, GenerationMode
            from duo_talk_core.prompt_engine import PromptEngine
            from duo_talk_core.character import get_character
            from duo_talk_core.llm_client import create_client
            self.create_dialogue_manager = create_dialogue_manager
            self.GenerationMode = GenerationMode

            from duo_talk_director import DirectorHybrid
            from duo_talk_director.llm.evaluator import EvaluatorLLMClient
            self.DirectorHybrid = DirectorHybrid

            # Mock LLM client for Director (skip LLM evaluation)
            class MockLLMClient(EvaluatorLLMClient):
                def generate(self, prompt: str) -> str:
                    return "{}"
                def is_available(self) -> bool:
                    return False

            self.MockLLMClient = MockLLMClient
            self.llm_client = create_client(backend=self.backend, model=self.model)

            # Capture sample prompts
            engine = PromptEngine()
            yana = get_character("やな")
            self.system_prompt_sample = engine.build_dialogue_prompt(
                character=yana,
                topic="サンプルトピック",
                history=[],
            )

            # Setup evaluator
            try:
                if self.backend == "ollama":
                    from evaluation.ollama_evaluator import OllamaEvaluator
                    evaluator = OllamaEvaluator(model=self.model)
                    if evaluator.is_available():
                        self.evaluator = evaluator
                        print(f"✓ Evaluator available (Ollama / {self.model})")
            except ImportError:
                print("⚠ Evaluator not available, skipping metrics")

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
        print("\n" + "=" * 60)
        print("Phase 3.2 Injection Comparison Test")
        print("=" * 60)

        experiment_id = f"phase32_injection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = ExperimentResult(
            experiment_id=experiment_id,
            timestamp=datetime.now().isoformat(),
            conditions=["observe", "inject"],
            scenarios=self.scenarios,
            prompts={
                "system_prompt_sample": self.system_prompt_sample,
                "user_prompts": {s["name"]: s["initial_prompt"] for s in self.scenarios},
            },
        )

        for scenario in self.scenarios:
            print(f"\n--- Scenario: {scenario['name']} ---")
            print(f"Prompt: {scenario['initial_prompt']}")
            print(f"Turns: {scenario['turns']}")

            for run_num in range(self.runs_per_scenario):
                print(f"\n  Run {run_num + 1}/{self.runs_per_scenario}")

                # Condition A: inject_enabled=False
                print("    [A] Observe only...", end=" ", flush=True)
                result_a = self._run_dialogue(scenario, inject_enabled=False)
                result.results.append(result_a)
                self._print_result_summary(result_a)

                # Condition B: inject_enabled=True
                print("    [B] Injection active...", end=" ", flush=True)
                result_b = self._run_dialogue(scenario, inject_enabled=True)
                result.results.append(result_b)
                self._print_result_summary(result_b)

        result.summary = self._compute_summary(result)
        self._save_result(result)

        return result

    def _run_dialogue(self, scenario: dict, inject_enabled: bool) -> DialogueResult:
        start_time = time.time()
        condition = "inject" if inject_enabled else "observe"

        try:
            base_director = self.DirectorHybrid(
                llm_client=self.MockLLMClient(),
                skip_llm_on_static_retry=True,
                rag_enabled=True,
                inject_enabled=inject_enabled,
            )

            # Add blocked prop for prop_violation
            if scenario["name"] == "prop_violation":
                base_director.rag_manager.add_blocked_prop("グラス")

            logging_director = LoggingDirector(base_director, condition)

            manager = self.create_dialogue_manager(
                backend=self.backend,
                model=self.model,
                director=logging_director,
                max_retries=3,
                generation_mode=self.GenerationMode.TWO_PASS,
            )

            from duo_talk_core.dialogue_manager import DialogueSession
            session = DialogueSession(topic=scenario["initial_prompt"], max_turns=scenario["turns"])
            logging_director.reset_for_new_session()

            speakers = ["やな", "あゆ"]
            if scenario.get("first_speaker") == "あゆ":
                speakers = ["あゆ", "やな"]

            turn_details: list[TurnDetail] = []

            for i in range(scenario["turns"]):
                speaker = speakers[i % 2]
                logging_director.reset_for_new_turn()
                base_director.clear_rag_attempts()

                turn = manager.generate_turn(
                    speaker_name=speaker,
                    topic=scenario["initial_prompt"],
                    history=session.get_history(),
                    turn_number=i,
                )
                session.add_turn(turn)

                rejected = logging_director.get_rejections_for_turn()

                detail = TurnDetail(
                    turn_number=i,
                    speaker=speaker,
                    thought=turn.thought,
                    output=turn.output or turn.content,
                    final_content=turn.content,
                    retry_count=turn.retry_count,
                    director_reason=logging_director._last_reason,
                    rag_triggered_by=logging_director._last_rag_triggers,
                    injection_decision=logging_director._last_injection_decision,
                    facts_injected=logging_director._last_facts_injected,
                    rejected_responses=rejected,
                )
                turn_details.append(detail)

            conversation = [
                {"speaker": turn.speaker, "content": turn.output or turn.content}
                for turn in session.turns
            ]

            total_retries = sum(turn.retry_count for turn in session.turns)

            metrics = None
            if self.evaluator:
                try:
                    metrics_obj = self.evaluator.evaluate_conversation(conversation)
                    metrics = metrics_obj.to_dict() if hasattr(metrics_obj, "to_dict") else None
                except Exception:
                    pass

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
        if result.success:
            retries = f", retries={result.total_retries}" if result.total_retries else ""
            score = ""
            if result.metrics and "overall_score" in result.metrics:
                score = f", score={result.metrics['overall_score']:.2f}"
            print(f"OK ({result.execution_time:.1f}s{retries}{score})")
        else:
            print(f"FAILED: {result.error}")

    def _compute_summary(self, result: ExperimentResult) -> dict:
        summary = {
            "total_runs": len(result.results),
            "successful_runs": sum(1 for r in result.results if r.success),
            "by_condition": {},
            "by_scenario": {},
            "comparison": {},
        }

        for condition in result.conditions:
            cond_results = [r for r in result.results if r.condition == condition and r.success]
            retries = [r.total_retries for r in cond_results]

            total_rag_triggers = {"prohibited_terms": 0, "blocked_props": 0, "tone_violation": 0, "addressing_violation": 0}
            total_facts_injected = 0

            for r in cond_results:
                for td in r.turn_details:
                    for trigger in td.rag_triggered_by:
                        if trigger in total_rag_triggers:
                            total_rag_triggers[trigger] += 1
                    if td.injection_decision:
                        total_facts_injected += td.injection_decision.get("facts_injected", 0)

            summary["by_condition"][condition] = {
                "total": len([r for r in result.results if r.condition == condition]),
                "successful": len(cond_results),
                "total_retries": sum(retries),
                "avg_retries": sum(retries) / len(retries) if retries else 0,
                "rag_triggers": total_rag_triggers,
                "facts_injected": total_facts_injected,
            }

        # Scenario breakdown
        for scenario in result.scenarios:
            scenario_name = scenario["name"]
            summary["by_scenario"][scenario_name] = {}
            for condition in result.conditions:
                cond_results = [r for r in result.results if r.condition == condition and r.scenario == scenario_name and r.success]
                summary["by_scenario"][scenario_name][condition] = {
                    "retries": sum(r.total_retries for r in cond_results),
                }

        # Comparison
        observe = summary["by_condition"].get("observe", {})
        inject = summary["by_condition"].get("inject", {})

        summary["comparison"] = {
            "retry_delta": observe.get("total_retries", 0) - inject.get("total_retries", 0),
        }

        return summary

    def _truncate(self, text: str, max_len: int = 80) -> str:
        if not text:
            return "-"
        text = text.replace("|", "\\|").replace("\n", " ")
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

    def _save_result(self, result: ExperimentResult):
        exp_dir = self.output_dir / result.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)

        result_path = exp_dir / "result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        report_path = exp_dir / "REPORT.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self._generate_report(result))

        print(f"\n✓ Results saved to {exp_dir}/")

    def _generate_report(self, result: ExperimentResult) -> str:
        lines = [
            "# Phase 3.2 Injection Comparison Test Report",
            "",
            "**比較対象**: DirectorHybrid (inject_enabled=False vs True)",
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
            "| RAG | 有効 |",
            "| Temperature | 0.7 |",
            "| max_tokens | 300 |",
            "| max_retries | 3 |",
            f"| 実行回数/シナリオ | {self.runs_per_scenario} |",
            f"| 総実行数 | {result.summary.get('total_runs', 0)} |",
            f"| 成功実行数 | {result.summary.get('successful_runs', 0)} |",
            "",
            "### 条件構成",
            "",
            "| 条件 | inject_enabled | 説明 |",
            "|------|:--------------:|------|",
            "| A: Observe | False | RAG観察のみ（注入なし） |",
            "| B: Inject | True | RAG注入有効（Phase 3.2） |",
            "",
            "---",
            "",
            "## 2. 使用シナリオ",
            "",
            "| シナリオ | プロンプト | ターン数 | 検出対象 |",
            "|----------|----------|:-------:|----------|",
        ]

        scenario_targets = {
            "tone_violation": "やなへの丁寧語要求",
            "addressing_violation": "あゆの呼称違反",
            "prop_violation": "存在しない小物使用",
        }

        for s in result.scenarios:
            target = scenario_targets.get(s["name"], "-")
            lines.append(f"| {s['name']} | {s['initial_prompt']} | {s['turns']} | {target} |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. 条件比較サマリー",
            "",
        ])

        observe = result.summary.get("by_condition", {}).get("observe", {})
        inject = result.summary.get("by_condition", {}).get("inject", {})
        comparison = result.summary.get("comparison", {})

        lines.extend([
            "| メトリクス | Observe (A) | Inject (B) | Delta |",
            "|------------|:-----------:|:----------:|:-----:|",
            f"| 成功数 | {observe.get('successful', 0)} | {inject.get('successful', 0)} | - |",
            f"| 総リトライ数 | {observe.get('total_retries', 0)} | {inject.get('total_retries', 0)} | {comparison.get('retry_delta', 0):+d} |",
            f"| 平均リトライ数 | {observe.get('avg_retries', 0):.2f} | {inject.get('avg_retries', 0):.2f} | - |",
            f"| Facts注入数 | - | {inject.get('facts_injected', 0)} | - |",
        ])

        # RAG Triggers
        lines.extend([
            "",
            "### RAGトリガー内訳",
            "",
            "| トリガー | Observe (A) | Inject (B) |",
            "|----------|:-----------:|:----------:|",
        ])

        obs_triggers = observe.get("rag_triggers", {})
        inj_triggers = inject.get("rag_triggers", {})
        for trigger in ["prohibited_terms", "blocked_props", "tone_violation", "addressing_violation"]:
            lines.append(f"| {trigger} | {obs_triggers.get(trigger, 0)} | {inj_triggers.get(trigger, 0)} |")

        # Scenario breakdown
        lines.extend([
            "",
            "### シナリオ別リトライ数",
            "",
            "| シナリオ | Observe (A) | Inject (B) | Delta |",
            "|----------|:-----------:|:----------:|:-----:|",
        ])

        for scenario_name, data in result.summary.get("by_scenario", {}).items():
            obs_ret = data.get("observe", {}).get("retries", 0)
            inj_ret = data.get("inject", {}).get("retries", 0)
            delta = obs_ret - inj_ret
            lines.append(f"| {scenario_name} | {obs_ret} | {inj_ret} | {delta:+d} |")

        lines.extend([
            "",
            "---",
            "",
            "## 4. 全会話サンプル",
            "",
            "### 4.1 凡例",
            "",
            "| Director値 | 意味 |",
            "|:----------:|------|",
            "| `PASS` | 採用 |",
            "| `WARN` | 警告付き採用 |",
            "| **`RETRY`** | 不採用（取り消し線で表示） |",
            "",
            "### 4.2 会話サンプル",
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
            observe_results = [r for r in results_list if r.condition == "observe"]
            inject_results = [r for r in results_list if r.condition == "inject"]

            for run_idx, (obs, inj) in enumerate(zip(observe_results, inject_results), 1):
                lines.append(f"#### {scenario_name} - Run {run_idx}")
                lines.append("")

                # Observe section
                lines.append(f"**Observe (inject_enabled=False)** (リトライ: {obs.total_retries}回)")
                lines.append("")
                lines.append("| Turn | Speaker | Thought | Output | Director |")
                lines.append("|:----:|:-------:|---------|--------|:--------:|")

                for td in obs.turn_details:
                    for rej in td.rejected_responses:
                        lines.append(f"| {td.turn_number + 1} | {td.speaker} | ~~{self._truncate(rej.thought)}~~ | ~~{self._truncate(rej.output)}~~ | **`RETRY`** |")
                    lines.append(f"| {td.turn_number + 1} | {td.speaker} | {self._truncate(td.thought)} | {self._truncate(td.output)} | `PASS` |")

                lines.append("")

                # Inject section
                lines.append(f"**Inject (inject_enabled=True)** (リトライ: {inj.total_retries}回)")
                lines.append("")
                lines.append("| Turn | Speaker | Thought | Output | Director | Injection |")
                lines.append("|:----:|:-------:|---------|--------|:--------:|-----------|")

                for td in inj.turn_details:
                    for rej in td.rejected_responses:
                        lines.append(f"| {td.turn_number + 1} | {td.speaker} | ~~{self._truncate(rej.thought)}~~ | ~~{self._truncate(rej.output)}~~ | **`RETRY`** | - |")

                    injection_info = "-"
                    if td.injection_decision and td.injection_decision.get("would_inject"):
                        reasons = td.injection_decision.get("reasons", [])
                        injection_info = ", ".join(reasons[:2]) if reasons else "injected"

                    lines.append(f"| {td.turn_number + 1} | {td.speaker} | {self._truncate(td.thought)} | {self._truncate(td.output)} | `PASS` | {injection_info} |")

                lines.append("")
                lines.append("---")
                lines.append("")

        # Conclusion
        lines.extend([
            "## 5. 結論",
            "",
        ])

        retry_delta = comparison.get("retry_delta", 0)
        if retry_delta > 0:
            lines.append(f"**✅ Injection有効**: リトライ数が **{retry_delta}回** 削減された。")
        elif retry_delta < 0:
            lines.append(f"**⚠️ Injection効果なし**: リトライ数が **{abs(retry_delta)}回** 増加した。")
        else:
            lines.append("**➖ 差なし**: リトライ数に変化なし。")

        lines.extend([
            "",
            "---",
            "",
            "*Report generated by Phase 3.2 Injection Comparison Test*",
        ])

        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3.2 Injection Comparison Test")
    parser.add_argument("--backend", default="ollama", help="LLM backend")
    parser.add_argument("--model", default="gemma3:12b", help="Model name")
    parser.add_argument("--runs", type=int, default=1, help="Runs per scenario")
    parser.add_argument("--output", default="results", help="Output directory")
    args = parser.parse_args()

    runner = Phase32InjectionComparison(
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

    observe = result.summary.get("by_condition", {}).get("observe", {})
    inject = result.summary.get("by_condition", {}).get("inject", {})
    comparison = result.summary.get("comparison", {})

    print(f"Observe (A) - Total retries: {observe.get('total_retries', 0)}")
    print(f"Inject (B)  - Total retries: {inject.get('total_retries', 0)}, Facts injected: {inject.get('facts_injected', 0)}")
    print(f"Delta: {comparison.get('retry_delta', 0):+d}")


if __name__ == "__main__":
    main()
