"""A/Bテスト実行エンジン"""

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from .adapters import ConfigurableAdapter
from .config import ExperimentConfig, ScenarioConfig, VariationConfig

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """シナリオ実行結果"""
    scenario_name: str
    variation_name: str
    success: bool
    conversation: list[dict] = field(default_factory=list)
    metrics: Optional[dict] = None
    execution_time_seconds: float = 0.0
    error: Optional[str] = None


@dataclass
class ExperimentResult:
    """実験全体の結果"""
    experiment_id: str
    experiment_name: str
    timestamp: str
    variations: list[dict] = field(default_factory=list)
    scenarios: list[dict] = field(default_factory=list)
    results: list[ScenarioResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "timestamp": self.timestamp,
            "variations": self.variations,
            "scenarios": self.scenarios,
            "results": [asdict(r) for r in self.results],
            "summary": self.summary,
        }


class ABTestRunner:
    """A/Bテスト実行エンジン"""

    def __init__(
        self,
        config: ExperimentConfig,
        evaluator=None,
        output_dir: Path = Path("results"),
    ):
        """
        Args:
            config: 実験設定
            evaluator: 評価器（Noneの場合は評価をスキップ）
            output_dir: 結果出力ディレクトリ
        """
        self.config = config
        self.evaluator = evaluator
        self.output_dir = output_dir

    def run(self) -> ExperimentResult:
        """実験を実行"""
        logger.info(f"Starting experiment: {self.config.name}")
        logger.info(f"Variations: {len(self.config.variations)}")
        logger.info(f"Scenarios: {len(self.config.scenarios)}")

        result = ExperimentResult(
            experiment_id=self.config.experiment_id,
            experiment_name=self.config.name,
            timestamp=datetime.now().isoformat(),
            variations=[self._variation_to_dict(v) for v in self.config.variations],
            scenarios=[self._scenario_to_dict(s) for s in self.config.scenarios],
        )

        # 各バリエーションで各シナリオを実行
        for variation in self.config.variations:
            logger.info(f"\n{'='*60}")
            logger.info(f"Variation: {variation.name}")
            logger.info(f"  LLM: {variation.llm_backend.value} / {variation.llm_model}")
            logger.info(f"  Prompt: {variation.prompt_structure.value}")
            logger.info(f"{'='*60}")

            adapter = ConfigurableAdapter(variation)

            if not adapter.is_available():
                logger.error(f"Backend not available: {variation.llm_backend.value}")
                continue

            for scenario in self.config.scenarios:
                logger.info(f"\n--- Scenario: {scenario.name} ---")
                logger.info(f"Prompt: {scenario.initial_prompt}")

                scenario_result = self._run_scenario(adapter, variation, scenario)
                result.results.append(scenario_result)

                if scenario_result.success:
                    logger.info(f"Success: {len(scenario_result.conversation)} turns")
                    if scenario_result.metrics:
                        logger.info(f"Overall: {scenario_result.metrics.get('overall_score', 'N/A'):.3f}")
                else:
                    logger.error(f"Failed: {scenario_result.error}")

        # サマリー計算
        result.summary = self._compute_summary(result)

        # 結果保存
        self._save_result(result)

        return result

    def _run_scenario(
        self,
        adapter: ConfigurableAdapter,
        variation: VariationConfig,
        scenario: ScenarioConfig,
    ) -> ScenarioResult:
        """シナリオを実行"""
        try:
            # 対話生成
            dialogue_result = adapter.generate_dialogue(
                initial_prompt=scenario.initial_prompt,
                turns=scenario.turns,
            )

            if not dialogue_result["success"]:
                return ScenarioResult(
                    scenario_name=scenario.name,
                    variation_name=variation.name,
                    success=False,
                    error=dialogue_result.get("error", "Unknown error"),
                    execution_time_seconds=dialogue_result.get("execution_time_seconds", 0),
                )

            # 評価（評価器がある場合）
            metrics = None
            if self.evaluator:
                try:
                    conversation = adapter.to_standard_format(dialogue_result)
                    metrics_obj = self.evaluator.evaluate_conversation(conversation)
                    metrics = metrics_obj.to_dict() if hasattr(metrics_obj, "to_dict") else metrics_obj
                except Exception as e:
                    logger.warning(f"Evaluation failed: {e}")

            return ScenarioResult(
                scenario_name=scenario.name,
                variation_name=variation.name,
                success=True,
                conversation=dialogue_result["conversation"],
                metrics=metrics,
                execution_time_seconds=dialogue_result.get("execution_time_seconds", 0),
            )

        except Exception as e:
            logger.exception(f"Scenario execution failed: {scenario.name}")
            return ScenarioResult(
                scenario_name=scenario.name,
                variation_name=variation.name,
                success=False,
                error=str(e),
            )

    def _compute_summary(self, result: ExperimentResult) -> dict:
        """実験結果のサマリーを計算"""
        summary = {
            "total_runs": len(result.results),
            "successful_runs": sum(1 for r in result.results if r.success),
            "by_variation": {},
            "by_scenario": {},
        }

        # バリエーション別集計
        for variation in self.config.variations:
            var_results = [r for r in result.results if r.variation_name == variation.name]
            var_scores = [
                r.metrics.get("overall_score", 0)
                for r in var_results
                if r.success and r.metrics
            ]
            summary["by_variation"][variation.name] = {
                "total": len(var_results),
                "successful": sum(1 for r in var_results if r.success),
                "avg_score": sum(var_scores) / len(var_scores) if var_scores else None,
                "scores": var_scores,
            }

        # シナリオ別集計
        for scenario in self.config.scenarios:
            scn_results = [r for r in result.results if r.scenario_name == scenario.name]
            summary["by_scenario"][scenario.name] = {
                "total": len(scn_results),
                "successful": sum(1 for r in scn_results if r.success),
                "by_variation": {
                    r.variation_name: {
                        "score": r.metrics.get("overall_score") if r.metrics else None,
                        "metrics": r.metrics,
                    }
                    for r in scn_results if r.success
                },
            }

        return summary

    def _save_result(self, result: ExperimentResult):
        """結果を保存"""
        # 実験IDディレクトリを作成
        exp_dir = self.output_dir / result.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)

        # メイン結果ファイル
        result_path = exp_dir / "result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Results saved to {result_path}")

    def _variation_to_dict(self, v: VariationConfig) -> dict:
        """バリエーション設定を辞書に変換"""
        return {
            "name": v.name,
            "llm_backend": v.llm_backend.value,
            "llm_model": v.llm_model,
            "prompt_structure": v.prompt_structure.value,
            "rag_enabled": v.rag_enabled,
            "director_enabled": v.director_enabled,
            "few_shot_count": v.few_shot_count,
        }

    def _scenario_to_dict(self, s: ScenarioConfig) -> dict:
        """シナリオ設定を辞書に変換"""
        return {
            "name": s.name,
            "initial_prompt": s.initial_prompt,
            "turns": s.turns,
            "evaluation_focus": s.evaluation_focus,
        }
