#!/usr/bin/env python3
"""Director A/B Test: Compare dialogue quality with various Director configurations

This experiment supports multiple comparison modes:
- Default: Without Director vs With Director
- RAG mode (--rag): Director with RAG observation enabled
- Inject mode (--inject): Director with RAG injection enabled (Phase 3.2)
- AB mode (--ab): Compare RAG observe-only vs RAG inject

Records:
- All prompts used in testing
- Thought and Output for each turn
- All rejected responses with rejection reasons
- Retry counts per turn
- InjectionDecision details (Phase 3.2)
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
    rag: Optional[dict] = None  # Phase 3.1: RAG log entry


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
    rag: Optional[dict] = None  # Phase 3.1: RAG log entry for accepted response
    injection_decision: Optional[dict] = None  # Phase 3.2: InjectionDecision details
    facts_injected: list[dict] = field(default_factory=list)  # Phase 3.2: Facts injected


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

    def __init__(self, base_director, rag_enabled: bool = False, inject_enabled: bool = False):
        self.base_director = base_director
        self.rag_enabled = rag_enabled
        self.inject_enabled = inject_enabled
        self.rejection_log: list[RejectedResponse] = []
        self._current_attempt = 0
        self._last_rag_log: Optional[dict] = None  # Phase 3.1
        self._last_injection_decision: Optional[dict] = None  # Phase 3.2
        self._last_facts_injected: list[dict] = []  # Phase 3.2

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

        # Phase 3.1: Capture RAG log if available
        rag_log = None
        if hasattr(self.base_director, 'get_last_rag_log'):
            rag_entry = self.base_director.get_last_rag_log()
            if rag_entry:
                rag_log = rag_entry.to_dict()
        self._last_rag_log = rag_log

        # Phase 3.2: Capture InjectionDecision if available
        if hasattr(self.base_director, 'get_last_injection_decision'):
            decision = self.base_director.get_last_injection_decision()
            if decision:
                self._last_injection_decision = decision.to_dict()

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
                rag=rag_log,  # Phase 3.1
            )
            self.rejection_log.append(rejection)

        return evaluation

    def commit_evaluation(self, response: str, evaluation) -> None:
        self.base_director.commit_evaluation(response, evaluation)

    def reset_for_new_session(self) -> None:
        self.base_director.reset_for_new_session()
        self.rejection_log = []
        self._current_attempt = 0
        self._last_rag_log = None
        self._last_injection_decision = None
        self._last_facts_injected = []

    def reset_for_new_turn(self) -> None:
        """Reset for a new turn (keep session, reset turn data)"""
        self._current_attempt = 0
        self._last_injection_decision = None
        self._last_facts_injected = []
        # Phase 3.1: Clear RAG attempts for new turn
        if hasattr(self.base_director, 'clear_rag_attempts'):
            self.base_director.clear_rag_attempts()

    def get_rejections_for_turn(self) -> list[RejectedResponse]:
        """Get rejections for current turn and clear"""
        rejections = self.rejection_log.copy()
        self.rejection_log = []
        self._current_attempt = 0
        return rejections

    def get_last_rag_log(self) -> Optional[dict]:
        """Get the last RAG log entry (Phase 3.1)"""
        return self._last_rag_log

    def get_last_injection_decision(self) -> Optional[dict]:
        """Get the last InjectionDecision (Phase 3.2)"""
        return self._last_injection_decision

    def get_last_facts_injected(self) -> list[dict]:
        """Get the facts injected in the last call (Phase 3.2)"""
        return self._last_facts_injected

    def get_facts_for_injection(self, speaker: str, response_text: str = "", topic: str = "") -> list[dict]:
        """Wrap get_facts_for_injection to capture injected facts (Phase 3.2)"""
        if hasattr(self.base_director, 'get_facts_for_injection'):
            facts = self.base_director.get_facts_for_injection(speaker, response_text, topic)
            self._last_facts_injected = facts
            # Also capture decision
            if hasattr(self.base_director, 'get_last_injection_decision'):
                decision = self.base_director.get_last_injection_decision()
                if decision:
                    self._last_injection_decision = decision.to_dict()
            return facts
        return []


class DirectorABTest:
    """Director A/B Test Runner with detailed logging"""

    # Preset scenarios
    PRESET_STANDARD = [
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

    PRESET_PHASE32 = [
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
            "blocked_props": ["グラス"],  # Phase 3.2: Register blocked prop
        },
    ]

    def __init__(
        self,
        backend: str = "ollama",
        model: str = "gemma3:12b",
        runs_per_scenario: int = 3,
        output_dir: Path = Path("results"),
        rag_enabled: bool = False,
        inject_enabled: bool = False,
        ab_mode: bool = False,
        preset: str = "standard",
    ):
        self.backend = backend
        self.model = model
        self.runs_per_scenario = runs_per_scenario
        self.output_dir = output_dir
        self.evaluator = None
        self.system_prompt_sample = None
        self.fewshot_sample = None

        # Phase 3.2: RAG/Inject settings
        self.rag_enabled = rag_enabled
        self.inject_enabled = inject_enabled
        self.ab_mode = ab_mode

        # inject implies rag (prevent user error)
        if self.inject_enabled:
            self.rag_enabled = True

        # Select preset scenarios
        if preset == "phase32":
            self.scenarios = self.PRESET_PHASE32.copy()
        else:
            self.scenarios = self.PRESET_STANDARD.copy()

    def setup(self) -> bool:
        """Setup experiment components"""
        try:
            # Import duo-talk-core
            from duo_talk_core import create_dialogue_manager
            from duo_talk_core.prompt_engine import PromptEngine
            from duo_talk_core.character import get_character
            self.create_dialogue_manager = create_dialogue_manager

            # Import duo-talk-director
            from duo_talk_director import DirectorMinimal, DirectorHybrid
            self.DirectorMinimal = DirectorMinimal
            self.DirectorHybrid = DirectorHybrid

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

    def build_director(
        self,
        rag_enabled: bool = False,
        inject_enabled: bool = False,
        scenario: Optional[dict] = None,
    ):
        """Build a Director instance with specified configuration (Phase 3.2)

        Args:
            rag_enabled: Enable RAG observation
            inject_enabled: Enable RAG injection (implies rag_enabled)
            scenario: Optional scenario dict for blocked_props setup

        Returns:
            Tuple of (base_director, logging_director)
        """
        # inject implies rag
        if inject_enabled:
            rag_enabled = True

        # Create mock LLM client for DirectorHybrid (skip LLM evaluation)
        from duo_talk_director.llm.evaluator import EvaluatorLLMClient

        class MockLLMClient(EvaluatorLLMClient):
            def generate(self, prompt: str) -> str:
                return "{}"  # Return empty JSON to skip LLM scoring

            def is_available(self) -> bool:
                return False

        # Always use DirectorHybrid (DirectorMinimal is legacy)
        base_director = self.DirectorHybrid(
            llm_client=MockLLMClient(),
            skip_llm_on_static_retry=True,
            rag_enabled=rag_enabled,
            inject_enabled=inject_enabled,
        )

        # Phase 3.2: Register blocked props for scenario
        if scenario and scenario.get("blocked_props"):
            for prop in scenario["blocked_props"]:
                base_director.rag_manager.add_blocked_prop(prop)

        logging_director = LoggingDirectorMinimal(
            base_director,
            rag_enabled=rag_enabled,
            inject_enabled=inject_enabled,
        )

        return base_director, logging_director

    def run(self) -> ExperimentResult:
        """Run the A/B test experiment"""
        print("\n" + "=" * 60)
        print("Director A/B Test (Detailed Logging)")
        print("=" * 60)

        # Log execution parameters for debugging/reproducibility
        git_hash = self._get_git_hash()
        preset_name = "phase32" if self.scenarios == self.PRESET_PHASE32 else "standard"
        print(f"Git Hash: {git_hash}")
        print(f"Preset: {preset_name} ({len(self.scenarios)} scenarios)")
        print(f"Runs per scenario: {self.runs_per_scenario}")
        print(f"Backend: {self.backend} / {self.model}")

        # Determine conditions based on mode
        if self.ab_mode:
            # AB mode: Compare RAG observe-only vs RAG inject
            conditions = ["observe", "inject"]
            condition_configs = {
                "observe": {"rag_enabled": True, "inject_enabled": False},
                "inject": {"rag_enabled": True, "inject_enabled": True},
            }
            print("Mode: A/B (observe vs inject)")
        elif self.inject_enabled:
            # Single condition: inject enabled
            conditions = ["inject"]
            condition_configs = {
                "inject": {"rag_enabled": True, "inject_enabled": True},
            }
            print("Mode: Inject (RAG injection enabled)")
        elif self.rag_enabled:
            # Single condition: rag enabled (observe only)
            conditions = ["observe"]
            condition_configs = {
                "observe": {"rag_enabled": True, "inject_enabled": False},
            }
            print("Mode: Observe (RAG observation only)")
        else:
            # Default: Compare without director vs with director
            conditions = ["without_director", "with_director"]
            condition_configs = {
                "without_director": {"rag_enabled": False, "inject_enabled": False, "no_director": True},
                "with_director": {"rag_enabled": False, "inject_enabled": False},
            }
            print("Mode: Default (without vs with Director)")

        experiment_id = f"director_ab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = ExperimentResult(
            experiment_id=experiment_id,
            timestamp=datetime.now().isoformat(),
            conditions=conditions,
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

                for idx, condition in enumerate(conditions):
                    config = condition_configs[condition]
                    label = chr(ord('A') + idx)  # A, B, C, ...
                    print(f"    [{label}] {condition}...", end=" ", flush=True)

                    result_item = self._run_dialogue(
                        scenario=scenario,
                        with_director=not config.get("no_director", False),
                        rag_enabled=config.get("rag_enabled", False),
                        inject_enabled=config.get("inject_enabled", False),
                        condition_name=condition,
                    )
                    result.results.append(result_item)
                    self._print_result_summary(result_item)

        # Compute summary
        result.summary = self._compute_summary(result)

        # Save results
        self._save_result(result)

        return result

    def _run_dialogue(
        self,
        scenario: dict,
        with_director: bool,
        rag_enabled: bool = False,
        inject_enabled: bool = False,
        condition_name: Optional[str] = None,
    ) -> DialogueResult:
        """Run a single dialogue with detailed logging"""
        condition = condition_name or ("with_director" if with_director else "without_director")
        start_time = time.time()

        try:
            logging_director = None

            # Create manager with or without director
            if with_director:
                # Use build_director for consistent configuration
                _base_director, logging_director = self.build_director(
                    rag_enabled=rag_enabled,
                    inject_enabled=inject_enabled,
                    scenario=scenario,
                )
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

            # Determine speaker order
            speakers = ["やな", "あゆ"]
            if scenario.get("first_speaker") == "あゆ":
                speakers = ["あゆ", "やな"]

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
                rag_log = None
                injection_decision = None
                facts_injected = []
                if logging_director:
                    rejected = logging_director.get_rejections_for_turn()
                    rag_log = logging_director.get_last_rag_log()  # Phase 3.1
                    injection_decision = logging_director.get_last_injection_decision()  # Phase 3.2
                    facts_injected = logging_director.get_last_facts_injected()  # Phase 3.2

                detail = TurnDetail(
                    turn_number=i,
                    speaker=speaker,
                    thought=turn.thought,
                    output=turn.output or turn.content,
                    final_content=turn.content,
                    retry_count=turn.retry_count,
                    rejected_responses=rejected,
                    rag=rag_log,  # Phase 3.1
                    injection_decision=injection_decision,  # Phase 3.2
                    facts_injected=facts_injected,  # Phase 3.2
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

            # Phase 3.2: Count facts injected and injection triggers
            total_facts_injected = 0
            injection_triggers = {
                "prohibited_terms": 0,
                "blocked_props": 0,
                "tone_violation": 0,
                "addressing_violation": 0,
            }
            for r in cond_results:
                for td in r.turn_details:
                    if td.facts_injected:
                        total_facts_injected += len(td.facts_injected)
                    if td.injection_decision:
                        for reason in td.injection_decision.get("reasons", []):
                            if reason in injection_triggers:
                                injection_triggers[reason] += 1

            summary["by_condition"][condition] = {
                "total": len([r for r in result.results if r.condition == condition]),
                "successful": len(cond_results),
                "avg_overall_score": sum(scores) / len(scores) if scores else None,
                "avg_retries": sum(retries) / len(retries) if retries else 0,
                "total_retries": sum(retries),
                "total_rejections": total_rejections,
                "total_facts_injected": total_facts_injected,
                "injection_triggers": injection_triggers,
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

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text for table display, escaping pipe characters"""
        if not text:
            return "-"
        # Escape pipe characters for markdown tables
        text = text.replace("|", "\\|")
        # Remove newlines
        text = text.replace("\n", " ")
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

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

    def _get_git_hash(self) -> str:
        """Get current git commit hash for reproducibility"""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _generate_report(self, result: ExperimentResult) -> str:
        """Generate detailed markdown report"""
        git_hash = self._get_git_hash()

        lines = [
            "# Director A/B Test Report",
            "",
            f"**Experiment ID**: {result.experiment_id}",
            f"**Timestamp**: {result.timestamp}",
            f"**Git Hash**: {git_hash}",
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
        ]

        # ABモードの場合は条件別設定を表示
        if self.ab_mode:
            lines.extend([
                "| モード | A/B比較 (observe vs inject) |",
                "| A条件 | RAG観察のみ (inject_enabled=False) |",
                "| B条件 | RAG注入有効 (inject_enabled=True) |",
            ])
        else:
            lines.extend([
                f"| RAG観察 | {'有効' if self.rag_enabled else '無効'} |",
                f"| RAG注入 | {'有効' if self.inject_enabled else '無効'} |",
            ])

        lines.extend([
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
        ])

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

        # Dynamic condition comparison table based on mode
        by_cond = result.summary.get("by_condition", {})

        if self.ab_mode:
            # AB mode: observe vs inject
            observe = by_cond.get("observe", {})
            inject = by_cond.get("inject", {})
            retry_delta = observe.get("total_retries", 0) - inject.get("total_retries", 0)

            lines.extend([
                "| メトリクス | Observe (A) | Inject (B) | Delta |",
                "|------------|:-----------:|:----------:|:-----:|",
                f"| 成功数 | {observe.get('successful', 0)} | {inject.get('successful', 0)} | - |",
                f"| 総リトライ数 | {observe.get('total_retries', 0)} | {inject.get('total_retries', 0)} | {retry_delta:+d} |",
                f"| 平均リトライ数 | {observe.get('avg_retries', 0):.2f} | {inject.get('avg_retries', 0):.2f} | - |",
                f"| Facts注入数 | - | {inject.get('total_facts_injected', 0)} | - |",
            ])

            # Injection triggers breakdown
            inj_triggers = inject.get("injection_triggers", {})
            if any(inj_triggers.values()):
                lines.extend([
                    "",
                    "### RAGトリガー内訳 (Inject条件)",
                    "",
                    "| トリガー | 発火数 |",
                    "|----------|:------:|",
                ])
                for trigger, count in inj_triggers.items():
                    lines.append(f"| {trigger} | {count} |")

        elif len(result.conditions) == 1:
            # Single condition mode
            cond_name = result.conditions[0]
            cond = by_cond.get(cond_name, {})

            lines.extend([
                f"### {cond_name} 結果",
                "",
                "| メトリクス | 値 |",
                "|------------|:---:|",
                f"| 成功数 | {cond.get('successful', 0)} |",
                f"| 総リトライ数 | {cond.get('total_retries', 0)} |",
                f"| 平均リトライ数 | {cond.get('avg_retries', 0):.2f} |",
                f"| 総不採用数 | {cond.get('total_rejections', 0)} |",
            ])
            if cond.get("total_facts_injected"):
                lines.append(f"| Facts注入数 | {cond.get('total_facts_injected', 0)} |")

        else:
            # Default mode: without_director vs with_director
            without = by_cond.get("without_director", {})
            with_dir = by_cond.get("with_director", {})

            lines.extend([
                "| メトリクス | Director無し | Director有り | 差分 |",
                "|------------|:-----------:|:-----------:|:----:|",
                f"| 成功数 | {without.get('successful', 0)} | {with_dir.get('successful', 0)} | - |",
                f"| 平均リトライ数 | {without.get('avg_retries', 0):.2f} | {with_dir.get('avg_retries', 0):.2f} | +{with_dir.get('avg_retries', 0) - without.get('avg_retries', 0):.2f} |",
                f"| 総不採用数 | {without.get('total_rejections', 0)} | {with_dir.get('total_rejections', 0)} | +{with_dir.get('total_rejections', 0)} |",
            ])

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
            "| `-` | Director無し条件 |",
            "| `PASS` | 採用 |",
            "| `WARN` | 警告付き採用 |",
            "| **`RETRY`** | 不採用（取り消し線で表示） |",
            "",
            "### 4.2 会話サンプル",
            "",
        ])

        # Group results by scenario
        scenarios_runs: dict[str, dict[str, list]] = {}
        for r in result.results:
            if not r.success:
                continue
            if r.scenario not in scenarios_runs:
                scenarios_runs[r.scenario] = {}
            if r.condition not in scenarios_runs[r.scenario]:
                scenarios_runs[r.scenario][r.condition] = []
            scenarios_runs[r.scenario][r.condition].append(r)

        # Show conversations for each scenario and run
        for scenario_name, cond_results in scenarios_runs.items():
            # Determine number of runs (use first condition's count)
            first_cond = result.conditions[0] if result.conditions else None
            if not first_cond or first_cond not in cond_results:
                continue
            num_runs = len(cond_results[first_cond])

            for run_idx in range(num_runs):
                lines.append(f"#### {scenario_name} - Run {run_idx + 1}")
                lines.append("")

                # Show each condition
                for cond_idx, condition in enumerate(result.conditions):
                    if condition not in cond_results or run_idx >= len(cond_results[condition]):
                        continue

                    r = cond_results[condition][run_idx]
                    label = chr(ord('A') + cond_idx)

                    # Determine header based on condition
                    if condition == "without_director":
                        header = "**Director無し**"
                    elif condition == "observe":
                        header = f"**Observe (inject_enabled=False)** (リトライ: {r.total_retries}回)"
                    elif condition == "inject":
                        header = f"**Inject (inject_enabled=True)** (リトライ: {r.total_retries}回)"
                    else:
                        header = f"**{condition}** (リトライ: {r.total_retries}回)"

                    lines.append(header)
                    lines.append("")

                    # Build table header
                    if self.ab_mode and condition == "inject":
                        lines.append("| Turn | Speaker | Thought | Output | Director | Injection |")
                        lines.append("|:----:|:-------:|---------|--------|:--------:|-----------|")
                    else:
                        lines.append("| Turn | Speaker | Thought | Output | Director |")
                        lines.append("|:----:|:-------:|---------|--------|:--------:|")

                    for td in r.turn_details:
                        # Show rejected responses first
                        for rej in td.rejected_responses:
                            thought_rej = self._truncate(rej.thought or "-", 40)
                            output_rej = self._truncate(rej.output, 50)
                            if self.ab_mode and condition == "inject":
                                lines.append(f"| {td.turn_number + 1} | {td.speaker} | ~~{thought_rej}~~ | ~~{output_rej}~~ | **`RETRY`** | - |")
                            else:
                                lines.append(f"| {td.turn_number + 1} | {td.speaker} | ~~{thought_rej}~~ | ~~{output_rej}~~ | **`RETRY`** |")

                        # Final accepted response
                        thought_short = self._truncate(td.thought or "-", 40)
                        output_short = self._truncate(td.output, 50)
                        director_status = "`PASS`" if condition != "without_director" else "`-`"

                        # Injection info for AB mode inject condition
                        if self.ab_mode and condition == "inject":
                            inj_info = "-"
                            if td.injection_decision and td.injection_decision.get("reasons"):
                                inj_info = ", ".join(td.injection_decision["reasons"])
                            lines.append(f"| {td.turn_number + 1} | {td.speaker} | {thought_short} | {output_short} | {director_status} | {inj_info} |")
                        else:
                            lines.append(f"| {td.turn_number + 1} | {td.speaker} | {thought_short} | {output_short} | {director_status} |")

                    lines.append("")

                lines.append("---")
                lines.append("")

        # Summary and conclusion
        lines.extend([
            "## 5. 結論",
            "",
        ])

        by_cond = result.summary.get("by_condition", {})

        if self.ab_mode:
            # AB mode conclusion
            observe = by_cond.get("observe", {})
            inject = by_cond.get("inject", {})
            retry_delta = observe.get("total_retries", 0) - inject.get("total_retries", 0)

            if retry_delta > 0:
                lines.append(f"**✅ Injection有効**: リトライ数が **{retry_delta}回** 削減された。")
            elif retry_delta < 0:
                lines.append(f"**⚠️ Injection効果なし**: リトライ数が **{abs(retry_delta)}回** 増加した。")
            else:
                lines.append("**➖ 差なし**: リトライ数に変化なし。")
        elif result.summary.get("comparison", {}).get("score_improvement_percent"):
            comparison = result.summary.get("comparison", {})
            pct = comparison["score_improvement_percent"]
            if pct > 5:
                lines.append(f"Director有効化により、全体スコアが **{pct:+.1f}%** 改善しました。")
            elif pct < -5:
                lines.append(f"Director有効化により、全体スコアが **{pct:+.1f}%** 低下しました。")
            else:
                lines.append(f"Director有効化による影響は軽微でした（{pct:+.1f}%）。")
        else:
            # Fallback for default mode
            with_dir = by_cond.get("with_director", by_cond.get(result.conditions[-1] if result.conditions else "", {}))
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

    parser = argparse.ArgumentParser(
        description="Director A/B Test (Phase 3.2 対応)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: Compare without vs with Director
  python director_ab_test.py --runs 2

  # RAG observation only (Phase 3.1)
  python director_ab_test.py --rag --runs 2

  # RAG injection enabled (Phase 3.2)
  python director_ab_test.py --inject --runs 2

  # A/B comparison: observe vs inject
  python director_ab_test.py --ab --runs 2

  # Phase 3.2 preset scenarios with A/B mode
  python director_ab_test.py --preset phase32 --ab --runs 2
""",
    )
    parser.add_argument("--backend", default="ollama", help="LLM backend (ollama or koboldcpp)")
    parser.add_argument("--model", default="gemma3:12b", help="Model name")
    parser.add_argument("--runs", type=int, default=2, help="Runs per scenario")
    parser.add_argument("--output", default="results", help="Output directory")

    # Phase 3.2 options
    parser.add_argument("--rag", action="store_true", help="Enable RAG observation (Phase 3.1)")
    parser.add_argument("--inject", action="store_true", help="Enable RAG injection (Phase 3.2, implies --rag)")
    parser.add_argument("--ab", action="store_true", help="A/B mode: compare observe vs inject")
    parser.add_argument(
        "--preset",
        choices=["standard", "phase32"],
        default="standard",
        help="Scenario preset: standard (default) or phase32 (violation scenarios)",
    )

    args = parser.parse_args()

    # inject implies rag
    rag_enabled = args.rag or args.inject or args.ab
    inject_enabled = args.inject

    runner = DirectorABTest(
        backend=args.backend,
        model=args.model,
        runs_per_scenario=args.runs,
        output_dir=Path(args.output),
        rag_enabled=rag_enabled,
        inject_enabled=inject_enabled,
        ab_mode=args.ab,
        preset=args.preset,
    )

    if not runner.setup():
        print("\n✗ Setup failed, exiting")
        sys.exit(1)

    result = runner.run()

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for condition in result.conditions:
        cond_data = result.summary.get("by_condition", {}).get(condition, {})
        print(f"\n{condition}:")
        print(f"  Avg retries: {cond_data.get('avg_retries', 0):.2f}")
        print(f"  Total rejections: {cond_data.get('total_rejections', 0)}")
        if cond_data.get("total_facts_injected"):
            print(f"  Facts injected: {cond_data.get('total_facts_injected', 0)}")


if __name__ == "__main__":
    main()
