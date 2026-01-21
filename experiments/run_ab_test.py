#!/usr/bin/env python3
"""A/Bテスト実行スクリプト

使用方法:
    # LLM比較実験
    python experiments/run_ab_test.py configs/llm_comparison.yaml

    # プロンプト構造比較実験
    python experiments/run_ab_test.py configs/prompt_comparison.yaml

    # 評価なしで対話生成のみ
    python experiments/run_ab_test.py configs/llm_comparison.yaml --no-eval

    # 結果ディレクトリ指定
    python experiments/run_ab_test.py configs/llm_comparison.yaml --output-dir results/experiments
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.ab_test.config import ExperimentConfig
from experiments.ab_test.runner import ABTestRunner
from experiments.ab_test.report import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_evaluator(no_eval: bool = False):
    """評価器を取得"""
    if no_eval:
        logger.info("Evaluation disabled")
        return None

    # Gemini優先
    if os.environ.get("GEMINI_API_KEY"):
        try:
            from evaluation.evaluator import DialogueEvaluator
            evaluator = DialogueEvaluator()
            logger.info("Using Gemini API evaluator")
            return evaluator
        except Exception as e:
            logger.warning(f"Gemini evaluator failed: {e}")

    # KoboldCPPフォールバック
    try:
        from evaluation.local_evaluator import LocalLLMEvaluator
        local_eval = LocalLLMEvaluator()
        if local_eval.is_available():
            logger.info("Using LocalLLM (KoboldCPP) evaluator")
            return local_eval
    except ImportError:
        pass

    logger.warning("No evaluator available - running without evaluation")
    return None


def main():
    parser = argparse.ArgumentParser(description="A/Bテスト実行")
    parser.add_argument(
        "config",
        type=Path,
        help="実験設定ファイル（YAML）"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="結果出力ディレクトリ（デフォルト: results）"
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="評価をスキップ（対話生成のみ）"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Markdownレポートを生成"
    )

    args = parser.parse_args()

    # 設定ファイルのパスを解決
    config_path = args.config
    if not config_path.is_absolute():
        # experimentsディレクトリからの相対パス
        config_path = PROJECT_ROOT / "experiments" / config_path

    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    # 設定読み込み
    logger.info(f"Loading config: {config_path}")
    config = ExperimentConfig.from_yaml(config_path)
    logger.info(f"Experiment: {config.name}")
    logger.info(f"Variations: {len(config.variations)}")
    logger.info(f"Scenarios: {len(config.scenarios)}")

    # 評価器取得
    evaluator = get_evaluator(args.no_eval)

    # 実験実行
    runner = ABTestRunner(
        config=config,
        evaluator=evaluator,
        output_dir=args.output_dir,
    )

    result = runner.run()

    # レポート生成
    report_gen = ReportGenerator(result)
    report_gen.print_summary()

    if args.report:
        report_path = report_gen.save_markdown(args.output_dir)
        logger.info(f"Report saved to {report_path}")

    logger.info("Done!")


if __name__ == "__main__":
    main()
