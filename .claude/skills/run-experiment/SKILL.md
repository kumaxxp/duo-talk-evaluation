---
name: run-experiment
description: 標準化された実験を実行し、定型フォーマットでレポートを生成する。A/Bテスト、比較実験などを一貫した方法で実施。
---

# 標準化実験実行スキル

duo-talk-ecosystemの各コンポーネントを評価する実験を、一貫したフォーマットで実行します。

## 使用タイミング

- A/Bテスト実験を実行する時
- Director有無の比較実験
- モデル比較実験
- `/run-experiment` コマンド実行時

## 実験タイプ

### 1. Director A/Bテスト

```bash
python experiments/director_ab_test.py --runs 2 --output results
```

**出力**: `results/director_ab_{timestamp}/`

### 2. モデル比較

```bash
python experiments/model_comparison.py --models "gemma3:12b,gemma3:27b"
```

### 3. プロンプト構造比較

```bash
python experiments/prompt_comparison.py --structures "layered,simple"
```

## 実験パラメータ（固定）

すべての実験で以下を固定:

| パラメータ | 値 | 理由 |
|-----------|-----|------|
| Temperature | 0.7 | 創造性と一貫性のバランス |
| max_tokens | 300 | 応答長の標準化 |
| max_retries | 3 | Director再試行回数 |
| runs_per_scenario | 2 | 統計的信頼性 |

## シナリオセット（固定）

```python
STANDARD_SCENARIOS = [
    {
        "name": "casual_greeting",
        "initial_prompt": "おはよう、二人とも",
        "turns": 5,
        "focus": ["character_consistency", "naturalness"]
    },
    {
        "name": "topic_exploration",
        "initial_prompt": "最近のAI技術について話して",
        "turns": 6,
        "focus": ["topic_novelty", "concreteness"]
    },
    {
        "name": "emotional_support",
        "initial_prompt": "最近疲れてるんだ...",
        "turns": 5,
        "focus": ["relationship_quality", "naturalness"]
    },
]
```

## 実行フロー

### Step 1: 事前確認

```
✓ バックエンド確認 (Ollama起動中)
✓ モデル確認 (gemma3:12b ロード済み)
✓ 評価器確認 (Ollama Evaluator 利用可能)
```

### Step 2: 実験実行

```
============================================================
Director A/B Test
============================================================

--- Scenario: casual_greeting ---
  Run 1/2
    [A] Without Director... OK (18.8s, score=0.50)
    [B] With Director... OK (16.1s, score=0.60)
  Run 2/2
    ...
```

### Step 3: 結果保存

```
results/
└── director_ab_{timestamp}/
    ├── result.json      # 生データ
    └── REPORT.md        # 整形済みレポート
```

## レポートフォーマット（必須セクション）

### 1. 実験諸元（表形式）

| 項目 | 値 |
|------|-----|
| バックエンド | ollama |
| LLM | gemma3:12b |
| プロンプト構造 | Layered (v3.8.1) |
| RAG | 無効 |
| Director | 比較対象 |
| Temperature | 0.7 |
| max_tokens | 300 |

### 2. 使用プロンプト（完全版）

```markdown
### システムプロンプト（サンプル）
[完全なプロンプトを記載]

### ユーザープロンプト（シナリオ別）
| シナリオ | プロンプト | ターン数 |
```

### 3. 条件比較サマリー

| メトリクス | 条件A | 条件B | 差分 |
|------------|-------|-------|------|
| 成功数 | 6 | 6 | - |
| 平均リトライ数 | 0.00 | 0.50 | +0.50 |
| 平均スコア | 0.70 | 0.67 | -4.3% |

### 4. 全会話サンプル（詳細版）

各ターンについて:

```markdown
#### Turn N: {speaker}

**不採用応答:** (Director有効時のみ)
- **Attempt 1** ❌
  - Response: {不採用になった応答}
  - Status: `RETRY`
  - Checker: `tone_check`
  - Reason: {不採用理由}

**採用応答:** ✅
- **Thought**: {内省内容}
- **Output**: {発言内容}
- **リトライ回数**: N
```

### 5. 分析と考察

- 定量的結果のまとめ
- 定性的評価
- 観察された問題点

### 6. 結論

1文で結論を述べる。

## 完了報告フォーマット

```
============================================================
実験完了
============================================================

📊 実験タイプ: Director A/B Test
⏱️ 実行時間: 5分32秒
📁 結果保存先: results/director_ab_20260124_014743/

## サマリー

| 条件 | 平均スコア | 平均リトライ |
|------|----------|-------------|
| Director無し | 0.70 | 0回 |
| Director有り | 0.67 | 0.5回 |

## 主要な発見

1. {発見1}
2. {発見2}
3. {発見3}

📄 詳細レポート: results/director_ab_20260124_014743/REPORT.md
```

## トラブルシューティング

### バックエンドが起動していない

```bash
# Ollamaを起動
ollama serve

# モデルをロード
ollama run gemma3:12b
```

### メモリ不足

```
⚠️ メモリ不足の可能性があります
→ 軽量モデル (gemma3:4b) に切り替えてください
```

## ベストプラクティス

1. 実験前に `git status` で変更がないことを確認
2. 長時間実験は `tmux` 内で実行
3. 結果は即座にコミット
4. レポートは必ず確認してからマージ
