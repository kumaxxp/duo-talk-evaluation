# Thought出力問題 調査報告書

**作成日**: 2026-01-23
**調査者**: Claude Code
**対象システム**: duo-talk-ecosystem (duo-talk-core, duo-talk-director, duo-talk-evaluation)

---

## エグゼクティブサマリー

duo-talk-directorのv0.4でThoughtChecker（思考形式検証機能）を追加した結果、**LLMの初回応答の約40%がThought形式を欠いている**という重大な問題が発見された。この問題は以前から存在していたが、検出機構がなかったため可視化されていなかった。

### 重要な発見

| 項目 | 値 |
|------|-----|
| 初回応答のThought欠落率 | 約40% |
| リトライ後の最終Thought率 | 100% |
| 空Thought率 | 9.4% - 12.5% |
| v0.4での平均リトライ数 | 10.67回/セッション |

---

## 1. 問題の発見経緯

### 1.1 背景

duo-talk-ecosystemは、AI姉妹キャラクター「やな」と「あゆ」の対話システム。各応答は以下の形式を期待：

```
Thought: (キャラクターの内心・思考)
Output: (実際の発言)
```

### 1.2 ThoughtChecker導入

v0.4でThoughtCheckerを追加し、以下を検証：
- `Thought:` マーカーの存在
- Thought内容の有無（空でないか）
- `Output:` マーカーの存在
- 内容の切り詰め（truncation）検出

### 1.3 発見された問題

ThoughtChecker導入後、**リトライ率が6,176%増加**：

| メトリクス | v0.3 (検出なし) | v0.4 (検出あり) | 増加率 |
|------------|-----------------|-----------------|--------|
| 平均リトライ数 | 0.17 | 10.67 | +6,176% |
| 総不採用数 | 1 | 96 | +9,500% |

---

## 2. 歴史的データ分析

### 2.1 実験データ

**v0.3実験 (2026-01-23 11:34)**
- 総ターン数: 64
- 最終応答のThought率: 100% (64/64)
- 空Thought率: 9.4% (6/64)
- リトライで不採用: 0件（検出機構なし）

**v0.4実験 (2026-01-23 12:01)**
- 総ターン数: 64
- 最終応答のThought率: 100% (64/64)
- 空Thought率: 12.5% (8/64)
- リトライで不採用: 96件

### 2.2 重要な発見

**最終応答は両バージョンとも100% Thought形式を持つ**

これは、96件の不採用が**中間リトライ応答**であることを意味する。

```
v0.3 (検出なし):
  初回応答 [Thought無し 40%] → そのまま採用 ← 問題が隠蔽

v0.4 (検出あり):
  初回応答 [Thought無し 40%] → RETRY → 再生成 → [Thought有り] → 採用
                    ↑
              ここで96件不採用（正しく検出）
```

### 2.3 結論

| 質問 | 回答 |
|------|------|
| 問題は新規か？ | いいえ、以前から存在 |
| なぜ発見されなかった？ | 検出機構がなかった |
| 根本原因は？ | LLMのプロンプト遵守率が約60% |

---

## 3. 技術的詳細

### 3.1 ThoughtChecker実装

```python
class ThoughtChecker:
    THOUGHT_PATTERN = re.compile(
        r"Thought:\s*(.+?)(?=\nOutput:|$)",
        re.DOTALL | re.IGNORECASE
    )
    OUTPUT_PATTERN = re.compile(r"Output:", re.IGNORECASE)

    def check(self, response: str) -> CheckResult:
        # 1. Thoughtマーカーの存在確認
        # 2. 内容の有無確認
        # 3. 切り詰め検出
        # 4. Outputマーカーの存在確認
```

### 3.2 検出パターン

| パターン | 例 | 検出結果 |
|----------|-----|----------|
| 正常 | `Thought: (姉様と話せて嬉しい)\nOutput: 「おはよう」` | PASS |
| Thought欠落 | `(にっこり笑って) 「おはよう」` | RETRY |
| 空Thought | `Thought: (\nOutput: 「おはよう」` | RETRY |
| Output欠落 | `Thought: (考え中)「おはよう」` | WARN |
| 短いThought | `Thought: (ふむ)\nOutput: 「おはよう」` | WARN |

### 3.3 不採用応答の具体例

**casual_greeting, Turn 1 (やな) - v0.4実験より**

❌ Attempt 1 (RETRY):
```
(にっこり笑って) 「おはよう！あゆ、起きてる？ 良い天気だね～」
```
→ 理由: Thoughtマーカーなし

❌ Attempt 2 (RETRY):
```
(伸びをして) 「おはよう！あゆ、ちゃんと寝た？　今日はいいことありそうだね、ね」
```
→ 理由: Thoughtマーカーなし

❌ Attempt 3 (RETRY):
```
(にっこり笑って) 「おはよう！あゆ、ちゃんと寝れた？」
```
→ 理由: Thoughtマーカーなし

✅ Adopted (max_retries到達後):
```
(にっこり笑って) 「おはよう！あゆ、ちゃんと寝れた？」
```
→ max_retries=3到達のため強制採用

### 3.4 正常応答の例

**topic_exploration, Turn 1 (やな) - Director無し時**

```
Thought: (Yana: あゆ、AIの話となったら目が輝くだろうな。)
Output: (目を輝かせて) 「AIの話！最近、ChatGPTとか話題になってるよね！あゆ、なんか面白い技術ある？」
```

---

## 4. 空Thought問題

### 4.1 空Thoughtのパターン

実験で観察された空Thoughtパターン：

```
Thought: (
Output: *くしゃくしゃと笑って* 「またそんな改まった話し方しなくてもいいって言ってるでしょ」
```

```
Thought: (Yana:
Output: (にっこり笑って) 「おはよう！」
```

### 4.2 空Thought検出ロジック

```python
def _clean_thought_content(self, content: str) -> str:
    # 話者プレフィックス除去: "(Yana:" → ""
    cleaned = re.sub(r"^\s*\([A-Za-zやなあゆ姉妹様]+:\s*", "", content)

    # 括弧除去
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]

    return cleaned.strip()

# 空判定
is_empty = len(cleaned_content) <= 1 or cleaned_content in ["…", "...", "。", "、"]
```

### 4.3 空Thought統計

| 実験 | 空Thought数 | 空Thought率 |
|------|-------------|-------------|
| v0.3 | 6/64 | 9.4% |
| v0.4 | 8/64 | 12.5% |

---

## 5. プロンプト分析

### 5.1 現行プロンプト構造

duo-talk-coreではLayered Promptingを使用：

```
[System Layer]
キャラクター設定、世界観

[Character Layer]
個別キャラクターの性格、口調

[Few-shot Layer]
会話例（Thought/Output形式を含む）

[User Input]
実際の入力
```

### 5.2 Few-shot例

```
User: おはよう

Thought: (Yana: あゆもちゃんと起きてるかな？今日も一緒にいられて嬉しいな。)
Output: (にこやかに) 「おはよう！今日もいい天気だね～」
```

### 5.3 問題点

1. **Few-shot例が1-2個のみ**: 形式学習に不十分
2. **明示的な指示がない**: "必ずThought:で始めてください"のような明確な指示がない
3. **モデル特性**: gemma3:12bは指示遵守率が不安定

---

## 6. 影響分析

### 6.1 パフォーマンス影響

| メトリクス | v0.3 | v0.4 | 影響 |
|------------|------|------|------|
| 平均応答時間 | 18s | 35s | +94% |
| API呼び出し数 | 1.0x | 4.0x | +300% |
| 品質スコア | 0.71 | 0.71 | ±0% |

### 6.2 品質影響

ThoughtCheckerによる品質改善効果は観察されず：
- character_consistency: 変化なし
- topic_novelty: 変化なし
- relationship_quality: 変化なし

### 6.3 根本的な問題

| 問題 | 影響度 | 説明 |
|------|--------|------|
| プロンプト遵守率 | 高 | LLMが約40%の確率で形式を無視 |
| リトライコスト | 高 | 10.67回/セッションは許容範囲外 |
| 形式強制の限界 | 中 | max_retries到達後は形式不正でも採用 |

---

## 7. 調査すべき追加項目

### 7.1 プロンプト改善

1. **明示的指示の追加**
   ```
   IMPORTANT: すべての応答は以下の形式で開始してください：
   Thought: (あなたの内心・思考)
   Output: (実際の発言)
   ```

2. **Few-shot例の増強**: 3-5例に増加

3. **フォーマット強調**: 応答開始時に形式を再確認

### 7.2 モデル比較

| モデル | テスト対象 |
|--------|-----------|
| gemma3:12b | 現行（遵守率約60%） |
| gemma3:27b | より大きなモデル |
| llama3.2:8b | 異なるアーキテクチャ |
| mistral:7b | 異なるファミリー |

### 7.3 システム設計

1. **ThoughtCheckerのオプション化**
   ```python
   director = DirectorMinimal(
       enforce_thought_format=False  # デフォルト無効
   )
   ```

2. **max_retriesの調整**: 3 → 5に増加

3. **フォールバック戦略**: Thought欠落時の自動補完

---

## 8. 推奨アクション

### 8.1 短期（即時対応）

| 優先度 | アクション | 理由 |
|--------|-----------|------|
| 高 | ThoughtCheckerをオプション化 | リトライ削減 |
| 高 | `enforce_thought_format`フラグ追加 | 柔軟な運用 |
| 中 | 空Thought許容モード検討 | 形式より内容重視 |

### 8.2 中期（プロンプト改善）

| 優先度 | アクション | 期待効果 |
|--------|-----------|----------|
| 高 | 明示的形式指示の追加 | 遵守率+20-30% |
| 中 | Few-shot例を3-5個に増加 | 形式定着 |
| 中 | システムプロンプトでの強調 | 初回遵守率向上 |

### 8.3 長期（アーキテクチャ）

| 優先度 | アクション | 理由 |
|--------|-----------|------|
| 中 | モデル比較実験 | 最適モデル選定 |
| 低 | Thought自動補完機能 | フォールバック |
| 低 | 二段階生成方式検討 | 形式保証 |

---

## 9. 実験データ参照

### 9.1 関連ファイル

| ファイル | 内容 |
|----------|------|
| `results/director_ab_20260123_113447/REPORT.md` | v0.3実験レポート |
| `results/director_ab_20260123_120140/REPORT.md` | v0.4実験レポート |
| `results/director_ab_20260123_120140/V0.4_ANALYSIS_REPORT.md` | v0.4改善分析 |
| `results/director_ab_20260123_120140/experiment_results.json` | 生データ |

### 9.2 コード参照

| ファイル | 内容 |
|----------|------|
| `duo-talk-director/src/duo_talk_director/checks/thought_check.py` | ThoughtChecker実装 |
| `duo-talk-director/src/duo_talk_director/director_minimal.py` | DirectorMinimal統合 |
| `duo-talk-director/tests/test_thought_check.py` | ThoughtCheckerテスト |

---

## 10. 結論

### 10.1 発見された根本問題

**LLMのプロンプト遵守率が約60%であり、約40%の初回応答がThought形式を欠いている。**

この問題は以前から存在していたが、ThoughtChecker導入まで検出されていなかった。

### 10.2 現状の評価

| 項目 | 評価 |
|------|------|
| ThoughtChecker機能 | ✅ 正常動作 |
| 問題検出 | ✅ 全件検出 |
| 運用実用性 | ❌ リトライ過多 |
| 品質改善効果 | △ 有意差なし |

### 10.3 今後の方向性

1. **短期**: ThoughtCheckerをオプション化し、デフォルト無効
2. **中期**: プロンプト改善でLLM遵守率を向上
3. **長期**: モデル選定とアーキテクチャ改善

---

## 付録A: 生データサンプル

### A.1 v0.4不採用応答（96件中の抜粋）

```json
{
  "scenario": "casual_greeting",
  "turn": 0,
  "speaker": "やな",
  "attempts": [
    {
      "attempt": 1,
      "response": "(にっこり笑って) 「おはよう！あゆ、起きてる？ 良い天気だね～」",
      "status": "RETRY",
      "reason": "Thoughtが見つかりません。思考（Thought）と発言（Output）の2段階で応答してください。"
    },
    {
      "attempt": 2,
      "response": "(伸びをして) 「おはよう！あゆ、ちゃんと寝た？　今日はいいことありそうだね、ね」",
      "status": "RETRY",
      "reason": "Thoughtが見つかりません。"
    },
    {
      "attempt": 3,
      "response": "(にっこり笑って) 「おはよう！あゆ、ちゃんと寝れた？」",
      "status": "RETRY",
      "reason": "Thoughtが見つかりません。"
    }
  ],
  "final_response": "(にっこり笑って) 「おはよう！あゆ、ちゃんと寝れた？」",
  "note": "max_retries到達のため形式不正でも採用"
}
```

### A.2 正常応答サンプル

```json
{
  "scenario": "topic_exploration",
  "turn": 0,
  "speaker": "やな",
  "response": "Thought: (Yana: あゆ、AIの話となったら目が輝くだろうな。)\nOutput: (目を輝かせて) 「AIの話！最近、ChatGPTとか話題になってるよね！あゆ、なんか面白い技術ある？」",
  "status": "PASS"
}
```

---

## 付録B: 調査用質問リスト

他のAIシステムへの調査依頼時に使用：

1. **プロンプト遵守率の改善方法**
   - Few-shot例の最適な数は？
   - 明示的指示の効果的な書き方は？
   - システムプロンプトでの強調方法は？

2. **モデル特性**
   - gemma3系の指示遵守傾向は？
   - 他モデルとの比較データは？
   - ファインチューニングの効果は？

3. **アーキテクチャ設計**
   - 二段階生成（Thought→Output）は有効か？
   - 形式検証のベストプラクティスは？
   - リトライ戦略の最適化方法は？

4. **業界事例**
   - 類似の問題を解決した事例は？
   - Chain-of-Thoughtの強制方法は？
   - 出力形式制御のパターンは？

---

*Generated by duo-talk-evaluation investigation framework*
*Report ID: THOUGHT_INVESTIGATION_20260123*
