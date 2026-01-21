"""3システム比較実験

duo-talk, duo-talk-simple, duo-talk-silly の対話品質を比較評価するスクリプト。
4つの評価シナリオで各システムを評価し、結果をJSON/Markdownで出力。

使用方法:
    python experiments/compare_systems.py

出力先:
    results/YYYYMMDD_HHMMSS_comparison.json
    results/YYYYMMDD_HHMMSS_comparison.md
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.adapters import (
    DuoTalkAdapter,
    DuoTalkSimpleAdapter,
    DuoTalkSillyAdapter,
    EvaluationScenario,
    DialogueResult,
)
from evaluation.local_evaluator import LocalLLMEvaluator
from evaluation.evaluator import DialogueEvaluator
from evaluation.metrics import DialogueQualityMetrics

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 評価シナリオ定義
SCENARIOS = [
    EvaluationScenario(
        name="casual_greeting",
        initial_prompt="おはよう、二人とも",
        turns=5,
        evaluation_focus=["character_consistency", "naturalness"]
    ),
    EvaluationScenario(
        name="topic_exploration",
        initial_prompt="最近のAI技術について話して",
        turns=8,
        evaluation_focus=["topic_novelty", "concreteness"]
    ),
    EvaluationScenario(
        name="disagreement_resolution",
        initial_prompt="直感とデータ、どっちが大事？",
        turns=10,
        evaluation_focus=["relationship_quality", "naturalness"]
    ),
    EvaluationScenario(
        name="emotional_support",
        initial_prompt="最近疲れてるんだ...",
        turns=6,
        evaluation_focus=["relationship_quality", "naturalness"]
    ),
]


def create_evaluator() -> Optional[object]:
    """評価器を作成（Gemini優先、なければKoboldCPP）"""
    # Gemini APIが利用可能か確認
    if os.environ.get("GEMINI_API_KEY"):
        try:
            evaluator = DialogueEvaluator()
            logger.info("Using Gemini API evaluator")
            return evaluator
        except Exception as e:
            logger.warning(f"Gemini evaluator failed: {e}")

    # KoboldCPPを試す
    local_eval = LocalLLMEvaluator()
    if local_eval.is_available():
        logger.info("Using LocalLLM (KoboldCPP) evaluator")
        return local_eval

    logger.error("No evaluator available (neither Gemini nor KoboldCPP)")
    return None


def run_comparison_experiment(
    output_dir: Path = Path("results"),
    scenarios: Optional[List[EvaluationScenario]] = None
) -> Dict:
    """
    3システム比較実験を実行

    Args:
        output_dir: 結果出力ディレクトリ
        scenarios: 評価シナリオリスト（Noneの場合はデフォルト）

    Returns:
        Dict: 実験結果
    """
    scenarios = scenarios or SCENARIOS

    # アダプタ初期化
    adapters = {
        "duo-talk": DuoTalkAdapter(),
        "duo-talk-simple": DuoTalkSimpleAdapter(),
        "duo-talk-silly": DuoTalkSillyAdapter(),
    }

    # 評価器初期化
    evaluator = create_evaluator()
    if not evaluator:
        logger.error("Cannot run experiment without evaluator")
        return {"error": "No evaluator available"}

    # 結果格納
    results = {
        "timestamp": datetime.now().isoformat(),
        "evaluator": type(evaluator).__name__,
        "scenarios": {},
        "summary": {},
    }

    # 利用可能なシステムをチェック
    available_systems = []
    for name, adapter in adapters.items():
        available = adapter.is_available()
        if available:
            available_systems.append(name)
            logger.info(f"✓ {name}: Available")
        else:
            logger.warning(f"✗ {name}: NOT Available")

    if not available_systems:
        logger.error("No systems available for testing")
        results["error"] = "No systems available"
        return results

    results["available_systems"] = available_systems

    # 各シナリオを実行
    for scenario in scenarios:
        logger.info(f"\n{'='*50}")
        logger.info(f"Scenario: {scenario.name}")
        logger.info(f"Prompt: {scenario.initial_prompt}")
        logger.info(f"Turns: {scenario.turns}")
        logger.info(f"{'='*50}")

        scenario_results = {}

        for system_name in available_systems:
            adapter = adapters[system_name]
            logger.info(f"\n--- Running {system_name} ---")

            # 会話生成
            dialogue_result = adapter.run_scenario(scenario)

            if dialogue_result.success:
                logger.info(f"Generated {len(dialogue_result.conversation)} turns")

                # 会話内容を表示
                for turn in dialogue_result.conversation:
                    logger.debug(f"  {turn.speaker}: {turn.content[:50]}...")

                # 評価実行
                conversation = dialogue_result.to_standard_format()
                try:
                    metrics = evaluator.evaluate_conversation(conversation)

                    scenario_results[system_name] = {
                        "success": True,
                        "conversation": conversation,
                        "metrics": metrics.to_dict(),
                        "execution_time": dialogue_result.execution_time_seconds,
                    }

                    logger.info(f"Overall score: {metrics.overall_score:.3f}")
                    logger.info(f"  character_consistency: {metrics.character_consistency:.3f}")
                    logger.info(f"  topic_novelty: {metrics.topic_novelty:.3f}")
                    logger.info(f"  relationship_quality: {metrics.relationship_quality:.3f}")
                    logger.info(f"  naturalness: {metrics.naturalness:.3f}")
                    logger.info(f"  concreteness: {metrics.concreteness:.3f}")

                except Exception as e:
                    logger.error(f"Evaluation failed: {e}")
                    scenario_results[system_name] = {
                        "success": False,
                        "error": f"Evaluation failed: {e}",
                        "conversation": conversation,
                        "execution_time": dialogue_result.execution_time_seconds,
                    }
            else:
                scenario_results[system_name] = {
                    "success": False,
                    "error": dialogue_result.error,
                    "execution_time": dialogue_result.execution_time_seconds,
                }
                logger.error(f"Dialogue generation failed: {dialogue_result.error}")

        results["scenarios"][scenario.name] = scenario_results

    # サマリー計算
    for system_name in available_systems:
        scores = []
        for scenario_name, scenario_data in results["scenarios"].items():
            if system_name in scenario_data:
                data = scenario_data[system_name]
                if data.get("success") and "metrics" in data:
                    scores.append(data["metrics"]["overall_score"])

        if scores:
            results["summary"][system_name] = {
                "avg_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "successful_scenarios": len(scores),
                "total_scenarios": len(scenarios),
            }
        else:
            results["summary"][system_name] = {
                "avg_score": 0,
                "successful_scenarios": 0,
                "total_scenarios": len(scenarios),
            }

    # 結果保存
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON保存
    json_path = output_dir / f"{timestamp}_comparison.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"\nResults saved to {json_path}")

    # Markdownレポート生成
    md_path = output_dir / f"{timestamp}_comparison.md"
    generate_report(results, md_path)
    logger.info(f"Report saved to {md_path}")

    return results


def generate_report(results: Dict, output_path: Path):
    """Markdownレポート生成"""
    lines = [
        "# duo-talk 3システム比較レポート",
        "",
        f"**実行日時**: {results['timestamp']}",
        f"**評価器**: {results.get('evaluator', 'Unknown')}",
        f"**利用可能システム**: {', '.join(results.get('available_systems', []))}",
        "",
        "## サマリー",
        "",
        "| システム | 平均スコア | 最小 | 最大 | 成功/全体 |",
        "|----------|-----------|------|------|----------|",
    ]

    # スコアでソート（降順）
    sorted_summary = sorted(
        results.get("summary", {}).items(),
        key=lambda x: x[1].get("avg_score", 0),
        reverse=True
    )

    for system, data in sorted_summary:
        lines.append(
            f"| {system} | {data.get('avg_score', 0):.3f} | "
            f"{data.get('min_score', 0):.3f} | {data.get('max_score', 0):.3f} | "
            f"{data.get('successful_scenarios', 0)}/{data.get('total_scenarios', 0)} |"
        )

    lines.extend(["", "## シナリオ別結果", ""])

    for scenario_name, scenario_data in results.get("scenarios", {}).items():
        lines.append(f"### {scenario_name}")
        lines.append("")

        # スコアでソート
        sorted_systems = sorted(
            scenario_data.items(),
            key=lambda x: x[1].get("metrics", {}).get("overall_score", 0) if x[1].get("success") else 0,
            reverse=True
        )

        for system, data in sorted_systems:
            if data.get("success") and "metrics" in data:
                metrics = data["metrics"]
                lines.append(f"#### {system} (Score: {metrics['overall_score']:.3f})")
                lines.append("")
                lines.append("| メトリクス | スコア |")
                lines.append("|-----------|--------|")
                lines.append(f"| character_consistency | {metrics['character_consistency']:.3f} |")
                lines.append(f"| topic_novelty | {metrics['topic_novelty']:.3f} |")
                lines.append(f"| relationship_quality | {metrics['relationship_quality']:.3f} |")
                lines.append(f"| naturalness | {metrics['naturalness']:.3f} |")
                lines.append(f"| concreteness | {metrics['concreteness']:.3f} |")
                lines.append("")

                if metrics.get("issues"):
                    lines.append("**問題点:**")
                    for issue in metrics["issues"]:
                        lines.append(f"- {issue}")
                    lines.append("")

                if metrics.get("strengths"):
                    lines.append("**良い点:**")
                    for strength in metrics["strengths"]:
                        lines.append(f"- {strength}")
                    lines.append("")

            else:
                lines.append(f"#### {system}: Failed")
                lines.append(f"エラー: {data.get('error', 'Unknown error')}")
                lines.append("")

    # 会話サンプル（最初のシナリオのみ）
    lines.extend(["", "## 会話サンプル（casual_greeting）", ""])

    first_scenario = results.get("scenarios", {}).get("casual_greeting", {})
    for system, data in first_scenario.items():
        if data.get("success") and data.get("conversation"):
            lines.append(f"### {system}")
            lines.append("")
            lines.append("```")
            for turn in data["conversation"][:6]:  # 最初の6ターン
                lines.append(f"{turn['speaker']}: {turn['content']}")
            lines.append("```")
            lines.append("")

    # フッター
    lines.extend([
        "",
        "---",
        "",
        "*Generated by duo-talk-evaluation*",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    """メインエントリポイント"""
    print("=" * 60)
    print("duo-talk 3システム比較実験")
    print("=" * 60)
    print()

    # 実験実行
    results = run_comparison_experiment()

    # サマリー表示
    if "error" not in results:
        print("\n" + "=" * 60)
        print("実験完了 - サマリー")
        print("=" * 60)

        for system, data in results.get("summary", {}).items():
            print(f"\n{system}:")
            print(f"  平均スコア: {data.get('avg_score', 0):.3f}")
            print(f"  成功シナリオ: {data.get('successful_scenarios', 0)}/{data.get('total_scenarios', 0)}")
    else:
        print(f"\n実験失敗: {results.get('error')}")


if __name__ == "__main__":
    main()
