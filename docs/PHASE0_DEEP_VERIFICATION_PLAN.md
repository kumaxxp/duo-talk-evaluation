# Phase 0 深掘り検証計画 - 実装ドキュメント

**作成日**: 2026-01-21
**更新日**: 2026-01-21
**基準文書**: [duo-talk-verification-plan.md](./duo-talk-verification-plan.md)
**目的**: Phase 0評価結果の因果関係を特定し、Phase 1設計の根拠を確立

---

## 0. 更新履歴

### 2026-01-21 更新
- **LLM設定の修正**: duo-talk/duo-talk-simpleは Gemma3-12b (Ollama) を使用
- **キャラクター設定の強化**: duo-talk準拠の設定に更新
  - あゆは「姉様」と呼ぶ（「お姉ちゃん」ではない）
  - あゆは敬語ベース（「〜ですね」「〜かもしれません」）
  - やなはカジュアル（「〜じゃん」「〜でしょ」）

---

## 1. 検証の背景

### 1.1 Phase 0評価結果サマリー

| システム | 平均スコア | 処理時間 | LLM | 主な特徴 |
|----------|-----------|----------|-----|----------|
| duo-talk | 0.695 | 約2分 | Gemma3-12b (Ollama) | Director/NoveltyGuard、フル機能 |
| duo-talk-simple | 0.675 | 中速 | Gemma3-12b (Ollama) | シンプル構造、RAGあり |
| duo-talk-silly | 0.665 | 最速 | Gemma2-27B (KoboldCPP) | 最小構成、高速 |

### 1.2 未解決の因果関係

現状では以下が不明確:

1. **naturalness差** (duo-talk-silly: 0.900 vs 他: 0.700-0.750)
   - Gemma2 27Bの能力によるものか？
   - シンプルなプロンプト構造によるものか？
   - RAGがないため余計な情報が混入しないからか？

2. **concreteness差** (duo-talk: 0.625 vs duo-talk-silly: 0.200)
   - RAGの効果か？
   - モデルサイズの影響か？

3. **処理時間差** (duo-talk: 2分 vs duo-talk-silly: 最速)
   - Director/NoveltyGuardの影響か？
   - モデルサイズの影響か？

---

## 2. 検証戦略

### 2.1 変数隔離アプローチ

**原則**: 1回の実験で1変数のみを変更し、因果関係を特定する

```
実験1: LLM比較（他の変数固定）
  - Gemma3 12B vs Gemma2 27B
  - 同一プロンプト構造（シンプル）
  - RAG: 無効
  - Director: 無効

実験2: プロンプト構造比較（LLM固定）
  - レイヤリング vs シンプル vs SillyTavern
  - LLM: Gemma3 12B（固定）
  - RAG: 無効
  - Director: 無効

実験3: RAG影響（他の変数固定）
  - RAGあり vs なし
  - LLM: Gemma3 12B（固定）
  - プロンプト: シンプル（固定）

実験4: Director影響（他の変数固定）
  - Directorあり vs なし
  - LLM: Gemma3 12B（固定）
  - プロンプト: duo-talk形式（固定）
```

### 2.2 優先順位

| 優先度 | 検証軸 | 理由 | 推定工数 |
|--------|--------|------|----------|
| **1** | LLM比較 | 最大の変数、結果が他の検証に影響 | 1日 |
| **2** | プロンプト構造 | 設計変更で対応可能、即効性あり | 1日 |
| 3 | RAG影響 | concreteness向上の検証 | 0.5日 |
| 4 | Director影響 | 処理時間と品質のトレードオフ | 0.5日 |

---

## 3. 実装計画

### 3.1 A/Bテストフレームワーク

#### 3.1.1 アーキテクチャ

```
experiments/
├── ab_test/
│   ├── __init__.py
│   ├── runner.py          # A/Bテスト実行エンジン
│   ├── config.py          # 実験設定定義
│   ├── variations.py      # 変数バリエーション定義
│   └── report.py          # レポート生成
├── configs/
│   ├── llm_comparison.yaml       # 実験1設定
│   ├── prompt_comparison.yaml    # 実験2設定
│   ├── rag_comparison.yaml       # 実験3設定
│   └── director_comparison.yaml  # 実験4設定
└── run_ab_test.py         # エントリポイント
```

#### 3.1.2 コア機能

```python
# experiments/ab_test/runner.py
class ABTestRunner:
    """A/Bテスト実行エンジン"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)

    def run_experiment(self) -> ExperimentResult:
        """実験を実行"""
        results = []
        for variation in self.config.variations:
            adapter = self._create_adapter(variation)
            for scenario in self.config.scenarios:
                result = self._run_scenario(adapter, scenario)
                results.append(result)
        return self._aggregate_results(results)

    def _create_adapter(self, variation: VariationConfig) -> SystemAdapter:
        """変数設定に基づいてアダプタを作成"""
        # LLMバックエンドの選択
        # プロンプト構造の選択
        # RAG/Directorの有効/無効
```

#### 3.1.3 設定ファイル形式

```yaml
# experiments/configs/llm_comparison.yaml
experiment:
  id: "exp_llm_comparison_001"
  name: "LLM比較: Gemma3 12B vs Gemma2 27B"
  description: "同一プロンプトでLLMのみを変更し、品質差を検証"

base_config:
  prompt_structure: "simple"  # シンプル構造で固定
  rag_enabled: false
  director_enabled: false
  scenarios:
    - casual_greeting
    - emotional_support
    - topic_exploration

variations:
  - name: "swallow_8b"
    llm_backend: "ollama"
    llm_model: "swallow-8b"

  - name: "gemma2_27b"
    llm_backend: "koboldcpp"
    llm_model: "gemma2-27b"

metrics:
  - naturalness
  - character_consistency
  - concreteness
  - relationship_quality
  - topic_novelty

analysis:
  statistical_significance: true
  confidence_level: 0.95
```

### 3.2 検証軸1: LLM比較

#### 3.2.1 実験設計

```yaml
# 実験1-A: Gemma3 12B vs Gemma2 27B
conditions:
  prompt_structure: "simple"  # duo-talk-simpleのシンプル構造
  rag_enabled: false
  director_enabled: false
  few_shot_count: 3

variations:
  - name: "swallow_8b_ollama"
    backend: "ollama"
    model: "hf.co/mmnga/tokyotech-llm-Llama-3.1-Swallow-8B-Instruct-v0.3-gguf:Q4_K_M"

  - name: "gemma2_27b_koboldcpp"
    backend: "koboldcpp"
    model: "Gemma-2-Llama-Swallow-27b-it-v0.1-Q4_K_M"

scenarios:
  - name: casual_greeting
    prompt: "おはよう、二人とも"
    turns: 5
  - name: emotional_support
    prompt: "最近疲れてるんだ..."
    turns: 6
  - name: topic_exploration
    prompt: "最近のAI技術について話して"
    turns: 8
```

#### 3.2.2 必要な実装

1. **ConfigurableAdapter**: 変数を切り替え可能なアダプタ
   - LLMバックエンドの動的切り替え
   - プロンプト構造の選択
   - RAG/Directorのフラグ制御

2. **プロンプト構造の抽出**:
   - duo-talk-simpleのシンプル構造をテンプレート化
   - duo-talk-sillyのSillyTavern形式をテンプレート化

### 3.3 検証軸2: プロンプト構造比較

#### 3.3.1 プロンプト構造の定義

**構造A: レイヤリング (duo-talk方式)**
```python
LAYERED_PROMPT_TEMPLATE = """
<System Prompt is="Sister AI Duo">
<Absolute Command>
{absolute_commands}
</Absolute Command>

<Deep Consciousness>
{deep_consciousness}
</Deep Consciousness>

<Surface Consciousness>
{character_settings}
</Surface Consciousness>
</System Prompt>
"""
```

**構造B: シンプル構造 (duo-talk-simple方式)**
```python
SIMPLE_PROMPT_TEMPLATE = """
あなたは{character_name}。{summary}
信念: 「{core_belief}」

【関係性】
{relationship}

★★★ {max_sentences}文以内で返答 ★★★

【会話構造ルール】
{conversation_rules}

【キャラクター専用ルール】
{character_constraints}

[今の状態] {state}

[返答例]
{few_shot_examples}
"""
```

**構造C: SillyTavern形式 (duo-talk-silly方式)**
```python
SILLYTAVERN_PROMPT_TEMPLATE = """
{system_prompt}

# キャラクター設定
- 名前: {name}
- 一人称: {first_person}
- 性格: {personality}
- 口調: {speech_pattern}

# 話し方の例
{examples}
"""
```

#### 3.3.2 実験設計

```yaml
# 実験2-A: プロンプト構造の比較
conditions:
  llm_backend: "ollama"
  llm_model: "swallow-8b"
  rag_enabled: false
  director_enabled: false

variations:
  - name: "layered"
    prompt_structure: "layered"

  - name: "simple"
    prompt_structure: "simple"

  - name: "sillytavern"
    prompt_structure: "sillytavern"
```

### 3.4 検証軸3: RAG影響

#### 3.4.1 実験設計

```yaml
# 実験3-A: RAGの有無比較
conditions:
  llm_backend: "ollama"
  llm_model: "swallow-8b"
  prompt_structure: "simple"
  director_enabled: false

variations:
  - name: "rag_disabled"
    rag_enabled: false

  - name: "rag_enabled"
    rag_enabled: true
    rag_top_k: 3
```

### 3.5 検証軸4: Director影響

#### 3.5.1 実験設計

```yaml
# 実験4-A: Directorの有無比較
conditions:
  llm_backend: "ollama"
  llm_model: "swallow-8b"
  prompt_structure: "layered"  # duo-talk形式
  rag_enabled: true

variations:
  - name: "director_disabled"
    director_enabled: false

  - name: "director_enabled"
    director_enabled: true
    novelty_guard_enabled: true
    max_retries: 3
```

---

## 4. 実装タスク

### 4.1 Phase 1: A/Bテスト基盤 (優先度: 最高)

| タスク | 詳細 | 推定工数 |
|--------|------|----------|
| ConfigurableAdapter作成 | 変数切り替え可能なアダプタ | 2h |
| プロンプトテンプレート抽出 | 3種類の構造をテンプレート化 | 2h |
| ABTestRunner実装 | 実験実行エンジン | 3h |
| 設定ファイル形式定義 | YAML設定の構造定義 | 1h |
| レポート生成 | 比較レポートの自動生成 | 2h |

### 4.2 Phase 2: 検証軸1実行 (LLM比較)

| タスク | 詳細 | 推定工数 |
|--------|------|----------|
| llm_comparison.yaml作成 | 実験設定ファイル | 0.5h |
| 実験実行 | 3シナリオ x 2バリエーション | 1h |
| 結果分析 | メトリクス比較、統計分析 | 1h |
| レポート作成 | LLM比較レポート | 0.5h |

### 4.3 Phase 3: 検証軸2実行 (プロンプト構造)

| タスク | 詳細 | 推定工数 |
|--------|------|----------|
| prompt_comparison.yaml作成 | 実験設定ファイル | 0.5h |
| 実験実行 | 3シナリオ x 3バリエーション | 1.5h |
| 結果分析 | メトリクス比較 | 1h |
| レポート作成 | プロンプト構造比較レポート | 0.5h |

### 4.4 Phase 4: 検証軸3-4実行 (RAG/Director)

| タスク | 詳細 | 推定工数 |
|--------|------|----------|
| rag_comparison.yaml作成 | 実験設定ファイル | 0.5h |
| director_comparison.yaml作成 | 実験設定ファイル | 0.5h |
| 実験実行 | 合計4バリエーション | 1h |
| 結果分析 | メトリクス比較 | 1h |
| 統合レポート作成 | 全検証軸の統合分析 | 1h |

---

## 5. 成果物

### 5.1 コード成果物

```
experiments/
├── ab_test/
│   ├── __init__.py
│   ├── runner.py
│   ├── config.py
│   ├── variations.py
│   ├── adapters/
│   │   └── configurable_adapter.py
│   └── prompts/
│       ├── layered.py
│       ├── simple.py
│       └── sillytavern.py
├── configs/
│   ├── llm_comparison.yaml
│   ├── prompt_comparison.yaml
│   ├── rag_comparison.yaml
│   └── director_comparison.yaml
└── run_ab_test.py
```

### 5.2 レポート成果物

```
results/
├── exp_llm_comparison_001/
│   ├── raw_results.json
│   ├── metrics_comparison.json
│   └── REPORT.md
├── exp_prompt_comparison_001/
│   └── ...
├── exp_rag_comparison_001/
│   └── ...
├── exp_director_comparison_001/
│   └── ...
└── DEEP_VERIFICATION_SUMMARY.md  # 統合分析レポート
```

---

## 6. 期待される知見とPhase 1への示唆

### 6.1 LLM比較の結果パターン

| 結果パターン | 解釈 | Phase 1への示唆 |
|--------------|------|-----------------|
| Gemma2 27B >> Gemma3 12B | モデルサイズが支配的 | 大型モデル推奨 |
| Gemma3 12B > Gemma2 27B (consistency) | 日本語特化が有効 | 日本語特化モデル優先 |
| 差が僅少 | プロンプト設計が重要 | LLMより設計に注力 |

### 6.2 プロンプト構造の結果パターン

| 結果パターン | 解釈 | Phase 1への示唆 |
|--------------|------|-----------------|
| レイヤリング > シンプル | 階層構造が有効 | レイヤリング採用 |
| シンプル > レイヤリング | シンプルさが重要 | 過剰設計を避ける |
| SillyTavern ≈ シンプル | フォーマット差は小さい | 任意の形式でOK |

### 6.3 RAGの結果パターン

| 結果パターン | 解釈 | Phase 1への示唆 |
|--------------|------|-----------------|
| RAGあり >> なし (concreteness) | 知識注入が有効 | RAG必須 |
| RAGあり = なし | 現行RAGが非効率 | RAG改善or削除 |
| RAGあり < なし (relevance) | 文脈混入問題 | RAG選択的使用 |

### 6.4 Directorの結果パターン

| 結果パターン | 解釈 | Phase 1への示唆 |
|--------------|------|-----------------|
| Directorあり > なし (品質) | 品質制御が有効 | Director維持 |
| 差が僅少 | コストに見合わない | Director軽量化or削除 |
| 処理時間が大幅増加 | トレードオフ明確 | 軽量版Director検討 |

---

## 7. 次のアクション

1. [ ] A/Bテストフレームワークの実装開始
2. [ ] ConfigurableAdapterの作成
3. [ ] プロンプトテンプレートの抽出
4. [ ] 検証軸1（LLM比較）の実行
5. [ ] 結果分析とレポート作成

---

*このドキュメントはPhase 0評価結果に基づく深掘り検証の実装計画です。*
