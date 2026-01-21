# duo-talk-evaluation Project

## Project Overview
AI姉妹キャラクター「やな」と「あゆ」の対話品質評価システム。
**Phase 0: 評価基盤** として、既存3プロジェクトの定量評価を担当。

## Current State (2026-01-21)
- **Gemini API連携**: ✅ 正常動作（gemini-2.5-flash）
- **ローカルLLM評価器**: ✅ LocalLLMEvaluator実装済み
- **テスト**: ✅ 37/37 passed
- **SystemAdapter**: ✅ 3アダプタ実装完了
- **3プロジェクト比較**: ✅ compare_systems.py完成

## Microservices Architecture

```
duo-talk-ecosystem/
│
├── duo-talk-evaluation/     # Phase 0 ← 現在ここ（実装完了）
│   └── 既存3プロジェクトの定量評価
│
├── duo-talk-core/           # Phase 1
│   └── 純粋な対話性能のベースライン
│
├── duo-talk-director/       # Phase 2
│   └── Director有無での性能差測定
│
├── duo-talk-rag/            # Phase 3
│   └── RAG有無での性能差測定
│
├── duo-talk-gui/            # Phase 4 (低優先)
│   └── 結果可視化とデモ
│
└── duo-talk-integration/    # Phase 5
    └── 最適構成の統合版
```

## Phase 0: 評価基盤（実装完了）

### 進捗状況
| タスク | 状態 |
|--------|------|
| LocalLLMEvaluator実装 | ✅ 完了 |
| Gemini評価器実装 | ✅ 完了 |
| テスト整備 | ✅ 37/37 passed |
| SystemAdapter実装 | ✅ 完了（3アダプタ） |
| compare_systems.py | ✅ 完了 |
| 比較実験実行 | 🔲 未実行（サービス起動が必要） |
| レポート生成 | 🔲 比較実験後 |

### 成功基準
- [x] SystemAdapter実装（3プロジェクト対応）
- [ ] 3プロジェクトで同一シナリオ実行
- [ ] 5つのメトリクスで定量評価
- [ ] スコア差の統計的有意性確認
- [ ] 「なぜduo-talkが良いのか」の仮説3つ以上

## Tech Stack
- **Language**: Python 3.11
- **Environment**: conda (duo-talk)
- **Testing**: pytest
- **APIs**:
  - google-genai SDK (gemini-2.5-flash)
  - KoboldCPP API (http://localhost:5001)

## Architecture
```
duo-talk-evaluation/
├── src/evaluation/
│   ├── metrics.py              # メトリクス定義 ✅
│   ├── evaluator.py            # Gemini評価器 ✅
│   ├── local_evaluator.py      # ローカルLLM評価器 ✅
│   └── adapters/               # 各プロジェクトへの接続
│       ├── types.py            # 共通型定義 ✅
│       ├── base.py             # SystemAdapter基底クラス ✅
│       ├── duo_talk_adapter.py # duo-talk接続（HTTP API） ✅
│       ├── duo_talk_simple_adapter.py # ライブラリインポート ✅
│       └── duo_talk_silly_adapter.py  # KoboldCPP直接 ✅
├── tests/
│   ├── test_evaluator.py       # 評価器テスト ✅
│   └── test_adapters.py        # アダプタテスト ✅
├── experiments/
│   ├── quick_test.py           # 動作確認 ✅
│   ├── model_list.py           # モデル一覧 ✅
│   └── compare_systems.py      # 3プロジェクト比較 ✅
├── docs/
│   ├── gemini-api-guide.md     # API運用ガイド ✅
│   └── duo-talkマイクロサービス化詳細設計書.md ✅
└── results/                     # 実験結果保存先
```

## SystemAdapter Implementation

### 接続方式
| アダプタ | システム | 接続方式 | ステータス |
|----------|----------|----------|------------|
| DuoTalkAdapter | duo-talk | HTTP API `/api/unified/run/start-sync` | ✅ |
| DuoTalkSimpleAdapter | duo-talk-simple | ライブラリインポート | ✅ |
| DuoTalkSillyAdapter | duo-talk-silly | KoboldCPP API直接呼び出し | ✅ |

### 使用例
```python
from evaluation.adapters import (
    DuoTalkAdapter,
    DuoTalkSimpleAdapter,
    DuoTalkSillyAdapter,
    EvaluationScenario,
)

# アダプタ初期化
duo_talk = DuoTalkAdapter()
duo_simple = DuoTalkSimpleAdapter()
duo_silly = DuoTalkSillyAdapter()

# 利用可能性チェック
if duo_talk.is_available():
    result = duo_talk.generate_dialogue("おはよう", turns=5)
    print(result.to_standard_format())

# シナリオ実行
scenario = EvaluationScenario(
    name="casual_greeting",
    initial_prompt="おはよう、二人とも",
    turns=5
)
result = duo_talk.run_scenario(scenario)
```

## Character Settings
**やな（姉 / Edge AI）**
- 一人称: 私
- 性格: 直感的、行動派、妹思い
- 口調: 「〜わ」「〜かしら」「〜ね」

**あゆ（妹 / Cloud AI）**
- 一人称: あたし
- 性格: 分析的、慎重、理論派
- 口調: 「〜だよ」「〜じゃん」「〜かな？」

## Evaluation Metrics
1. **character_consistency** (0.0-1.0): 一人称・口調・性格の一貫性
2. **topic_novelty** (0.0-1.0): 話題の反復がないか
3. **relationship_quality** (0.0-1.0): 姉妹らしい掛け合い
4. **naturalness** (0.0-1.0): 会話のテンポと流れ
5. **concreteness** (0.0-1.0): 具体例・数値の有無

## Evaluation Scenarios
```yaml
scenarios:
  - name: "casual_greeting"
    initial_prompt: "おはよう、二人とも"
    turns: 5
    評価観点: character_consistency, naturalness

  - name: "topic_exploration"
    initial_prompt: "最近のAI技術について話して"
    turns: 8
    評価観点: topic_novelty, concreteness

  - name: "disagreement_resolution"
    initial_prompt: "直感とデータ、どっちが大事？"
    turns: 10
    評価観点: relationship_quality, naturalness

  - name: "emotional_support"
    initial_prompt: "最近疲れてるんだ..."
    turns: 6
    評価観点: relationship_quality, naturalness
```

## Sequential Comparison Workflow (メモリ制約対応)

**重要**: 3システム同時実行はメモリ不足で不可能。1システムずつ評価を実行。

### 実行手順
```bash
# Step 1: KoboldCPP起動中に実行
python experiments/compare_single.py duo-talk-silly

# Step 2: KoboldCPP停止 → Ollama起動（Swallow 8B推奨）
python experiments/compare_single.py duo-talk-simple

# Step 3: Ollama停止 → duo-talk Flask起動（軽量モデル設定必須）
python experiments/compare_single.py duo-talk --port 5002

# Step 4: 結果マージ
python experiments/compare_single.py --merge
```

### メモリ要件
| システム | バックエンド | メモリ要件 |
|----------|-------------|-----------|
| duo-talk-silly | KoboldCPP | ~16GB VRAM (Gemma2 27B) |
| duo-talk-simple | Ollama | ~5GB RAM (Swallow 8B) |
| duo-talk | Ollama (Flask経由) | ~16GB RAM (gemma3:27b) |

### 出力ファイル
- `results/single_<system>_<timestamp>.json` - 個別結果
- `results/<timestamp>_merged_comparison.json` - マージ済み比較結果

## Next Steps (優先順)
1. **順次比較実験** - `compare_single.py`で1システムずつ評価
2. **結果マージ** - `compare_single.py --merge`で統合
3. **Phase 1移行判断** - 結果に基づき決定

## Environment Details
- **Server**: Ubuntu 22.04, RTX A5000 (24GB VRAM)
- **Working Dir**: `/home/owner/work/duo-talk-ecosystem/duo-talk-evaluation`
- **KoboldCPP**: http://localhost:5001
- **Model**: Gemma-2-Llama-Swallow-27b-it-v0.1-Q4_K_M.gguf

## Quick Commands
```bash
# 評価テスト
python experiments/quick_test.py

# モデル一覧
python experiments/model_list.py

# 全テスト実行
python -m pytest tests/ -v

# 単一システム評価（推奨）
python experiments/compare_single.py duo-talk-silly
python experiments/compare_single.py duo-talk-simple
python experiments/compare_single.py duo-talk --port 5002

# 結果マージ
python experiments/compare_single.py --merge

# 3システム同時比較（非推奨：メモリ不足）
# python experiments/compare_systems.py
```

## Resolved Issues
### Gemini API接続エラー (解決済み)
**原因**: `gemini-1.5-flash`は存在しないモデル名
**解決**: `gemini-2.5-flash`に変更

### API Quota超過 (解決済み)
**原因**: モデルごとに独立したクォータ
**解決**: `gemini-2.5-flash`に切り替え、リトライロジック実装

## Commands Available
- `/plan`: プロジェクト設計
- `/tdd`: テスト駆動実装
- `/build-fix`: ビルドエラー修正
- `/code-review`: コードレビュー

---

## Instructions for Claude
1. **比較実験の実行** - サービス起動が必要
2. **TDDアプローチ** - テスト先行で実装
3. **設計書参照** - `docs/duo-talkマイクロサービス化詳細設計書.md`
4. **結果に基づく判断** - 予断を持たず、測定結果で次を決める

Follow the patterns in `.claude/rules/` and use Gemini API guide in `docs/`.

---

## 実験レポート記載要件

実験レポート（`results/*.md`）を作成する際は、以下の情報を必ず含めること。

### 必須セクション

#### 1. 実験諸元（各実験ごとに表形式で記載）
| 項目 | 記載内容 |
|------|---------|
| バックエンド | Ollama / KoboldCPP / その他 |
| LLM | モデル名とサイズ（例: gemma3:12b） |
| プロンプト構造 | Layered / Simple / SillyTavern / その他 |
| 対応リポジトリ | どのリポジトリを模倣・再現しているか |
| 固定変数 | 変数隔離のために固定した設定 |

#### 2. プロンプトテンプレート
- 各プロンプト構造の実際のテンプレート例を掲載
- 少なくとも1キャラクター分（やな or あゆ）のサンプルを含める

#### 3. 共通設定
| 項目 | 例 |
|------|-----|
| RAG | 有効/無効 |
| Director | 有効/無効 |
| Few-shot数 | 数値 |
| Temperature | 数値 |
| max_tokens | 数値 |

#### 4. 実験の限界
- 変数隔離により実際のシステム構成とは異なる点
- プロンプト構造が模倣版である点
- API制限やその他の制約

#### 5. 全会話サンプル
- 実験で生成されたすべての対話サンプルを掲載
- 各サンプルにスコアと簡単なコメントを付記

### レポート例
`results/PHASE0_FINAL_REPORT.md` を参照のこと。
