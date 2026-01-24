# Phase 2.3 仕様書

**文書ID**: 20260124_006
**作成日**: 2026-01-24
**ステータス**: Draft
**前提**: Phase 2.2.1完了

---

## 目的

TWO_PASS会話エンジンを **「壊れずに」「没入感を壊さずに」** 運用できる状態にする。
高度化（StateUpdater/RAG/物語進行）は対象外。

---

## スコープ

### ✅ In Scope

| 項目 | 実装クラス/モジュール | 状態 |
|------|---------------------|:----:|
| TWO_PASSデフォルト運用 | `GenerationMode.TWO_PASS` | ✅ 完了 |
| DirectorMinimal（本番） | `DirectorMinimal` | ✅ 完了 |
| DirectorHybrid（評価用） | `DirectorHybrid` | ✅ 完了 |
| ActionSanitizer軽量版 | `ActionSanitizer` | ✅ 完了 |
| StateExtractor | `StateExtractor` | ✅ 完了 |
| ログ収集 | 🔜 新規 | Phase 2.3 |
| 回帰ミニベンチ | 🔜 新規 | Phase 2.3 |

### ❌ Out of Scope

| 項目 | 理由 |
|------|------|
| 高度なStateUpdater | 抽出のみも含めて先送り |
| 行動生成専用LLM | TWO_PASS+Scene制約で十分 |
| 多エージェント構成 | 過設計リスク |
| RAG統合 | Phase 3 |
| 小説向きAI混合 | Phase 3以降 |
| 形態素解析 | Phase 3候補 |

---

## 入出力仕様

### Phase 1: Thought生成

| 項目 | 仕様 |
|------|------|
| 出力形式 | Thoughtテキストのみ |
| 禁止 | 台詞記号「」『』、行動括弧（）、*asterisks* |
| 長さ | 1〜4行 |
| max_tokens | 120 |
| 実装 | `TwoPassGenerator.generate_thought()` |

**正常例**:
```
あゆも起きてるかな？朝から何して遊ぶか、もうワクワクしてる！
```

**NG例**:
```
（嬉しそうに）あゆに会えて嬉しい  ← 行動括弧NG
「おはよう」って言おう  ← 台詞記号NG
```

### Phase 2: Speech+Action生成

| 項目 | 仕様 |
|------|------|
| 正規形1 | `（行動）「台詞」` |
| 正規形2 | `「台詞」` |
| 行動 | 最大1個、台詞の前のみ |
| *asterisks* | 禁止（出たらサニタイズ） |
| max_tokens | 300 |
| 実装 | `TwoPassGenerator.generate_output()` |

**正常例**:
```
（微笑んで）「おはよう、あゆ。今日も元気そうだね」
「おはようございます、姉様」
```

**NG例（サニタイズ対象）**:
```
*微笑んで* 「おはよう」  ← asterisks禁止
（コーヒーを飲みながら）「おはよう」  ← Sceneにコーヒーなければ削除
```

---

## チェック・サニタイズ仕様

### DirectorMinimal（本番用）

| チェック | 条件 | 結果 |
|---------|------|------|
| Thought存在 | 空/括弧だけ/3文字未満 | RETRY |
| 出力フォーマット | 正規形でない | RETRY |
| 禁止語 | NG辞書に該当 | RETRY |

**設定**:
```python
DirectorMinimal(
    strict_thought_check=True,  # 空Thought→RETRY
    min_thought_length=3,       # 最小文字数
)
```

### ActionSanitizer（本番用）

| 条件 | 判定 | 挙動 |
|------|------|------|
| Action内にProps | Scene（inventory/nearby/temporary）に存在しない | 置換or削除 |

**置換ルール**:
```python
FALLBACK_ACTIONS = {
    "コーヒー": "一息つく",
    "眼鏡": "目を細める",
    "スマホ": "考え込む",
    # ...
}
DEFAULT_FALLBACK = "小さく頷く"
```

**ログ出力**:
```python
@dataclass
class SanitizerResult:
    sanitized_text: str
    action_removed: bool
    action_replaced: bool
    blocked_props: list[str]
    original_action: str | None
```

---

## ログ仕様

### ActionSanitizerログ

| フィールド | 型 | 説明 |
|-----------|-----|------|
| timestamp | str | ISO形式 |
| turn_number | int | ターン番号 |
| speaker | str | 話者名 |
| blocked_props | list[str] | ブロックされたprops |
| action_removed | bool | 削除されたか |
| action_replaced | bool | 置換されたか |
| original_action | str | 元のAction |

### Thoughtログ

| フィールド | 型 | 説明 |
|-----------|-----|------|
| timestamp | str | ISO形式 |
| turn_number | int | ターン番号 |
| speaker | str | 話者名 |
| thought | str | Thoughtテキスト |
| emotion | str | 検出感情 |
| emotion_intensity | float | 感情強度 |
| relationship_tone | str | 関係性トーン |

---

## 回帰ミニベンチ仕様

### 固定シナリオ

| シナリオ | プロンプト | ターン数 |
|----------|----------|---------|
| casual_greeting | おはよう、二人とも | 6 |
| topic_exploration | 最近のAI技術について話して | 6 |
| emotional_support | 最近疲れてるんだ... | 6 |

### 評価指標

| 指標 | 計算方法 | 目標 |
|------|---------|------|
| format_success_rate | 正規形出力数 / 全出力数 | 100% |
| thought_missing_rate | Thought欠落数 / 全ターン数 | ≤1% |
| avg_retries | 総リトライ数 / 全ターン数 | ≤0.1 |
| action_sanitized_rate | サニタイズ発動数 / Action付きターン数 | 把握のみ |
| blocked_props_topN | ブロックprops上位N件 | 把握のみ |

### 実行方法

```bash
# ミニベンチ実行
make benchmark

# または
python scripts/ci/run_benchmark.py --scenarios all
```

---

## 完了条件（Definition of Done）

### 必須条件

| 条件 | 基準 |
|------|------|
| format_success_rate | = 100% |
| thought_missing_rate | ≤ 1% |
| avg_retries | ≤ 0.1 |
| action_sanitized_rate | 把握できている |
| blocked_props_topN | トップ原因が特定できている |

### 確認事項

- [ ] 3シナリオ×6ターンで上記基準を満たす
- [ ] ActionSanitizerログが正常に出力される
- [ ] Thoughtログが正常に出力される
- [ ] 回帰ミニベンチがCIで実行可能

---

## 実装タスク

### Phase 2.3.1: ログ収集

| タスク | 優先度 | 見積 |
|--------|:------:|------|
| ActionSanitizerログ出力追加 | 高 | 小 |
| Thoughtログ出力追加 | 高 | 小 |
| ログ保存先設定 | 中 | 小 |

### Phase 2.3.2: 回帰ミニベンチ

| タスク | 優先度 | 見積 |
|--------|:------:|------|
| ベンチマークスクリプト作成 | 高 | 中 |
| 指標計算ロジック | 高 | 中 |
| CIへの統合 | 中 | 小 |
| レポート自動生成 | 低 | 小 |

---

## 設定パラメータ

### DirectorMinimal

```python
# duo-talk-director/src/duo_talk_director/director_minimal.py
DEFAULT_CONFIG = {
    "strict_thought_check": True,
    "min_thought_length": 3,
    "max_retries": 3,
}
```

### ActionSanitizer

```python
# duo-talk-director/src/duo_talk_director/checks/action_sanitizer.py
PROPS_NG_DICT = {
    "コーヒー", "眼鏡", "スマホ", "タバコ", ...
}
FALLBACK_ACTIONS = {
    "コーヒー": "一息つく",
    "眼鏡": "目を細める",
    ...
}
```

### TwoPassGenerator

```python
# duo-talk-core/src/duo_talk_core/two_pass_generator.py
DEFAULT_CONFIG = {
    "thought_max_tokens": 120,
    "output_max_tokens": 300,
    "temperature": 0.7,
}
```

---

## 関連ファイル

| ファイル | 役割 |
|----------|------|
| [dialogue_manager.py](../../../duo-talk-core/src/duo_talk_core/dialogue_manager.py) | 生成モード管理 |
| [two_pass_generator.py](../../../duo-talk-core/src/duo_talk_core/two_pass_generator.py) | TWO_PASS生成 |
| [director_minimal.py](../../../duo-talk-director/src/duo_talk_director/director_minimal.py) | 静的チェック |
| [action_sanitizer.py](../../../duo-talk-director/src/duo_talk_director/checks/action_sanitizer.py) | Propsサニタイズ |
| [state/extractor.py](../../../duo-talk-director/src/duo_talk_director/state/extractor.py) | 状態抽出 |

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-01-24 | 1.0 | 初版作成 |

---

*このドキュメントはPhase 2.3の実装仕様を定義します*
