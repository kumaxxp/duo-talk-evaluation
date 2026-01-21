# Phase 0: 評価基盤 - 状況レポート

**作成日**: 2026-01-21
**プロジェクト**: duo-talk-evaluation
**目的**: 既存3プロジェクトの定量評価

---

## 1. 評価概要

### 1.1 評価対象システム

| システム | アーキテクチャ | バックエンド | 特徴 |
|----------|---------------|-------------|------|
| duo-talk | UnifiedPipeline + Director + RAG | Ollama (Swallow 8B) | フル機能、品質重視 |
| duo-talk-simple | DuoDialogueManager + RAG | Ollama (Swallow 8B) | CLI特化、シンプル構成 |
| duo-talk-silly | 直接LLM呼び出し | KoboldCPP (Gemma2 27B) | 最小構成、高速 |

### 1.2 評価シナリオ

| シナリオ名 | 初期プロンプト | ターン数 | 評価観点 |
|-----------|---------------|---------|---------|
| casual_greeting | おはよう、二人とも | 5 | character_consistency, naturalness |
| topic_exploration | 最近のAI技術について話して | 8 | topic_novelty, concreteness |
| disagreement_resolution | 直感とデータ、どっちが大事？ | 10 | relationship_quality, naturalness |
| emotional_support | 最近疲れてるんだ... | 6 | relationship_quality, naturalness |

### 1.3 評価メトリクス

| メトリクス | 説明 | 範囲 |
|-----------|------|------|
| character_consistency | 一人称・口調・性格の一貫性 | 0.0-1.0 |
| topic_novelty | 話題の反復がないか | 0.0-1.0 |
| relationship_quality | 姉妹らしい掛け合い | 0.0-1.0 |
| naturalness | 会話のテンポと流れ | 0.0-1.0 |
| concreteness | 具体例・数値の有無 | 0.0-1.0 |

---

## 2. 評価結果

### 2.1 総合スコア比較

| システム | 平均スコア | 順位 |
|----------|-----------|------|
| **duo-talk** | **0.695** | 1位 |
| duo-talk-simple | 0.675 | 2位 |
| duo-talk-silly | 0.665 | 3位 |

### 2.2 シナリオ別スコア

| シナリオ | duo-talk | duo-talk-simple | duo-talk-silly |
|----------|----------|-----------------|----------------|
| casual_greeting | 0.680 | 0.700 | 0.600 |
| topic_exploration | 0.700 | 0.700 | 0.700 |
| disagreement_resolution | 0.700 | 0.700 | 0.700 |
| emotional_support | 0.700 | 0.600 | 0.660 |
| **平均** | **0.695** | **0.675** | **0.665** |

### 2.3 メトリクス別傾向

**duo-talk**:
- character_consistency: 0.800（安定）
- relationship_quality: 0.700-0.900（高品質）
- concreteness: 0.400-0.700（ばらつきあり）

**duo-talk-simple**:
- naturalness: 0.700-0.900（高品質）
- concreteness: 0.500-0.700（安定）

**duo-talk-silly**:
- naturalness: 0.900（最高）
- concreteness: 0.200-0.500（課題あり）

---

## 3. 定性的観察

### 3.1 duo-talk

**強み**:
- Director/NoveltyGuardによるループ検出・リトライが品質向上に寄与
- 話題の深掘り（WHY→HOW→DETAIL）の仕組みが機能
- RAGによる知識注入

**課題**:
- 処理時間が非常に長い（1シナリオ約2分）
- Fact Check有効時はさらに遅延
- JetRacerモード用の文脈が混入する問題（「マックス」「カーブ」等）

**観察されたログ例**:
```
🚨 NoveltyGuard: 軽度ループ検出 -> RETRY
🔄 RETRY (1/2): 【話題転換：別の視点へ】「論文」の話はループしています
```

### 3.2 duo-talk-simple

**強み**:
- シンプルな構成で高速動作
- JetRacer知識がRAGに組み込まれている
- コード理解が容易

**課題**:
- emotional_supportシナリオでスコア低下（0.600）
- 口調が攻撃的になる傾向（「！」多用）
- 発言が冗長になりがち

### 3.3 duo-talk-silly

**強み**:
- KoboldCPP直接呼び出しで最も高速
- naturalness（自然さ）が最高スコア（0.900）
- シンプルで予測可能

**課題**:
- casual_greetingのスコアが最低（0.600）
- 具体的情報が少ない（concreteness: 0.200）
- 一人称の不一致問題（やなが「あたし」を使用）

---

## 4. 技術的知見

### 4.1 メモリ制約

3システム同時実行は不可能。順次評価方式を採用。

| システム | バックエンド | メモリ要件 |
|----------|-------------|-----------|
| duo-talk-silly | KoboldCPP | ~16GB VRAM (Gemma2 27B) |
| duo-talk-simple | Ollama | ~5GB RAM (Swallow 8B) |
| duo-talk | Ollama | ~5GB RAM (Swallow 8B) |

### 4.2 評価器

LocalLLMEvaluator（KoboldCPP）を使用。
- Gemini APIは存在するがQuota制限あり
- ローカルLLM評価で十分な精度

### 4.3 アダプタ実装

| アダプタ | 接続方式 | 備考 |
|----------|---------|------|
| DuoTalkAdapter | ライブラリ直接呼び出し | Flaskサーバー不要に改修 |
| DuoTalkSimpleAdapter | ライブラリ直接呼び出し | 元から対応 |
| DuoTalkSillyAdapter | KoboldCPP API | HTTP経由 |

---

## 5. 結論と推奨

### 5.1 評価結果の解釈

1. **スコア差は僅差**（0.665-0.695、差は0.03）
2. **トレードオフが明確**:
   - duo-talk: 品質重視だが遅い
   - duo-talk-simple: バランス型
   - duo-talk-silly: 速度重視だが品質にばらつき

### 5.2 Phase 1への推奨

**オプション A: duo-talk-coreベースライン**
- duo-talk-simpleをベースに、不要機能を削除
- Director/NoveltyGuardの軽量版を検討

**オプション B: コンポーネント分離**
- Director、RAG、FactCheckを独立マイクロサービス化
- 必要に応じて組み合わせ可能な構成

**オプション C: 品質指標の再定義**
- 現在の5メトリクスでは差が出にくい
- より具体的な評価基準（一人称一貫性、話題展開力等）を追加

### 5.3 次のアクション

1. [ ] Phase 1設計書の作成
2. [ ] duo-talk-core骨格の実装
3. [ ] A/Bテスト用フレームワークの整備
4. [ ] 人間評価との相関検証

---

## 付録

### A. 評価実行コマンド

```bash
# 順次評価
python experiments/compare_single.py duo-talk-silly
python experiments/compare_single.py duo-talk-simple
python experiments/compare_single.py duo-talk

# 結果マージ
python experiments/compare_single.py --merge
```

### B. 結果ファイル

- `results/single_duo-talk_20260121_203135.json`
- `results/single_duo-talk-simple_20260121_184329.json`
- `results/single_duo-talk-silly_20260121_182313.json`
- `results/20260121_203146_merged_comparison.json`

### C. 評価環境

- **Server**: Ubuntu 22.04, RTX A5000 (24GB VRAM)
- **KoboldCPP**: Gemma-2-Llama-Swallow-27b-it-v0.1-Q4_K_M.gguf
- **Ollama**: Swallow 8B (Q4_K_M)
- **評価器**: LocalLLMEvaluator (KoboldCPP)

---

*このレポートはduo-talk-evaluation Phase 0の成果物です。*
