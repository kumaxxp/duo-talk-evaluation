"""単一システム評価スクリプト

メモリ制約のため、1システムずつ順番に評価を実行。
各システムの結果は個別ファイルに保存し、後でマージ可能。

使用方法:
    # KoboldCPP起動中
    python experiments/compare_single.py duo-talk-silly

    # Ollama起動中（Swallow 8B推奨）
    python experiments/compare_single.py duo-talk-simple

    # duo-talk Flask起動中（要: 軽量モデル設定）
    python experiments/compare_single.py duo-talk --port 5002

    # 結果マージ
    python experiments/compare_single.py --merge

出力:
    results/single_<system>_<timestamp>.json
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.adapters import (
    DuoTalkAdapter,
    DuoTalkSimpleAdapter,
    DuoTalkSillyAdapter,
    EvaluationScenario,
)
from evaluation.local_evaluator import LocalLLMEvaluator
from evaluation.evaluator import DialogueEvaluator
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 評価シナリオ
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


def get_adapter(system_name: str, port: int = 5000):
    """システム名からアダプタを取得

    Note: portパラメータは後方互換性のため残すが、
    duo-talkはコンソールモード（ライブラリ直接呼び出し）を使用するため不要。
    """
    adapters = {
        "duo-talk": lambda: DuoTalkAdapter(),  # コンソールモード（Flaskサーバー不要）
        "duo-talk-simple": lambda: DuoTalkSimpleAdapter(),
        "duo-talk-silly": lambda: DuoTalkSillyAdapter(),
    }

    if system_name not in adapters:
        raise ValueError(f"Unknown system: {system_name}. Available: {list(adapters.keys())}")

    return adapters[system_name]()


def get_evaluator():
    """利用可能な評価器を取得"""
    # Gemini優先
    if os.environ.get("GEMINI_API_KEY"):
        try:
            evaluator = DialogueEvaluator()
            logger.info("Using Gemini API evaluator")
            return evaluator
        except Exception as e:
            logger.warning(f"Gemini evaluator failed: {e}")

    # KoboldCPPフォールバック
    local_eval = LocalLLMEvaluator()
    if local_eval.is_available():
        logger.info("Using LocalLLM (KoboldCPP) evaluator")
        return local_eval

    logger.error("No evaluator available")
    return None


def run_single_system(system_name: str, port: int = 5000) -> dict:
    """単一システムの評価を実行"""
    logger.info(f"=" * 60)
    logger.info(f"Evaluating: {system_name}")
    logger.info(f"=" * 60)

    # アダプタ取得
    adapter = get_adapter(system_name, port)

    # 可用性チェック
    if not adapter.is_available():
        logger.error(f"{system_name} is NOT available")
        return {"error": f"{system_name} is not available", "system": system_name}

    logger.info(f"{system_name}: Available")

    # 評価器取得
    evaluator = get_evaluator()
    if not evaluator:
        return {"error": "No evaluator available", "system": system_name}

    # 結果格納
    results = {
        "system": system_name,
        "timestamp": datetime.now().isoformat(),
        "evaluator": type(evaluator).__name__,
        "scenarios": {},
        "summary": {},
    }

    # 各シナリオ実行
    scores = []
    for scenario in SCENARIOS:
        logger.info(f"\n--- Scenario: {scenario.name} ---")
        logger.info(f"Prompt: {scenario.initial_prompt}")
        logger.info(f"Turns: {scenario.turns}")

        # 会話生成
        dialogue_result = adapter.run_scenario(scenario)

        if dialogue_result.success:
            logger.info(f"Generated {len(dialogue_result.conversation)} turns")

            # 評価実行
            conversation = dialogue_result.to_standard_format()
            try:
                metrics = evaluator.evaluate_conversation(conversation)

                results["scenarios"][scenario.name] = {
                    "success": True,
                    "conversation": conversation,
                    "metrics": metrics.to_dict(),
                    "execution_time": dialogue_result.execution_time_seconds,
                }

                scores.append(metrics.overall_score)

                logger.info(f"Overall: {metrics.overall_score:.3f}")
                logger.info(f"  character_consistency: {metrics.character_consistency:.3f}")
                logger.info(f"  topic_novelty: {metrics.topic_novelty:.3f}")
                logger.info(f"  relationship_quality: {metrics.relationship_quality:.3f}")
                logger.info(f"  naturalness: {metrics.naturalness:.3f}")
                logger.info(f"  concreteness: {metrics.concreteness:.3f}")

            except Exception as e:
                logger.error(f"Evaluation failed: {e}")
                results["scenarios"][scenario.name] = {
                    "success": False,
                    "error": f"Evaluation failed: {e}",
                    "conversation": conversation,
                }
        else:
            logger.error(f"Dialogue generation failed: {dialogue_result.error}")
            results["scenarios"][scenario.name] = {
                "success": False,
                "error": dialogue_result.error,
            }

    # サマリー計算
    if scores:
        results["summary"] = {
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "successful_scenarios": len(scores),
            "total_scenarios": len(SCENARIOS),
        }

    return results


def merge_results(results_dir: Path = Path("results")) -> dict:
    """個別結果ファイルをマージ"""
    merged = {
        "timestamp": datetime.now().isoformat(),
        "systems": {},
        "comparison": {},
    }

    # single_*.json ファイルを検索
    single_files = list(results_dir.glob("single_*.json"))

    if not single_files:
        logger.warning("No single system results found")
        return merged

    logger.info(f"Found {len(single_files)} result files")

    for filepath in single_files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        system_name = data.get("system", "unknown")
        merged["systems"][system_name] = data
        logger.info(f"  Loaded: {system_name} from {filepath.name}")

    # 比較テーブル作成
    for scenario_name in [s.name for s in SCENARIOS]:
        merged["comparison"][scenario_name] = {}
        for system_name, data in merged["systems"].items():
            if scenario_name in data.get("scenarios", {}):
                scenario_data = data["scenarios"][scenario_name]
                if scenario_data.get("success"):
                    merged["comparison"][scenario_name][system_name] = {
                        "overall_score": scenario_data["metrics"]["overall_score"],
                        "metrics": scenario_data["metrics"],
                    }

    return merged


def print_comparison_table(merged: dict):
    """比較テーブルを表示"""
    print("\n" + "=" * 70)
    print("COMPARISON TABLE")
    print("=" * 70)

    systems = list(merged.get("systems", {}).keys())
    if not systems:
        print("No systems to compare")
        return

    # ヘッダー
    header = "| Scenario               |"
    for sys in systems:
        header += f" {sys:^18} |"
    print(header)
    print("|" + "-" * 24 + "|" + ("|" + "-" * 20).join([""] * len(systems)) + "|")

    # 各シナリオ
    for scenario_name in [s.name for s in SCENARIOS]:
        row = f"| {scenario_name:22} |"
        for sys in systems:
            score = merged.get("comparison", {}).get(scenario_name, {}).get(sys, {}).get("overall_score")
            if score is not None:
                row += f" {score:^18.3f} |"
            else:
                row += f" {'N/A':^18} |"
        print(row)

    # 平均
    print("|" + "-" * 24 + "|" + ("|" + "-" * 20).join([""] * len(systems)) + "|")
    avg_row = f"| {'AVERAGE':22} |"
    for sys in systems:
        summary = merged.get("systems", {}).get(sys, {}).get("summary", {})
        avg = summary.get("avg_score")
        if avg is not None:
            avg_row += f" {avg:^18.3f} |"
        else:
            avg_row += f" {'N/A':^18} |"
    print(avg_row)
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Single system evaluation")
    parser.add_argument(
        "system",
        nargs="?",
        choices=["duo-talk", "duo-talk-simple", "duo-talk-silly"],
        help="System to evaluate"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port for duo-talk Flask server (default: 5000)"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge all single results into comparison"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Output directory (default: results)"
    )

    args = parser.parse_args()

    if args.merge:
        # 結果マージモード
        merged = merge_results(args.output_dir)

        # 比較テーブル表示
        print_comparison_table(merged)

        # マージ結果保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = args.output_dir / f"{timestamp}_merged_comparison.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        logger.info(f"Merged results saved to {output_path}")

    elif args.system:
        # 単一システム評価モード
        results = run_single_system(args.system, args.port)

        # 結果保存
        args.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = args.output_dir / f"single_{args.system}_{timestamp}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"\nResults saved to {output_path}")

        # サマリー表示
        if "summary" in results and results["summary"]:
            print("\n" + "=" * 40)
            print(f"SUMMARY: {args.system}")
            print("=" * 40)
            print(f"Average Score: {results['summary']['avg_score']:.3f}")
            print(f"Min/Max: {results['summary']['min_score']:.3f} / {results['summary']['max_score']:.3f}")
            print(f"Successful: {results['summary']['successful_scenarios']}/{results['summary']['total_scenarios']}")
        elif "error" in results:
            print(f"\nERROR: {results['error']}")
    else:
        parser.print_help()
        print("\n使用例:")
        print("  # KoboldCPP起動中")
        print("  python experiments/compare_single.py duo-talk-silly")
        print("")
        print("  # Ollama起動中")
        print("  python experiments/compare_single.py duo-talk-simple")
        print("")
        print("  # duo-talk Flask起動中 (ポート5002)")
        print("  python experiments/compare_single.py duo-talk --port 5002")
        print("")
        print("  # 結果マージ")
        print("  python experiments/compare_single.py --merge")


if __name__ == "__main__":
    main()
