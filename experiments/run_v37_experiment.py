#!/usr/bin/env python
"""v3.7 Direct Dialogue Enforcement 実験ランナー

v3.7の核心: 「名前を出力させない（発言内容のみ出力）」
- Output強制時のPrefillを `\nOutput: 「` に変更
- Stop sequenceを "」" または "\n" に変更

使用方法:
    python experiments/run_v37_experiment.py configs/prompt_v37_gemma3.yaml
    python experiments/run_v37_experiment.py configs/prompt_v37_gemma2.yaml
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
from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """シナリオ結果"""
    scenario_name: str
    variation_name: str
    success: bool
    conversation: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    execution_time_seconds: float = 0.0
    error: str = None


@dataclass
class ExperimentResult:
    """実験結果"""
    experiment_id: str
    experiment_name: str
    timestamp: str
    variations: list[dict]
    scenarios: list[dict]
    results: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def calculate_v37_metrics(conversation: list[dict]) -> dict:
    """v3.7専用メトリクスを計算

    Args:
        conversation: 会話リスト

    Returns:
        メトリクス辞書
    """
    if not conversation:
        return {
            "thought_rate": 0.0,
            "output_rate": 0.0,
            "bracket_rate": 0.0,
            "dialogue_content_rate": 0.0,
            "surname_stop_rate": 0.0,
        }

    thought_count = 0
    output_count = 0
    bracket_count = 0
    dialogue_content_count = 0
    surname_stop_count = 0

    for turn in conversation:
        content = turn.get("content", "")

        # Thoughtが含まれているか
        if "Thought:" in content:
            thought_count += 1

        # Outputが含まれているか
        if "Output:" in content:
            output_count += 1

            # Output:の後に「」があるか
            output_part = content.split("Output:")[1] if "Output:" in content else ""
            if "「" in output_part:
                bracket_count += 1

                # 「」の中に実際の対話内容があるか
                import re
                bracket_match = re.search(r"「(.+?)」", output_part)
                if bracket_match:
                    dialogue = bracket_match.group(1)
                    # 「澄ヶ瀬」のみで止まっていないか
                    if dialogue.strip() and dialogue.strip() != "澄ヶ瀬":
                        dialogue_content_count += 1
                    else:
                        surname_stop_count += 1
                else:
                    # 閉じカッコがなくても内容があるか確認
                    dialogue = output_part.split("「")[1] if "「" in output_part else ""
                    if dialogue.strip() and not dialogue.strip().startswith("澄ヶ瀬"):
                        dialogue_content_count += 1

            # Output:の直後が「澄ヶ瀬」で始まっているか（v3.6の問題）
            output_stripped = output_part.strip()
            if output_stripped.startswith("澄ヶ瀬"):
                surname_stop_count += 1

    total = len(conversation)
    return {
        "thought_rate": thought_count / total,
        "output_rate": output_count / total,
        "bracket_rate": bracket_count / total,
        "dialogue_content_rate": dialogue_content_count / total,
        "surname_stop_rate": surname_stop_count / total,
    }


def run_v37_experiment(config_path: Path, output_dir: Path) -> ExperimentResult:
    """v3.7実験を実行

    Args:
        config_path: 設定ファイルパス
        output_dir: 出力ディレクトリ

    Returns:
        実験結果
    """
    # 設定読み込み
    config = ExperimentConfig.from_yaml(config_path)
    logger.info(f"Loaded experiment config: {config.name}")

    # 結果オブジェクト初期化
    timestamp = datetime.now().isoformat()
    result = ExperimentResult(
        experiment_id=config.experiment_id,
        experiment_name=config.name,
        timestamp=timestamp,
        variations=[
            {
                "name": v.name,
                "llm_backend": v.llm_backend.value,
                "llm_model": v.ollama_model,
                "prompt_structure": v.prompt_structure.value,
                "rag_enabled": v.rag_enabled,
                "director_enabled": v.director_enabled,
                "few_shot_count": v.few_shot_count,
                "use_v37_flow": v.use_v37_flow,
            }
            for v in config.variations
        ],
        scenarios=[
            {
                "name": s.name,
                "initial_prompt": s.initial_prompt,
                "turns": s.turns,
                "evaluation_focus": s.evaluation_focus,
            }
            for s in config.scenarios
        ],
    )

    # 各バリエーション×シナリオで実行
    for variation in config.variations:
        logger.info(f"Running variation: {variation.name}")

        # v3.7アダプタを作成
        adapter = V37ConfigurableAdapter(variation)

        if not adapter.is_available():
            logger.error(f"Backend not available: {variation.llm_backend.value}")
            continue

        for scenario in config.scenarios:
            logger.info(f"  Scenario: {scenario.name}")

            try:
                # 対話生成
                dialogue_result = adapter.generate_dialogue(
                    initial_prompt=scenario.initial_prompt,
                    turns=scenario.turns,
                )

                # v3.7メトリクス計算
                metrics = calculate_v37_metrics(dialogue_result.get("conversation", []))

                scenario_result = ScenarioResult(
                    scenario_name=scenario.name,
                    variation_name=variation.name,
                    success=dialogue_result.get("success", False),
                    conversation=dialogue_result.get("conversation", []),
                    metrics=metrics,
                    execution_time_seconds=dialogue_result.get("execution_time_seconds", 0),
                    error=dialogue_result.get("error"),
                )

                result.results.append(asdict(scenario_result))
                logger.info(f"    Dialogue content rate: {metrics['dialogue_content_rate']:.1%}")
                logger.info(f"    Surname stop rate: {metrics['surname_stop_rate']:.1%}")

            except Exception as e:
                logger.exception(f"Error in scenario {scenario.name}")
                result.results.append(asdict(ScenarioResult(
                    scenario_name=scenario.name,
                    variation_name=variation.name,
                    success=False,
                    error=str(e),
                )))

    # サマリー計算
    result.summary = _calculate_summary(result.results)

    # 結果保存
    output_path = _save_results(result, output_dir)
    logger.info(f"Results saved to: {output_path}")

    return result


def _calculate_summary(results: list[dict]) -> dict:
    """サマリーを計算"""
    summary = {
        "total_runs": len(results),
        "successful_runs": sum(1 for r in results if r.get("success")),
        "by_variation": {},
        "by_scenario": {},
    }

    # バリエーション別
    for r in results:
        var_name = r.get("variation_name", "unknown")
        if var_name not in summary["by_variation"]:
            summary["by_variation"][var_name] = {
                "total": 0,
                "successful": 0,
                "avg_dialogue_content_rate": 0.0,
                "avg_surname_stop_rate": 0.0,
                "metrics_list": [],
            }
        summary["by_variation"][var_name]["total"] += 1
        if r.get("success"):
            summary["by_variation"][var_name]["successful"] += 1
        if r.get("metrics"):
            summary["by_variation"][var_name]["metrics_list"].append(r["metrics"])

    # 平均計算
    for var_name, var_data in summary["by_variation"].items():
        if var_data["metrics_list"]:
            var_data["avg_dialogue_content_rate"] = sum(
                m.get("dialogue_content_rate", 0) for m in var_data["metrics_list"]
            ) / len(var_data["metrics_list"])
            var_data["avg_surname_stop_rate"] = sum(
                m.get("surname_stop_rate", 0) for m in var_data["metrics_list"]
            ) / len(var_data["metrics_list"])
        del var_data["metrics_list"]

    # シナリオ別
    for r in results:
        scenario_name = r.get("scenario_name", "unknown")
        if scenario_name not in summary["by_scenario"]:
            summary["by_scenario"][scenario_name] = {
                "total": 0,
                "successful": 0,
                "by_variation": {},
            }
        summary["by_scenario"][scenario_name]["total"] += 1
        if r.get("success"):
            summary["by_scenario"][scenario_name]["successful"] += 1

        var_name = r.get("variation_name", "unknown")
        summary["by_scenario"][scenario_name]["by_variation"][var_name] = {
            "metrics": r.get("metrics"),
        }

    return summary


def _save_results(result: ExperimentResult, output_dir: Path) -> Path:
    """結果を保存"""
    # 出力ディレクトリ作成
    exp_dir = output_dir / result.experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    # JSON保存
    output_path = exp_dir / "result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, ensure_ascii=False, indent=2)

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="v3.7 Direct Dialogue Enforcement Experiment Runner")
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

    result = run_v37_experiment(config_path, args.output_dir)

    # サマリーを表示
    print("\n" + "=" * 60)
    print("v3.7 Experiment Summary")
    print("=" * 60)
    print(f"Experiment: {result.experiment_name}")
    print(f"Total runs: {result.summary['total_runs']}")
    print(f"Successful: {result.summary['successful_runs']}")
    print()

    for var_name, var_data in result.summary.get("by_variation", {}).items():
        print(f"\n[{var_name}]")
        print(f"  Success rate: {var_data['successful']}/{var_data['total']}")
        print(f"  Avg dialogue content rate: {var_data['avg_dialogue_content_rate']:.1%}")
        print(f"  Avg surname stop rate: {var_data['avg_surname_stop_rate']:.1%}")

    print("\n" + "=" * 60)
