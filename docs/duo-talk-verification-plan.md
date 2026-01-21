# duo-talk 深掘り検証計画書

**作成日**: 2026-01-21
**目的**: Phase 0評価結果を受け、LLM・プロンプト・RAG・Directorの各変数が品質に与える影響を体系的に検証し、Phase 1設計の根拠とする

---

## 1. Phase 0評価結果サマリー

### 1.1 総合スコア比較

| システム | 総合スコア | 処理時間 | 主な課題 |
|----------|-----------|----------|----------|
| duo-talk | 0.695 (1位) | 約2分/シナリオ | JetRacer文脈混入、リトライ遅延 |
| duo-talk-simple | 0.675 (2位) | 高速 | emotional_supportで攻撃的口調 |
| duo-talk-silly | 0.665 (3位) | 最速 | 一人称不一致、concreteness低 |

### 1.2 メトリクス別傾向

| メトリクス | duo-talk | duo-talk-simple | duo-talk-silly | 優位システム |
|-----------|----------|-----------------|----------------|--------------|
| naturalness | 0.700 | 0.750 | **0.900** | duo-talk-silly |
| consistency | 0.700 | 0.700 | 0.600 | duo-talk / simple |
| relevance | 0.750 | 0.700 | 0.800 | duo-talk-silly |
| concreteness | 0.625 | 0.600 | **0.200** | duo-talk |
| emotional_support | 0.700 | **0.600** | 0.800 | duo-talk-silly |

**注目点**:
- duo-talk-sillyはnaturalnessが最高だがconcretenessが極端に低い
- duo-talk-simpleはemotional_supportシナリオで攻撃的口調（0.600）
- duo-talkはバランス型だが処理時間が長い

---

## 2. 現状の変数マトリクス

| 変数 | duo-talk | duo-talk-simple | duo-talk-silly |
|------|----------|-----------------|----------------|
| **LLM** | Swallow 8B (Ollama) | Swallow 8B (Ollama) | Gemma2 27B (KoboldCPP) |
| **プロンプト構造** | レイヤリング + Director | シンプル構造 + RAG | SillyTavern形式（最小） |
| **RAG** | あり（ChromaDB） | あり（ChromaDB） | なし |
| **Director** | あり（NoveltyGuard含む） | なし | なし |
| **FactCheck** | あり（オプション） | なし | なし |
| **Few-shot** | 状況トリガー式 | 状態ベース | 固定例 |

### 2.1 問題：複数変数が同時に異なるため因果が不明確

現状では「duo-talk-sillyのnaturalnessが高い」理由が：
- Gemma2 27Bの能力によるものか？
- プロンプト構造のシンプルさによるものか？
- RAGがない分、余計な情報が混入しないからか？

を切り分けられていない。

---

## 3. 検証計画

### 3.1 検証軸の優先順位

| 優先度 | 検証軸 | 理由 | 工数 |
|--------|--------|------|------|
| **1** | **LLMの影響** | モデルサイズ・学習データの差が最大の変数 | 中 |
| **2** | **プロンプト構造の影響** | 設計変更で対応可能な領域 | 小 |
| 3 | RAGの影響 | concretenessへの寄与を検証 | 中 |
| 4 | Directorの影響 | 処理時間と品質のトレードオフ | 中 |

---

## 4. 検証軸1: LLMの影響（最優先）

### 4.1 仮説

| 仮説ID | 内容 | 検証方法 |
|--------|------|----------|
| H1-1 | Gemma2 27Bは日本語の自然さ（naturalness）でSwallow 8Bを上回る | 同一プロンプトでLLMのみ変更 |
| H1-2 | Swallow 8Bは日本語キャラクター一貫性（consistency）で優位 | Few-shot例の追従率を比較 |
| H1-3 | モデルサイズが大きいほど一人称ブレが少ない | 一人称出現頻度をカウント |

### 4.2 実験設計

#### 実験1-A: Swallow 8B vs Gemma2 27B（同一プロンプト）

```
条件:
- プロンプト: duo-talk-simpleのシンプル構造を使用
- シナリオ: 4シナリオ（casual_greeting, emotional_support, technical_discussion, long_conversation）
- キャラクター: やな、あゆ
- RAG: 無効
- Director: 無効

比較対象:
- Swallow 8B (Ollama)
- Gemma2 27B (KoboldCPP)

測定項目:
- naturalness, consistency, relevance, concreteness, emotional_support
- 一人称使用の正確性（やな:「私」、あゆ:「あたし」の出現率）
- Few-shot例への追従率（口調パターンの一致度）
```

#### 実験1-B: モデルサイズの段階的比較（オプション）

```
条件:
- プロンプト: 固定（duo-talk-simple形式）
- モデル: Gemma2 9B, Gemma2 27B, Swallow 8B, Swallow 70B（利用可能な場合）

測定項目:
- スコア vs モデルサイズの相関
- 処理時間 vs モデルサイズの相関
```

### 4.3 期待される知見

| 結果パターン | 解釈 | Phase 1への示唆 |
|--------------|------|-----------------|
| Gemma2 27B > Swallow 8B（全メトリクス） | モデルサイズが支配的 | 大型モデル推奨、プロンプト最適化は二次的 |
| Swallow 8B > Gemma2 27B（consistency） | 日本語特化学習が有効 | 日本語特化モデル優先、Few-shot強化 |
| 差が僅少 | プロンプト設計が支配的 | LLMより設計に注力 |

---

## 5. 検証軸2: プロンプト構造の影響

### 5.1 仮説

| 仮説ID | 内容 | 検証方法 |
|--------|------|----------|
| H2-1 | レイヤリング構造はconsistency向上に寄与 | 同一LLMでプロンプト構造のみ変更 |
| H2-2 | Few-shot例の数は口調一貫性と相関する | Few-shot 0/3/5/10例で比較 |
| H2-3 | 禁止ワード指定は攻撃的口調を抑制する | 禁止ワードあり/なしで比較 |
| H2-4 | 文数制限指定は冗長性を抑制する | 制限あり/なしで比較 |

### 5.2 プロンプト構造の比較

#### 構造A: レイヤリング（duo-talk方式）

```xml
<System Prompt is="Sister AI Duo">
<Absolute Command>
  キャラブレ防止の絶対指示
</Absolute Command>

<Deep Consciousness>
  背景知識・価値観
</Deep Consciousness>

<Surface Consciousness>
  キャラクター設定・口調
</Surface Consciousness>
</System Prompt>
```

#### 構造B: シンプル構造（duo-talk-simple方式）

```
あなたは[キャラクター名]。[要約]
信念: 「[core_belief]」

【関係性】
[姉妹の関係性定義]

★★★ [N]文以内で返答 ★★★

【会話構造ルール】
[禁止事項・推奨事項]

【キャラクター専用ルール】
[キャラクター固有の制約]

[今の状態] [state]

[返答例]
[few-shot]
```

#### 構造C: SillyTavern形式（duo-talk-silly方式）

```json
{
  "name": "キャラクター名",
  "description": "説明",
  "personality": "性格",
  "first_mes": "開始メッセージ",
  "mes_example": "<START>\n{{user}}: ...\n{{char}}: ...",
  "system_prompt": "基本指示"
}
```

### 5.3 実験設計

#### 実験2-A: プロンプト構造の比較（同一LLM）

```
条件:
- LLM: Swallow 8B（固定）
- シナリオ: 4シナリオ
- RAG: 無効
- Director: 無効

比較対象:
- 構造A: レイヤリング
- 構造B: シンプル構造
- 構造C: SillyTavern形式

測定項目:
- 5メトリクス
- キャラクター一貫性（一人称、口調パターン）
- 処理時間（プロンプト長の影響）
```

#### 実験2-B: Few-shot例の数の影響

```
条件:
- LLM: Swallow 8B（固定）
- プロンプト: 構造B（シンプル）をベースに

比較対象:
- Few-shot 0例（なし）
- Few-shot 3例
- Few-shot 5例
- Few-shot 10例

測定項目:
- consistency
- 口調パターンの一致度（手動評価）
- 処理時間（トークン数の影響）
```

#### 実験2-C: 禁止ワード・制約の効果

```
条件:
- LLM: Swallow 8B（固定）
- シナリオ: emotional_support（攻撃的口調が出やすい）

比較対象:
- 禁止ワードなし
- 禁止ワードあり（STRICT_CONVERSATION_RULES）
- 禁止ワード + キャラクター固有制約

測定項目:
- emotional_support スコア
- 禁止ワード出現回数
- 攻撃的表現の出現回数
```

### 5.4 期待される知見

| 結果パターン | 解釈 | Phase 1への示唆 |
|--------------|------|-----------------|
| レイヤリング > シンプル（consistency） | 階層構造が有効 | レイヤリング採用 |
| Few-shot 5例で飽和 | 過剰なFew-shotは不要 | 5例程度に最適化 |
| 禁止ワード効果大 | ネガティブ制約が有効 | 禁止ワード強化 |

---

## 6. 検証軸3: RAGの影響

### 6.1 仮説

| 仮説ID | 内容 | 検証方法 |
|--------|------|----------|
| H3-1 | RAGはconcreteness向上に寄与する | RAGあり/なしで比較 |
| H3-2 | RAGは文脈混入リスクを高める | 無関係な知識の出現率を測定 |
| H3-3 | RAGの知識量が多すぎると品質低下 | 注入知識量を段階的に変更 |

### 6.2 実験設計

#### 実験3-A: RAGの有無比較

```
条件:
- LLM: Swallow 8B（固定）
- プロンプト: 構造B（固定）
- Director: 無効

比較対象:
- RAGなし
- RAGあり（現行設定）

測定項目:
- concreteness
- relevance（無関係な知識混入の逆指標）
- 処理時間
```

---

## 7. 検証軸4: Directorの影響

### 7.1 仮説

| 仮説ID | 内容 | 検証方法 |
|--------|------|----------|
| H4-1 | NoveltyGuardはループ防止に有効だが処理時間を増加させる | 介入頻度と処理時間を計測 |
| H4-2 | Directorの介入は品質向上に寄与する | Director介入あり/なしで比較 |
| H4-3 | Director介入の副作用で文脈混入が発生する | JetRacerモード関連語の出現を計測 |

### 7.2 実験設計

#### 実験4-A: Directorの有無比較

```
条件:
- LLM: Swallow 8B（固定）
- プロンプト: duo-talk形式（固定）
- RAG: あり

比較対象:
- Directorなし
- Directorあり（NoveltyGuard含む）

測定項目:
- 5メトリクス
- 処理時間
- リトライ回数
- 文脈混入率（JetRacer関連語の出現）
```

---

## 8. 各システムの機能差サマリー

### 8.1 アーキテクチャ比較

```
┌─────────────────────────────────────────────────────────────────┐
│ duo-talk (フル機能)                                            │
├─────────────────────────────────────────────────────────────────┤
│ [ユーザー入力]                                                  │
│      ↓                                                          │
│ [PromptManager] → レイヤリング構造、モード別プロンプト           │
│      ↓                                                          │
│ [RAG/ChromaDB] → 知識検索・注入                                │
│      ↓                                                          │
│ [FewShotInjector] → 状況トリガー式Few-shot選択                 │
│      ↓                                                          │
│ [Director] → 品質監視・介入指示                                │
│   ├── NoveltyGuard → ループ検知                                │
│   ├── FactChecker → 事実検証（オプション）                     │
│   └── 禁止ワード検出 → 強制リトライ                            │
│      ↓                                                          │
│ [UnifiedPipeline] → 生成・リトライ制御                         │
│      ↓                                                          │
│ [LLM: Swallow 8B]                                              │
│      ↓                                                          │
│ [出力]                                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ duo-talk-simple (シンプル版)                                   │
├─────────────────────────────────────────────────────────────────┤
│ [ユーザー入力]                                                  │
│      ↓                                                          │
│ [PromptBuilder] → フラット構造、状態ベースプロンプト            │
│   ├── STRICT_CONVERSATION_RULES → 会話構造ルール               │
│   ├── get_character_constraints → キャラ固有制約               │
│   └── guess_state → 簡易状態推定                               │
│      ↓                                                          │
│ [RAG/ChromaDB] → 知識検索（シンプル版）                        │
│      ↓                                                          │
│ [Few-shot選択] → 状態ベース                                    │
│      ↓                                                          │
│ [DuoDialogueManager] → 直接生成                                │
│      ↓                                                          │
│ [LLM: Swallow 8B]                                              │
│      ↓                                                          │
│ [出力]                                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ duo-talk-silly (最小構成)                                      │
├─────────────────────────────────────────────────────────────────┤
│ [ユーザー入力]                                                  │
│      ↓                                                          │
│ [Character JSON] → SillyTavern形式の設定読み込み               │
│      ↓                                                          │
│ [直接LLM呼び出し] → プロンプト組み立て・生成                   │
│      ↓                                                          │
│ [LLM: Gemma2 27B]                                              │
│      ↓                                                          │
│ [出力]                                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 機能マトリクス

| 機能 | duo-talk | duo-talk-simple | duo-talk-silly |
|------|:--------:|:---------------:|:--------------:|
| **プロンプト構造** | |||
| レイヤリング（XML階層） | ✅ | ❌ | ❌ |
| モード別プロンプト | ✅ (JetRacer/General) | ❌ | ❌ |
| STRICT_CONVERSATION_RULES | ❌ | ✅ | ❌ |
| キャラクター固有制約 | ✅ (Director内) | ✅ | ❌ |
| 文数制限指定 | ✅ | ✅ (★強調) | ❌ |
| **Few-shot** | |||
| 状況トリガー式 | ✅ | ❌ | ❌ |
| 状態ベース | ❌ | ✅ | ❌ |
| 固定例 | ❌ | ❌ | ✅ (mes_example) |
| **知識ベース** | |||
| RAG (ChromaDB) | ✅ | ✅ | ❌ |
| 姉妹記憶システム | ✅ (SisterMemory) | ❌ | ❌ |
| **品質制御** | |||
| Director監視 | ✅ | ❌ | ❌ |
| NoveltyGuard (ループ検知) | ✅ | ❌ | ❌ |
| FactChecker (事実検証) | ✅ (オプション) | ❌ | ❌ |
| 禁止ワード強制リトライ | ✅ | ❌ | ❌ |
| **処理フロー** | |||
| マルチリトライ | ✅ (最大5回) | ❌ | ❌ |
| 評価・修正ループ | ✅ | ❌ | ❌ |

### 8.3 プロンプト設計の詳細比較

#### duo-talk: Director禁止ワード

```python
# 絶対禁止ワード（強制NOOP）
HARD_BANNED_WORDS = [
    "焦燥感", "期待", "ドキドキ", "ワクワク", "口調で", "トーンで",
    "興奮", "悲しげ", "嬉しそうに", "寂しそうに"
]

# 設定破壊検出用
SEPARATION_WORDS = [
    "姉様のお家", "姉様の家", "姉様の実家", ...
]

# あゆ専用の褒め言葉チェック
PRAISE_WORDS_FOR_AYU = [
    "いい観点", "いい質問", "さすが", "鋭い", ...
]
```

#### duo-talk-simple: キャラクター固有制約

```python
# あゆ専用ルール（調和的対立・最重要）
"""
★ 批判だけで終わるな（姉妹愛を見せろ）
★ 姉を見捨てるな
★ 認める時は渋々（ツンデレを忘れるな）
★ 感情のクッションを置け
★ 禁止ワード: 「必須です」「知りません」「素晴らしい」
"""

# 会話構造ルール（STRICT_CONVERSATION_RULES）
"""
1. ターン終了時の質問を避けろ
2. 無駄な相槌を削れ
3. 短く切れ
"""
```

#### duo-talk-silly: SillyTavern形式

```json
{
  "system_prompt": "あなたは「桜」という名前の明るく元気な日本人女性です。
- 敬語は使わず、フレンドリーなタメ口で話してください
- 「〜だよ」「〜かな」「〜だね」などの語尾を使ってください
- 絵文字やMarkdownは使わないでください
- 短い文で自然に会話してください（1-3文程度）"
}
```

---

## 9. 実施スケジュール

| フェーズ | 内容 | 期間 | 成果物 |
|----------|------|------|--------|
| **Week 1** | 検証軸1: LLM比較 | 2-3日 | LLM比較レポート |
| **Week 1** | 検証軸2: プロンプト構造比較 | 2-3日 | プロンプト設計指針 |
| **Week 2** | 検証軸3: RAG影響分析 | 1-2日 | RAG使用ガイドライン |
| **Week 2** | 検証軸4: Director影響分析 | 1-2日 | Director設計指針 |
| **Week 3** | 統合分析・Phase 1設計 | 3-4日 | Phase 1設計書 |

---

## 10. 検証環境

### 10.1 ハードウェア

| 項目 | スペック |
|------|----------|
| GPU | NVIDIA RTX A5000 (24GB VRAM) |
| メモリ | 64GB |
| OS | Ubuntu 22.04 |

### 10.2 ソフトウェア

| コンポーネント | バージョン/設定 |
|----------------|-----------------|
| Ollama | 最新版 (Swallow 8B) |
| KoboldCPP | 最新版 (Gemma2 27B) |
| 評価器 | LocalLLMEvaluator (Gemma2 27B) |
| 評価フレームワーク | duo-talk-evaluation |

### 10.3 評価メトリクス定義

| メトリクス | 定義 | スケール |
|-----------|------|----------|
| naturalness | 日本語として自然かどうか | 0.0-1.0 |
| consistency | キャラクター設定との一貫性 | 0.0-1.0 |
| relevance | ユーザー入力への適切な応答 | 0.0-1.0 |
| concreteness | 具体的な情報を含むか | 0.0-1.0 |
| emotional_support | 感情的なサポートの適切さ | 0.0-1.0 |

---

## 11. Claude Code実装指示（検証基盤構築）

### 11.1 A/Bテストフレームワーク

```markdown
## タスク: 検証用A/Bテストフレームワーク構築

【作業ディレクトリ】duo-talk-evaluation

### 要件

1. 変数隔離機能
   - LLMバックエンドの切り替え（Ollama/KoboldCPP）
   - プロンプト構造の切り替え（レイヤリング/シンプル/SillyTavern）
   - RAGの有効/無効切り替え
   - Directorの有効/無効切り替え

2. 統一評価インターフェース
   - 同一シナリオを異なる条件で実行
   - 結果をJSON形式で保存
   - メトリクス比較レポート生成

3. 実装ファイル
   - ab_test_runner.py: A/Bテスト実行エンジン
   - config_variations.yaml: 変数組み合わせ定義
   - report_generator.py: 比較レポート生成

### 出力形式

```json
{
  "experiment_id": "exp_llm_comparison_001",
  "variations": [
    {
      "name": "swallow_8b",
      "config": {"llm": "swallow_8b", "prompt": "simple", "rag": false},
      "results": {"naturalness": 0.75, "consistency": 0.80, ...}
    },
    {
      "name": "gemma2_27b",
      "config": {"llm": "gemma2_27b", "prompt": "simple", "rag": false},
      "results": {"naturalness": 0.90, "consistency": 0.60, ...}
    }
  ],
  "statistical_significance": {...}
}
```
```

---

## 12. 結論

### 12.1 最優先検証項目

1. **LLMの影響**: Swallow 8B vs Gemma2 27Bの直接比較
   - naturalness差の原因特定
   - consistency差の原因特定

2. **プロンプト構造の影響**: レイヤリング vs シンプル構造
   - キャラクター一貫性への寄与度
   - Few-shot例の最適数

### 12.2 検証後のPhase 1設計への反映

検証結果に基づき、以下を決定する:

| 決定事項 | 選択肢 |
|----------|--------|
| 推奨LLM | Swallow 8B / Gemma2 27B / ハイブリッド |
| プロンプト構造 | レイヤリング / シンプル / ハイブリッド |
| RAG戦略 | 常時有効 / 条件付き / 無効 |
| Director戦略 | 常時有効 / 軽量版 / 無効 |

---

*作成: 2026-01-21*
*対象プロジェクト: duo-talk, duo-talk-simple, duo-talk-silly*
