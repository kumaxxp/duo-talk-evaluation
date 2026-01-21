"""レポート生成"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .runner import ExperimentResult


class ReportGenerator:
    """比較レポート生成"""

    def __init__(self, result: ExperimentResult):
        self.result = result

    def generate_markdown(self) -> str:
        """Markdownレポートを生成"""
        lines = [
            f"# {self.result.experiment_name}",
            "",
            f"**実験ID**: {self.result.experiment_id}",
            f"**実行日時**: {self.result.timestamp}",
            "",
            "---",
            "",
            "## 1. 実験概要",
            "",
            "### 1.1 バリエーション",
            "",
            "| バリエーション | LLM | プロンプト構造 | RAG | Director |",
            "|---------------|-----|---------------|-----|----------|",
        ]

        for var in self.result.variations:
            lines.append(
                f"| {var['name']} | {var['llm_backend']}/{var['llm_model']} | "
                f"{var['prompt_structure']} | "
                f"{'✅' if var['rag_enabled'] else '❌'} | "
                f"{'✅' if var['director_enabled'] else '❌'} |"
            )

        lines.extend([
            "",
            "### 1.2 シナリオ",
            "",
            "| シナリオ | プロンプト | ターン数 |",
            "|---------|-----------|---------|",
        ])

        for scn in self.result.scenarios:
            lines.append(
                f"| {scn['name']} | {scn['initial_prompt'][:20]}... | {scn['turns']} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 2. 結果サマリー",
            "",
            f"- 総実行数: {self.result.summary.get('total_runs', 0)}",
            f"- 成功数: {self.result.summary.get('successful_runs', 0)}",
            "",
            "### 2.1 バリエーション別スコア",
            "",
            "| バリエーション | 成功率 | 平均スコア |",
            "|---------------|--------|-----------|",
        ])

        for var_name, var_data in self.result.summary.get("by_variation", {}).items():
            success_rate = var_data.get("successful", 0) / max(var_data.get("total", 1), 1)
            avg_score = var_data.get("avg_score")
            score_str = f"{avg_score:.3f}" if avg_score else "N/A"
            lines.append(f"| {var_name} | {success_rate:.0%} | {score_str} |")

        lines.extend([
            "",
            "### 2.2 シナリオ別スコア比較",
            "",
        ])

        # シナリオ別比較テーブル
        var_names = list(self.result.summary.get("by_variation", {}).keys())
        if var_names:
            header = "| シナリオ |" + "|".join(f" {v} " for v in var_names) + "|"
            separator = "|---------|" + "|".join("------" for _ in var_names) + "|"
            lines.extend([header, separator])

            for scn_name, scn_data in self.result.summary.get("by_scenario", {}).items():
                row_parts = [f"| {scn_name} |"]
                for var_name in var_names:
                    var_result = scn_data.get("by_variation", {}).get(var_name, {})
                    score = var_result.get("score")
                    score_str = f"{score:.3f}" if score else "N/A"
                    row_parts.append(f" {score_str} |")
                lines.append("".join(row_parts))

        lines.extend([
            "",
            "---",
            "",
            "## 3. 詳細結果",
            "",
        ])

        # 各シナリオの詳細
        for scn in self.result.scenarios:
            scn_name = scn["name"]
            lines.extend([
                f"### 3.{self.result.scenarios.index(scn)+1} {scn_name}",
                "",
                f"**プロンプト**: {scn['initial_prompt']}",
                "",
            ])

            scn_results = [r for r in self.result.results if r.scenario_name == scn_name]
            for sr in scn_results:
                lines.extend([
                    f"#### {sr.variation_name}",
                    "",
                ])

                if sr.success:
                    if sr.metrics:
                        lines.append("**メトリクス**:")
                        for metric, value in sr.metrics.items():
                            if isinstance(value, float):
                                lines.append(f"- {metric}: {value:.3f}")
                            else:
                                lines.append(f"- {metric}: {value}")
                        lines.append("")

                    lines.append("**会話**:")
                    lines.append("```")
                    for turn in sr.conversation[:5]:  # 最初の5ターンのみ
                        lines.append(f"{turn['speaker']}: {turn['content']}")
                    if len(sr.conversation) > 5:
                        lines.append(f"... (残り {len(sr.conversation) - 5} ターン)")
                    lines.append("```")
                else:
                    lines.append(f"**エラー**: {sr.error}")

                lines.append("")

        lines.extend([
            "---",
            "",
            "## 4. 考察",
            "",
            "> TODO: 結果に基づく考察を記載",
            "",
            "---",
            "",
            f"*生成日時: {datetime.now().isoformat()}*",
        ])

        return "\n".join(lines)

    def save_markdown(self, output_dir: Path):
        """Markdownレポートを保存"""
        report_path = output_dir / self.result.experiment_id / "REPORT.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown())

        return report_path

    def print_summary(self):
        """サマリーをコンソールに出力"""
        print("\n" + "=" * 60)
        print(f"EXPERIMENT: {self.result.experiment_name}")
        print("=" * 60)

        print(f"\nTotal runs: {self.result.summary.get('total_runs', 0)}")
        print(f"Successful: {self.result.summary.get('successful_runs', 0)}")

        print("\n--- By Variation ---")
        for var_name, var_data in self.result.summary.get("by_variation", {}).items():
            avg = var_data.get("avg_score")
            avg_str = f"{avg:.3f}" if avg else "N/A"
            print(f"  {var_name}: {avg_str}")

        print("\n--- By Scenario ---")
        for scn_name, scn_data in self.result.summary.get("by_scenario", {}).items():
            print(f"\n  {scn_name}:")
            for var_name, var_result in scn_data.get("by_variation", {}).items():
                score = var_result.get("score")
                score_str = f"{score:.3f}" if score else "N/A"
                print(f"    {var_name}: {score_str}")

        print("\n" + "=" * 60)
