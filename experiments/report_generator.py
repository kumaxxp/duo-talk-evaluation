"""会話実験レポート生成器.

会話実験の結果を詳細なマークダウンレポートとして出力する。
Thought/Output、GM介入、アクションなどを省略せずに記録。

Usage:
    python -m experiments.report_generator --results results/gm_2x2_xxx/
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def load_results(results_dir: Path) -> tuple[dict, list[dict], bool]:
    """Load results.json and turns data.

    Prefers turns_log.json (full data) over examples_index.csv (truncated).

    Returns:
        (metadata, rows, is_full_data) - is_full_data is True if turns_log.json was used
    """
    results_json = results_dir / "results.json"
    turns_log_path = results_dir / "turns_log.json"
    csv_path = results_dir / "examples_index.csv"

    with open(results_json, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # Prefer turns_log.json for full content
    if turns_log_path.exists():
        with open(turns_log_path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return metadata, rows, True
    else:
        # Fallback to CSV (truncated data)
        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return metadata, rows, False


def load_scenario(scenario_name: str) -> Optional[dict]:
    """Load scenario JSON if exists."""
    scenarios_dir = Path(__file__).parent / "scenarios"
    scenario_path = scenarios_dir / f"{scenario_name}.json"

    if scenario_path.exists():
        with open(scenario_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def generate_conversation_report(
    results_dir: str | Path,
    output_path: Optional[str | Path] = None,
) -> str:
    """Generate detailed conversation report.

    Args:
        results_dir: Path to results directory
        output_path: Optional output path for the report

    Returns:
        Generated report as markdown string
    """
    results_dir = Path(results_dir)
    metadata, rows, is_full_data = load_results(results_dir)

    # Helper to get boolean values (JSON has native bool, CSV has strings)
    def get_bool(row: dict, key: str, default: bool = False) -> bool:
        val = row.get(key, default)
        if isinstance(val, bool):
            return val
        return str(val).lower() == "true"

    # Helper to get int values
    def get_int(row: dict, key: str, default: int = 0) -> int:
        val = row.get(key, default)
        if isinstance(val, int):
            return val
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    # Helper to get list as string (for action_intents etc)
    def get_list_str(row: dict, key: str) -> str:
        val = row.get(key, "")
        if isinstance(val, list):
            return "|".join(str(v) for v in val)
        return str(val) if val else ""

    # Extract experiment info
    experiment_id = metadata.get("experiment_id", "unknown")
    mode = metadata.get("mode", "unknown")
    model = metadata.get("model", "unknown")
    max_turns = metadata.get("max_turns", 0)

    # Get scenario from first row
    scenario = rows[0].get("session_id", "").split("_")[-2] if rows else "default"
    scenario_data = load_scenario(scenario)

    # Get condition info
    conditions = list(metadata.get("conditions", {}).keys())
    condition_str = ", ".join(conditions)

    # Build report
    lines = []

    # Header
    lines.append(f"# 会話実験レポート: {experiment_id}")
    lines.append("")
    lines.append("| 項目 | 値 |")
    lines.append("|------|-----|")
    lines.append(f"| 実験ID | {experiment_id} |")
    lines.append(f"| 日時 | {datetime.now().isoformat()} |")
    lines.append(f"| プロファイル | {metadata.get('metadata', {}).get('profile', 'unknown')} |")
    lines.append(f"| シナリオ | {scenario} |")
    lines.append(f"| モデル | {model} |")
    lines.append(f"| ターン数 | {len(rows)} |")
    lines.append(f"| Condition | {condition_str} |")
    lines.append("")

    # GM-018+1: Terminology definitions
    lines.append("## 用語定義")
    lines.append("")
    lines.append("| 用語 | 定義 |")
    lines.append("|------|------|")
    lines.append("| **gm_injection** | fact_cardsを付与（毎ターンで発生しうる） |")
    lines.append("| **gm_intervention** | 何かを変えた/止めた/直した（repair, deny, retry等） |")
    lines.append("| **trigger** | interventionの契機（none=何もしなかった） |")
    lines.append("| **repair_steps** | 適用したrepair transformの段数（0=なし, 1=STRIP, 2+=中/重） |")
    lines.append("| **parse_attempts** | パース試行回数 = `1 + repair_steps` |")
    lines.append("")

    # World state section
    lines.append("## ワールド状態")
    lines.append("")

    if scenario_data:
        time_of_day = scenario_data.get("time_of_day", "unknown")
        locations = scenario_data.get("locations", {})
        characters = scenario_data.get("characters", {})

        # Find first location
        first_location = list(locations.keys())[0] if locations else "不明"
        lines.append(f"**場所**: {first_location}")
        lines.append(f"**時間帯**: {time_of_day}")
        lines.append("")

        lines.append("### Props（利用可能オブジェクト）")
        if first_location in locations:
            props = locations[first_location].get("props", [])
            for prop in props:
                lines.append(f"- {prop}")
        lines.append("")

        lines.append("### キャラクター状態")
        lines.append("| キャラクター | 場所 | 所持品 |")
        lines.append("|-------------|------|--------|")
        for char_name, char_data in characters.items():
            loc = char_data.get("location", "不明")
            holding = ", ".join(char_data.get("holding", [])) or "なし"
            lines.append(f"| {char_name} | {loc} | {holding} |")
        lines.append("")
    else:
        lines.append("**場所**: キッチン（デフォルト）")
        lines.append("**時間帯**: morning")
        lines.append("")
        lines.append("### Props（デフォルト）")
        lines.append("- コーヒーメーカー, マグカップ, 冷蔵庫, トースター, パン, コーヒー豆")
        lines.append("")

    # Conversation log section
    lines.append("## 会話ログ")
    lines.append("")

    intervention_summary = []

    for i, row in enumerate(rows):
        turn_num = get_int(row, "turn_number", i)
        speaker = row.get("speaker", "?")
        thought = row.get("parsed_thought", "") or ""
        speech = row.get("parsed_speech", "") or ""
        action_intents = get_list_str(row, "action_intents")
        final_action_intents = get_list_str(row, "final_action_intents")
        allowed = get_bool(row, "allowed", True)
        trigger = row.get("injection_trigger") or row.get("trigger") or "none"
        denied_reason = row.get("denied_reason", "") or ""
        # For JSON, count fact_cards list; for CSV, use fact_cards_count
        fact_cards = row.get("fact_cards", [])
        fact_cards_count = len(fact_cards) if isinstance(fact_cards, list) else get_int(row, "fact_cards_count", 0)
        preflight_triggered = get_bool(row, "preflight_triggered")
        # For JSON, get first guidance card; for CSV, use guidance_preview
        guidance_cards = row.get("guidance_cards", [])
        guidance_preview = guidance_cards[0] if isinstance(guidance_cards, list) and guidance_cards else row.get("guidance_preview", "")
        retry_steps = get_int(row, "retry_steps", 0)
        give_up = get_bool(row, "give_up")
        silent_correction = get_bool(row, "silent_correction")
        raw_speech = row.get("raw_speech", "") or ""
        final_speech = row.get("final_speech", "") or ""
        total_generation_calls = get_int(row, "total_generation_calls", 1)

        # Build intervention info
        intervention_info = "なし"
        if trigger and trigger != "none":
            intervention_info = trigger
        if denied_reason:
            intervention_info = f"{trigger} ({denied_reason})"

        # Build preflight info
        preflight_info = "なし"
        if preflight_triggered:
            preflight_info = f"トリガー (retry_steps={retry_steps})"
            if give_up:
                preflight_info += " → GIVE_UP"
            if silent_correction:
                preflight_info += " → Silent Correction"

        # GM status
        gm_status = "✅ Allowed" if allowed else f"❌ Denied ({denied_reason})"

        # Fact cards info
        fact_info = f"{fact_cards_count}枚" if fact_cards_count > 0 else "なし"

        lines.append(f"### Turn {turn_num}: {speaker}")
        lines.append("")
        lines.append("| 項目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| **Thought** | {thought or '(なし)'} |")
        lines.append(f"| **Output** | {speech or '(なし)'} |")
        lines.append(f"| **Action Intents** | {final_action_intents or action_intents or 'なし'} |")
        lines.append(f"| **GM Status** | {gm_status} |")
        lines.append(f"| **Intervention** | {intervention_info} |")
        lines.append(f"| **Fact Cards** | {fact_info} |")
        lines.append(f"| **Preflight** | {preflight_info} |")
        lines.append(f"| **Generation Calls** | {total_generation_calls} |")
        lines.append("")

        # Raw vs Final comparison (if different)
        if raw_speech and final_speech and raw_speech != final_speech:
            lines.append("**リトライ前後の比較:**")
            lines.append("")
            lines.append(f"- Before: {raw_speech}")
            lines.append(f"- After: {final_speech}")
            lines.append("")

        # Guidance preview
        if guidance_preview:
            lines.append(f"**Guidance:** `{guidance_preview}...`")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Collect intervention summary
        if trigger and trigger != "none":
            intervention_summary.append({
                "turn": turn_num,
                "speaker": speaker,
                "trigger": trigger,
                "denied_reason": denied_reason,
                "guidance": guidance_preview[:30] if guidance_preview else "-",
            })

    # Intervention summary section
    if intervention_summary:
        lines.append("## GM介入サマリー")
        lines.append("")
        lines.append("| Turn | Speaker | Trigger | Denied Reason | Guidance |")
        lines.append("|------|---------|---------|---------------|----------|")
        for item in intervention_summary:
            lines.append(
                f"| {item['turn']} | {item['speaker']} | {item['trigger']} | "
                f"{item['denied_reason'] or '-'} | {item['guidance']} |"
            )
        lines.append("")

    # Evaluation Path Summary section (GM-018)
    lines.append("## 評価経路サマリー")
    lines.append("")
    lines.append("| Turn | Speaker | Action Intents | Preflight | Δ World | Trigger | Resolution |")
    lines.append("|------|---------|----------------|-----------|---------|---------|------------|")

    physical_action_count = 0
    world_delta_total = 0
    trigger_non_none_count = 0

    for i, row in enumerate(rows):
        turn_num = get_int(row, "turn_number", i)
        speaker = row.get("speaker", "?")
        action_intents = get_list_str(row, "final_action_intents") or get_list_str(row, "action_intents")
        preflight = "✓" if get_bool(row, "preflight_triggered") else "-"
        world_delta = row.get("world_delta", [])
        delta_len = len(world_delta) if isinstance(world_delta, list) else 0
        trigger = row.get("injection_trigger") or row.get("trigger") or "none"
        resolution = row.get("resolution_method", "-") or "-"

        # Count physical actions (USE, TAKE, GIVE, MOVE)
        intent_list = action_intents.split("|") if action_intents else []
        physical_intents = [i for i in intent_list if i in ("USE", "TAKE", "GIVE", "MOVE")]
        if physical_intents:
            physical_action_count += 1

        world_delta_total += delta_len
        if trigger != "none":
            trigger_non_none_count += 1

        lines.append(f"| {turn_num} | {speaker} | {action_intents or '-'} | {preflight} | {delta_len} | {trigger} | {resolution} |")

    lines.append("")

    # Conclusion line
    total_turns = len(rows)
    if physical_action_count == 0 and world_delta_total == 0 and trigger_non_none_count == 0:
        lines.append("**結論**: 🗣️ **雑談テスト**（物理的操作なし、ワールド変更なし）")
    elif world_delta_total == 0 and physical_action_count > 0:
        lines.append(f"**結論**: ⚠️ **意図のみ検出** (action_intents={physical_action_count}回、world_delta=0) - GM解析が発動していない可能性")
    else:
        lines.append(f"**結論**: ✅ **物理操作テスト** (action_intents={physical_action_count}回、world_delta={world_delta_total}件)")
    lines.append("")

    # Turn 0 World State Analysis (GM-018)
    if rows:
        lines.append("## Turn 0 ワールド状態分析")
        lines.append("")

        first_row = rows[0]
        speech = first_row.get("parsed_speech", "") or ""

        # Check for props references in speech
        props_mentioned = []
        prop_keywords = {
            "豆": "コーヒー豆（beans）",
            "コーヒー": "コーヒー/コーヒーメーカー",
            "マグカップ": "マグカップ",
            "テレビ": "テレビ",
            "ソファ": "ソファ",
            "冷蔵庫": "冷蔵庫",
            "トースター": "トースター",
            "パン": "パン",
        }
        for keyword, display in prop_keywords.items():
            if keyword in speech:
                props_mentioned.append((keyword, display))

        lines.append("### 発話で言及されたオブジェクト")
        if props_mentioned:
            for keyword, display in props_mentioned:
                lines.append(f"- 「{keyword}」→ {display}")
        else:
            lines.append("- なし")
        lines.append("")

        lines.append("### デフォルトワールドの props")
        default_props = ["マグカップ", "コーヒーメーカー", "テレビ", "ソファ"]
        for prop in default_props:
            lines.append(f"- {prop}")
        lines.append("")

        # Check if "豆" was mentioned but not in props
        if "豆" in speech:
            lines.append("### 「豆」の解決状態")
            resolution = first_row.get("resolution_method", "none")
            resolved_target = first_row.get("resolved_target", "-")
            soft_correction = first_row.get("soft_correction", "-")
            lines.append(f"- resolution_method: `{resolution}`")
            lines.append(f"- resolved_target: `{resolved_target}`")
            lines.append(f"- soft_correction: `{soft_correction}`")
            if resolution in ("alias", "derived"):
                lines.append(f"- ✅ 「豆」はエイリアス/派生解決されました")
            elif resolution == "none":
                lines.append(f"- ⚠️ 「豆」は未解決（propsに存在しない、かつ解決されなかった）")
            lines.append("")

    # GM-018: Format Break Summary (if any)
    format_break_count = sum(1 for r in rows if get_bool(r, "format_break_triggered"))
    repaired_count = sum(1 for r in rows if get_bool(r, "repaired"))

    if format_break_count > 0:
        lines.append("## Format Break サマリー")
        lines.append("")
        lines.append("| 指標 | 値 |")
        lines.append("|------|-----|")
        lines.append(f"| format_break_total | {format_break_count} |")
        lines.append(f"| repaired_total | {repaired_count} |")
        lines.append(f"| unrepaired | {format_break_count - repaired_count} |")
        lines.append("")

        # Breakdown by type
        break_types: dict[str, int] = {}
        repair_methods: dict[str, int] = {}
        for r in rows:
            if get_bool(r, "format_break_triggered"):
                bt = r.get("format_break_type") or r.get("break_type") or "UNKNOWN"
                rm = r.get("repair_method") or "NONE"
                break_types[bt] = break_types.get(bt, 0) + 1
                repair_methods[rm] = repair_methods.get(rm, 0) + 1

        if break_types:
            lines.append("### break_type 分布")
            lines.append("")
            for bt, count in sorted(break_types.items(), key=lambda x: -x[1]):
                lines.append(f"- `{bt}`: {count}")
            lines.append("")

        if repair_methods:
            lines.append("### repair_method 分布")
            lines.append("")
            for rm, count in sorted(repair_methods.items(), key=lambda x: -x[1]):
                lines.append(f"- `{rm}`: {count}")
            lines.append("")

    # Quality metrics section
    lines.append("## 品質指標")
    lines.append("")

    total_turns = len(rows)
    allowed_count = sum(1 for r in rows if get_bool(r, "allowed", True))
    intervention_count = sum(1 for r in rows if (r.get("injection_trigger") or r.get("trigger") or "none") != "none")
    violation_count = sum(1 for r in rows if get_bool(r, "addressing_violation"))
    preflight_count = sum(1 for r in rows if get_bool(r, "preflight_triggered"))
    silent_count = sum(1 for r in rows if get_bool(r, "silent_correction"))
    total_gen_calls = sum(get_int(r, "total_generation_calls", 1) for r in rows)

    success_rate = (allowed_count / total_turns * 100) if total_turns > 0 else 0
    intervention_rate = (intervention_count / total_turns * 100) if total_turns > 0 else 0
    violation_rate = (violation_count / total_turns * 100) if total_turns > 0 else 0
    avg_gen_calls = total_gen_calls / total_turns if total_turns > 0 else 1

    # Count gm_injection (fact_cards attached)
    injection_count = sum(1 for r in rows if r.get("fact_cards") and len(r.get("fact_cards", [])) > 0)
    injection_rate = (injection_count / total_turns * 100) if total_turns > 0 else 0

    lines.append("| 指標 | 値 | 判定 |")
    lines.append("|------|-----|------|")
    lines.append(f"| Success Rate | {success_rate:.1f}% | {'🟢' if success_rate >= 90 else '🟡' if success_rate >= 70 else '🔴'} |")
    lines.append(f"| GM Injection Rate | {injection_rate:.1f}% | - |")
    lines.append(f"| GM Intervention Rate | {intervention_rate:.1f}% | - |")
    lines.append(f"| Addressing Violation Rate | {violation_rate:.1f}% | {'🟢' if violation_rate < 5 else '🟡' if violation_rate < 10 else '🔴'} |")
    lines.append(f"| Format Break Count | {format_break_count} | {'🟢' if format_break_count == 0 else '🟡'} |")
    lines.append(f"| Preflight Triggered | {preflight_count} | - |")
    lines.append(f"| Silent Correction | {silent_count} | - |")
    lines.append(f"| Avg Generation Calls | {avg_gen_calls:.2f} | {'🟢' if avg_gen_calls < 1.3 else '🟡' if avg_gen_calls < 1.5 else '🔴'} |")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().isoformat()}*")

    report = "\n".join(lines)

    # Write to file if output_path specified
    if output_path:
        output_path = Path(output_path)
        output_path.write_text(report, encoding="utf-8")

    return report


def main():
    parser = argparse.ArgumentParser(description="Generate conversation report")
    parser.add_argument("--results", required=True, help="Path to results directory")
    parser.add_argument("--output", help="Output path (default: CONVERSATION_REPORT.md in results dir)")
    args = parser.parse_args()

    results_dir = Path(args.results)
    output_path = args.output or (results_dir / "CONVERSATION_REPORT.md")

    report = generate_conversation_report(results_dir, output_path)
    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    main()
