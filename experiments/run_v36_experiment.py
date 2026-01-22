#!/usr/bin/env python
"""v3.6 System-Assisted Output Enforcement 実験ランナー

v3.6の核心:
- Prefill Pattern: "Thought:" をassistantメッセージに事前入力
- Stop Sequence: "Output:" で一旦停止
- Continue Generation: Output:がなければ追記して継続生成

使用方法:
    python experiments/run_v36_experiment.py configs/prompt_v36_gemma3.yaml
    python experiments/run_v36_experiment.py configs/prompt_v36_gemma2.yaml
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "experiments"))

from experiments.ab_test.config import ExperimentConfig, LLMBackend
from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """シナリオ実行結果"""
    scenario_name: str
    variation_name: str
    success: bool
    conversation: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    execution_time_seconds: float = 0.0
    error: str = ""


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


def run_v36_experiment(config_path: Path, output_dir: Path):
    """v3.6実験を実行"""
    logger.info(f"Loading config from: {config_path}")
    config = ExperimentConfig.from_yaml(config_path)

    logger.info(f"Starting experiment: {config.name}")
    logger.info(f"Variations: {len(config.variations)}")
    logger.info(f"Scenarios: {len(config.scenarios)}")

    result = ExperimentResult(
        experiment_id=config.experiment_id,
        experiment_name=config.name,
        timestamp=datetime.now().isoformat(),
        variations=[_variation_to_dict(v) for v in config.variations],
        scenarios=[_scenario_to_dict(s) for s in config.scenarios],
    )

    # 各バリエーションで各シナリオを実行
    for variation in config.variations:
        logger.info(f"\n{'='*60}")
        logger.info(f"Variation: {variation.name}")
        model_name = variation.ollama_model if variation.llm_backend == LLMBackend.OLLAMA else variation.llm_model
        logger.info(f"  LLM: {variation.llm_backend.value} / {model_name}")
        logger.info(f"  Prompt: {variation.prompt_structure.value}")
        logger.info(f"  v3.6 Flow: {variation.use_v36_flow}")
        logger.info(f"{'='*60}")

        # v3.6アダプタを使用
        adapter = V36ConfigurableAdapter(variation)

        if not adapter.is_available():
            logger.error(f"Backend not available: {variation.llm_backend.value}")
            continue

        for scenario in config.scenarios:
            logger.info(f"\n--- Scenario: {scenario.name} ---")
            logger.info(f"Prompt: {scenario.initial_prompt}")

            try:
                # 対話生成
                dialogue_result = adapter.generate_dialogue(
                    initial_prompt=scenario.initial_prompt,
                    turns=scenario.turns,
                )

                if not dialogue_result["success"]:
                    scenario_result = ScenarioResult(
                        scenario_name=scenario.name,
                        variation_name=variation.name,
                        success=False,
                        error=dialogue_result.get("error", "Unknown error"),
                        execution_time_seconds=dialogue_result.get("execution_time_seconds", 0),
                    )
                else:
                    # Output完了率を計算
                    output_metrics = _calculate_output_metrics(dialogue_result["conversation"])

                    scenario_result = ScenarioResult(
                        scenario_name=scenario.name,
                        variation_name=variation.name,
                        success=True,
                        conversation=dialogue_result["conversation"],
                        metrics=output_metrics,
                        execution_time_seconds=dialogue_result.get("execution_time_seconds", 0),
                    )
                    logger.info(f"Success: {len(scenario_result.conversation)} turns")
                    logger.info(f"Output completion rate: {output_metrics.get('output_completion_rate', 0):.1%}")

                result.results.append(scenario_result)

            except Exception as e:
                logger.exception(f"Scenario execution failed: {scenario.name}")
                result.results.append(ScenarioResult(
                    scenario_name=scenario.name,
                    variation_name=variation.name,
                    success=False,
                    error=str(e),
                ))

    # サマリー計算
    result.summary = _compute_summary(result, config)

    # 結果保存
    _save_result(result, output_dir)

    return result


def _calculate_output_metrics(conversation: list[dict]) -> dict:
    """Output完了率などのメトリクスを計算"""
    total_turns = len(conversation)
    turns_with_output = 0
    turns_with_thought = 0

    for turn in conversation:
        content = turn.get("content", "")
        if "Output:" in content:
            turns_with_output += 1
        if "Thought:" in content:
            turns_with_thought += 1

    return {
        "total_turns": total_turns,
        "turns_with_output": turns_with_output,
        "turns_with_thought": turns_with_thought,
        "output_completion_rate": turns_with_output / total_turns if total_turns > 0 else 0,
        "thought_presence_rate": turns_with_thought / total_turns if total_turns > 0 else 0,
    }


def _compute_summary(result: ExperimentResult, config: ExperimentConfig) -> dict:
    """実験結果のサマリーを計算"""
    summary = {
        "total_runs": len(result.results),
        "successful_runs": sum(1 for r in result.results if r.success),
        "by_variation": {},
        "by_scenario": {},
        "overall_output_completion_rate": 0.0,
    }

    # 全体のOutput完了率
    all_output_rates = [
        r.metrics.get("output_completion_rate", 0)
        for r in result.results
        if r.success and r.metrics
    ]
    if all_output_rates:
        summary["overall_output_completion_rate"] = sum(all_output_rates) / len(all_output_rates)

    # バリエーション別集計
    for variation in config.variations:
        var_results = [r for r in result.results if r.variation_name == variation.name]
        var_output_rates = [
            r.metrics.get("output_completion_rate", 0)
            for r in var_results
            if r.success and r.metrics
        ]
        summary["by_variation"][variation.name] = {
            "total": len(var_results),
            "successful": sum(1 for r in var_results if r.success),
            "avg_output_completion_rate": sum(var_output_rates) / len(var_output_rates) if var_output_rates else 0,
        }

    # シナリオ別集計
    for scenario in config.scenarios:
        scn_results = [r for r in result.results if r.scenario_name == scenario.name]
        summary["by_scenario"][scenario.name] = {
            "total": len(scn_results),
            "successful": sum(1 for r in scn_results if r.success),
            "by_variation": {
                r.variation_name: {
                    "metrics": r.metrics,
                }
                for r in scn_results if r.success
            },
        }

    return summary


def _save_result(result: ExperimentResult, output_dir: Path):
    """結果を保存"""
    exp_dir = output_dir / result.experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    result_path = exp_dir / "result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    logger.info(f"Results saved to {result_path}")


def _variation_to_dict(v) -> dict:
    """バリエーション設定を辞書に変換"""
    model_name = v.ollama_model if v.llm_backend == LLMBackend.OLLAMA else v.llm_model
    return {
        "name": v.name,
        "llm_backend": v.llm_backend.value,
        "llm_model": model_name,
        "prompt_structure": v.prompt_structure.value,
        "rag_enabled": v.rag_enabled,
        "director_enabled": v.director_enabled,
        "few_shot_count": v.few_shot_count,
        "use_v36_flow": v.use_v36_flow,
    }


def _scenario_to_dict(s) -> dict:
    """シナリオ設定を辞書に変換"""
    return {
        "name": s.name,
        "initial_prompt": s.initial_prompt,
        "turns": s.turns,
        "evaluation_focus": s.evaluation_focus,
    }


def main():
    parser = argparse.ArgumentParser(description="v3.6 System-Assisted Output Enforcement Experiment Runner")
    parser.add_argument("config", type=Path, help="Experiment config YAML file")
    parser.add_argument("--output-dir", type=Path, default=Path("results"), help="Output directory")
    args = parser.parse_args()

    # 設定ファイルのパスを解決
    config_path = args.config
    if not config_path.is_absolute():
        # まずカレントディレクトリからの相対パスを試す
        if not config_path.exists():
            # プロジェクトルートからの相対パスを試す
            config_path = project_root / config_path

    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    result = run_v36_experiment(config_path, args.output_dir)

    # サマリーを表示
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Total runs: {result.summary['total_runs']}")
    print(f"Successful: {result.summary['successful_runs']}")
    print(f"Overall Output Completion Rate: {result.summary['overall_output_completion_rate']:.1%}")
    print("\nBy Variation:")
    for var_name, var_data in result.summary.get("by_variation", {}).items():
        print(f"  {var_name}: {var_data['avg_output_completion_rate']:.1%}")


if __name__ == "__main__":
    main()
