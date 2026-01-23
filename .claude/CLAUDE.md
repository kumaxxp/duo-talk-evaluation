# duo-talk-evaluation Project

## Project Overview

AI姉妹キャラクター「やな」と「あゆ」の対話品質評価システム。
**実験ハブ (Experiment Hub)** として、duo-talk-ecosystemの各コンポーネントを統合的に評価・実験・知見蓄積を担当。

## Role Definition

```
┌─────────────────────────────────────────────────────────────┐
│                   duo-talk-evaluation                        │
│                   (実験ハブ / Experiment Hub)                │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Evaluator   │  │ Experiments │  │ Knowledge   │          │
│  │ (評価器)    │  │ (実験実行)  │  │ (知見蓄積)  │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │               │               │                    │
│         ▼               ▼               ▼                    │
│  - Gemini評価    - A/Bテスト     - specs/ (仕様書)          │
│  - Ollama評価    - 比較実験      - reports/ (レポート)       │
│  - 5軸スコア     - レポート生成  - 知見の集積               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ ライブラリとして利用
          ┌─────────────────────────────────────┐
          │  duo-talk-core / duo-talk-director  │
          │  (対話生成 / 品質制御)               │
          └─────────────────────────────────────┘
```

## Current State (2026-01-24)

- **Gemini API連携**: ✅ 正常動作（gemini-2.5-flash）
- **Ollama評価器**: ✅ 正常動作（gemma3:12b）
- **テスト**: ✅ 37/37 passed
- **Director A/Bテスト**: ✅ 標準化完了

## Directory Structure

```
duo-talk-evaluation/
├── .claude/
│   ├── CLAUDE.md           # このファイル
│   └── skills/             # カスタムスキル
│       ├── save-spec/      # 仕様書保存スキル
│       └── run-experiment/ # 実験実行スキル
│
├── specs/                  # 仕様書（知見蓄積）
│   ├── phases/             # フェーズ別仕様
│   ├── architecture/       # アーキテクチャ仕様
│   ├── experiments/        # 実験設計書
│   └── api/                # API仕様
│
├── reports/                # 実験レポート
│   └── archive/            # 過去レポート
│
├── templates/              # テンプレート
│   ├── EXPERIMENT_REPORT.md
│   └── SPECIFICATION.md
│
├── experiments/            # 実験スクリプト
│   ├── director_ab_test.py # Director A/Bテスト
│   ├── model_comparison.py # モデル比較
│   └── ...
│
├── results/                # 実験結果（生データ）
│   └── director_ab_{timestamp}/
│       ├── result.json
│       └── REPORT.md
│
├── src/evaluation/         # 評価ライブラリ
│   ├── metrics.py
│   ├── evaluator.py
│   ├── local_evaluator.py
│   ├── ollama_evaluator.py
│   └── adapters/
│
└── tests/                  # テスト
```

## Available Skills

### /save-spec

Geminiなどから取得した情報を仕様書として保存。

```
使用例:
ユーザー: これはGeminiから取得したOllama APIの情報です [コピペ]
Claude: /save-spec を実行 → specs/api/API_OLLAMA.md に保存
```

### /review-spec

保存した仕様を現行システムと比較し、実装可否・影響範囲を検討。

```
フロー:
1. 新仕様と現行仕様の差分分析
2. 影響範囲の特定
3. 変更カテゴリ判定（A:追加 / B:軽微 / C:大規模 / D:システム変更）
4. Gemini情報の妥当性検証
5. ユーザー確認（採用/修正/保留/却下）
6. 仕様確定 → docs/に移行
7. TDDワークフローで実装開始
```

### /run-experiment

標準化された実験を実行し、定型フォーマットでレポート生成。

```
使用例:
ユーザー: Director A/Bテストを実行して
Claude: /run-experiment director-ab → results/director_ab_{timestamp}/ に保存
```

## Experiment Standards

### 固定パラメータ

| パラメータ | 値 | 理由 |
|-----------|-----|------|
| Temperature | 0.7 | 創造性と一貫性のバランス |
| max_tokens | 300 | 応答長の標準化 |
| max_retries | 3 | Director再試行回数 |
| runs_per_scenario | 2 | 統計的信頼性 |

### 標準シナリオセット

| シナリオ | プロンプト | ターン数 | 評価観点 |
|----------|----------|---------|----------|
| casual_greeting | おはよう、二人とも | 5 | character_consistency, naturalness |
| topic_exploration | 最近のAI技術について話して | 6 | topic_novelty, concreteness |
| emotional_support | 最近疲れてるんだ... | 5 | relationship_quality, naturalness |

### レポート必須セクション

1. **実験諸元** - 表形式で全パラメータ記載
2. **使用プロンプト** - システムプロンプト完全版
3. **条件比較サマリー** - 定量的な比較表
4. **全会話サンプル** - Thought/Output分離、不採用応答含む
5. **分析と考察** - 定量・定性評価
6. **結論** - 1文で結論

## Microservices Architecture

```
duo-talk-ecosystem/
│
├── duo-talk-evaluation/     # 実験ハブ ← このリポジトリ
│   └── 評価・実験・知見蓄積
│
├── duo-talk-core/           # Phase 1 ✅
│   └── 対話生成エンジン
│
├── duo-talk-director/       # Phase 2 ✅
│   └── 品質制御
│
├── duo-talk-rag/            # Phase 3 🔲
│   └── RAG統合
│
├── duo-talk-gui/            # Phase 4 🔲
│   └── 可視化
│
└── duo-talk-integration/    # Phase 5 🔲
    └── 統合版
```

## Tech Stack

- **Language**: Python 3.11
- **Environment**: conda (duo-talk)
- **Testing**: pytest
- **Evaluation**:
  - google-genai SDK (gemini-2.5-flash)
  - Ollama API (gemma3:12b)
- **Components** (ライブラリとして利用):
  - duo-talk-core
  - duo-talk-director

## Git管理方針

### コミットルール

1. **コミットメッセージは日本語で記述**
2. Conventional Commits形式:
   - `feat:` 新機能
   - `fix:` バグ修正
   - `experiment:` 実験追加/結果
   - `docs:` ドキュメント
   - `spec:` 仕様書追加

### ブランチ戦略

- `main`: 安定版
- `experiment/{name}`: 実験ブランチ

## Quick Commands

```bash
# テスト実行
python -m pytest tests/ -v

# Director A/Bテスト
python experiments/director_ab_test.py --runs 2

# 評価器テスト
python experiments/quick_test.py
```

## Character Settings

**やな（姉）**
- 一人称: 私
- 性格: 直感的、行動派、妹思い
- 口調: 明るく柔らかい、「～」「よ」「ね」多用

**あゆ（妹）**
- 一人称: 私
- 性格: 分析的、慎重、姉には辛辣
- 口調: 丁寧語だが毒がある、姉を「姉様」と呼ぶ

## Evaluation Metrics

1. **character_consistency** (0.0-1.0): キャラクター一貫性
2. **topic_novelty** (0.0-1.0): 話題の新規性
3. **relationship_quality** (0.0-1.0): 姉妹関係の表現
4. **naturalness** (0.0-1.0): 会話の自然さ
5. **concreteness** (0.0-1.0): 情報の具体性

## Instructions for Claude

### 基本ルール
1. **実験はスキルで実行**: `/run-experiment` を使用
2. **仕様書はスキルで保存**: `/save-spec` を使用
3. **レポートは定型フォーマット**: templates/ を参照
4. **知見は蓄積**: specs/ と reports/ に整理
5. **TDDアプローチ**: テスト先行で実装

### 仕様検討ワークフロー

```
Gemini情報取得 → /save-spec → /review-spec → ユーザー確認 → 実装開始
```

1. **情報収集**: Geminiなどから情報取得
2. **仕様保存**: `/save-spec` で specs/ に保存
3. **仕様レビュー**: `/review-spec` で現行との比較・妥当性検証
4. **ユーザー確認**: 採用/修正/保留/却下を選択
5. **仕様確定**: 承認されたら docs/ に移行
6. **実装開始**: `/tdd` でTDDワークフロー開始

### Gemini情報の取り扱い

- **鵜呑みにしない**: 必ず現行コードと照合
- **矛盾を指摘**: 不整合があれば明示
- **影響範囲を保守的に見積もる**: 隠れた依存関係に注意

---

*Last Updated: 2026-01-24*
