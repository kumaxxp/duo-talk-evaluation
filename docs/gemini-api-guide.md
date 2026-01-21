# Gemini API 運用ガイド

duo-talk-evaluation プロジェクトで Gemini API を使用する際の知見をまとめたドキュメント。

## 目次

1. [SDK情報](#sdk情報)
2. [利用可能なモデル](#利用可能なモデル)
3. [モデル選択戦略](#モデル選択戦略)
4. [Rate Limit対策](#rate-limit対策)
5. [課金について](#課金について)
6. [トラブルシューティング](#トラブルシューティング)

---

## SDK情報

### 使用SDK

```bash
pip install google-genai
```

**注意**: `google-generativeai`（旧SDK）とは異なる。インポート方法：

```python
from google import genai

client = genai.Client(api_key="YOUR_API_KEY")
```

### バージョン確認

```bash
pip show google-genai
```

現在使用中: `google-genai==1.59.0`

---

## 利用可能なモデル

### 2026年1月時点の主要モデル

#### Flash モデル（高速・低コスト）

| モデル名 | 特徴 | 推奨用途 |
|---------|------|---------|
| `gemini-2.5-flash` | **推奨** 安定・高速 | 日常的な評価、大量テスト |
| `gemini-2.5-flash-lite` | 超軽量 | 簡易チェック |
| `gemini-2.0-flash` | 旧版 | Rate Limit厳しい（非推奨） |
| `gemini-3-flash-preview` | 次世代プレビュー | 実験用 |

#### Pro モデル（高性能）

| モデル名 | 特徴 | 推奨用途 |
|---------|------|---------|
| `gemini-2.5-pro` | 高精度 | 詳細分析、ここぞという時 |
| `gemini-3-pro-preview` | 次世代プレビュー | 実験用 |

### モデル一覧の取得

```bash
python experiments/model_list.py
```

---

## モデル選択戦略

### 用途別推奨設定

```python
from evaluation.evaluator import DialogueEvaluator

# 1. 通常使用（デフォルト）- 高速・大量テスト向け
evaluator = DialogueEvaluator()  # gemini-2.5-flash

# 2. 高精度評価 - 詳細分析、問題の深掘り
evaluator = DialogueEvaluator(model_name="gemini-2.5-pro")

# 3. 次世代モデル実験
evaluator = DialogueEvaluator(model_name="gemini-3-flash-preview")
```

### 推奨ワークフロー

1. **初回評価**: `gemini-2.5-flash` で高速スクリーニング
2. **問題発見時**: `gemini-2.5-pro` で詳細分析
3. **定期的な実験**: `gemini-3-*-preview` で次世代モデルの性能確認

---

## Rate Limit対策

### 無料枠の制限（2026年1月時点）

| 項目 | 制限値 |
|------|--------|
| RPM (Requests Per Minute) | 15回/分 |
| RPD (Requests Per Day) | モデルにより異なる |
| TPM (Tokens Per Minute) | 100万トークン/分 |

### 重要な発見

- **モデルごとに独立したクォータ**
  - `gemini-2.0-flash` が枯渇しても `gemini-2.5-flash` は使える
  - バージョン違いで別カウンター

- **`limit: 0` の意味**
  - 「今日の分を使い切った」ではなく「そのモデルの無料枠が0」の可能性
  - 別モデルに切り替えて対処

### コードでの対策

```python
# evaluator.py に組み込み済みのリトライロジック
import time

max_retries = 3
for attempt in range(max_retries):
    try:
        metrics = evaluator.evaluate_conversation(conversation)
        if "評価失敗" not in str(metrics.issues):
            break
        if "429" in str(metrics.issues):
            wait_time = 10 * (attempt + 1)
            time.sleep(wait_time)
    except Exception as e:
        time.sleep(10 * (attempt + 1))
```

---

## 課金について

### Google AI Studio 課金プラン

[https://ai.google.dev/pricing](https://ai.google.dev/pricing)

### 課金のメリット

1. **Rate Limit緩和**: RPM/RPDが大幅増加
2. **安定性向上**: 429エラーの大幅減少
3. **高性能モデルへのアクセス**: Pro系の制限緩和

### 課金検討の目安

- 1日50回以上の評価を継続的に行う場合
- Rate Limitによる開発遅延が頻発する場合
- Proモデルを常用したい場合

### 料金目安（2026年1月時点）

| モデル | 入力 | 出力 |
|--------|------|------|
| gemini-2.5-flash | $0.075/100万トークン | $0.30/100万トークン |
| gemini-2.5-pro | $1.25/100万トークン | $5.00/100万トークン |

**試算**: 1回の評価 ≈ 2,000トークン
- Flash: 約$0.0006/回 → 1,000回で約$0.60
- Pro: 約$0.01/回 → 1,000回で約$10

---

## トラブルシューティング

### エラー別対処法

#### 404 NOT_FOUND

```
models/gemini-1.5-flash is not found for API version v1beta
```

**原因**: 存在しないモデル名を指定
**対処**: `experiments/model_list.py` で利用可能なモデルを確認

#### 429 RESOURCE_EXHAUSTED

```
Quota exceeded for metric: generate_content_free_tier_requests
```

**原因**: Rate Limit超過
**対処**:
1. 別モデルに切り替え（例: 2.0系 → 2.5系）
2. 待機してリトライ
3. 課金プランにアップグレード

#### API Key エラー

```
GEMINI_API_KEY must be set
```

**対処**:
```bash
export GEMINI_API_KEY="your-api-key"
```

### デバッグ用コマンド

```bash
# モデル一覧確認
python experiments/model_list.py

# 接続テスト
python experiments/quick_test.py

# 全テスト実行
python -m pytest tests/ -v
```

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-21 | 初版作成。gemini-2.5-flash での安定動作を確認 |
