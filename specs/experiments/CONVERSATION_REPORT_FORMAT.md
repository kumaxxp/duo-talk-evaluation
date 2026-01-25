# 会話実験レポートフォーマット仕様書

## 概要

会話実験の結果を統一フォーマットで記録するための仕様書。
Thought/Output、GM介入、アクション検出などを省略せずに記録する。

## レポート構成

### 1. 実験概要セクション

```markdown
# 会話実験レポート: {experiment_id}

| 項目 | 値 |
|------|-----|
| 実験ID | {experiment_id} |
| 日時 | {timestamp} |
| プロファイル | {profile} |
| シナリオ | {scenario} |
| モデル | {model} |
| ターン数 | {turns} |
| Condition | {condition} |
```

### 2. ワールド状態セクション

```markdown
## ワールド状態

**場所**: {location}
**時間帯**: {time_of_day}

### Props（利用可能オブジェクト）
- {prop1}
- {prop2}
- ...

### キャラクター状態
| キャラクター | 場所 | 所持品 |
|-------------|------|--------|
| やな | {location} | {holding} |
| あゆ | {location} | {holding} |
```

### 3. 会話ログセクション（メイン）

各ターンを以下の表形式で記録：

```markdown
## 会話ログ

### Turn {n}: {speaker}

| 項目 | 内容 |
|------|------|
| **Thought** | {full_thought} |
| **Output** | {full_speech} |
| **Action Intents** | {action_intents} |
| **GM Status** | {allowed/denied} |
| **Intervention** | {trigger_type or "なし"} |
| **Fact Cards** | {fact_cards or "なし"} |
| **Preflight** | {preflight_status} |
| **Latency** | {latency_ms}ms |

**Raw Output** (参考):
```
{raw_output}
```
```

### 4. GM介入詳細セクション

```markdown
## GM介入サマリー

| Turn | Speaker | Trigger | Denied Reason | Guidance |
|------|---------|---------|---------------|----------|
| 1 | やな | format_break | - | - |
| 3 | あゆ | deny | MISSING_OBJECT | ALTERNATIVES提示 |
```

### 5. 品質指標セクション

```markdown
## 品質指標

| 指標 | 値 | 判定 |
|------|-----|------|
| Success Rate | {rate}% | {status} |
| GM Intervention Rate | {rate}% | - |
| Addressing Violation Rate | {rate}% | {status} |
| Preflight Triggered | {count} | - |
| Silent Correction | {count} | - |
| Avg Latency | {ms}ms | - |
```

## 出力例

以下は実際のレポート出力例：

---

# 会話実験レポート: normal_conv_example

| 項目 | 値 |
|------|-----|
| 実験ID | normal_conv_example |
| 日時 | 2026-01-25T15:42:51 |
| プロファイル | dev |
| シナリオ | default |
| モデル | gemma3:12b |
| ターン数 | 8 |
| Condition | D (Inject ON, GM ON) |

## ワールド状態

**場所**: キッチン
**時間帯**: morning

### Props
- コーヒーメーカー
- マグカップ
- 冷蔵庫
- トースター
- パン
- コーヒー豆

### キャラクター状態
| キャラクター | 場所 | 所持品 |
|-------------|------|--------|
| やな | キッチン | なし |
| あゆ | キッチン | なし |

## 会話ログ

### Turn 0: やな

| 項目 | 内容 |
|------|------|
| **Thought** | あー、朝か。あゆはまだ寝てるかな？コーヒーでも淹れて、ちょっとおしゃべりしようかな。 |
| **Output** | *コーヒーメーカーに豆を入れ、スイッチを入れる* ふー、いい香り。あゆ、起きなーい。ちょっとコーヒー |
| **Action Intents** | USE(コーヒーメーカー) |
| **GM Status** | ✅ Allowed |
| **Intervention** | format_break |
| **Fact Cards** | WORLD_STATE更新 |
| **Preflight** | なし |
| **Latency** | 1237ms |

---

## 使用方法

### スクリプトからの生成

```python
from experiments.report_generator import generate_conversation_report

generate_conversation_report(
    results_dir="results/gm_2x2_xxx/",
    output_path="results/gm_2x2_xxx/CONVERSATION_REPORT.md"
)
```

### CLI

```bash
python -m experiments.generate_report --results results/gm_2x2_xxx/
```

---

*仕様バージョン: 1.0*
*作成日: 2026-01-25*
