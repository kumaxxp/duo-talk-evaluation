# P-Next4 Topic A: Semantic Matcher 実験計画

**Branch**: `experiments/semantic_matcher`
**Created**: 2026-01-26
**Status**: 評価フェーズ（mainへの統合なし）

---

## 目的

**MISSING_OBJECT エラーを 5% から 1% 以下に低減する。**

現状、GM が応答で言及するオブジェクト名と、シナリオ定義内のオブジェクト名が
微妙に異なる場合（例: "コーヒー" vs "コーヒー豆"）、MISSING_OBJECT として検出される。

Semantic Matcher は、この名前不一致を解消し、正しいオブジェクトへの紐付けを
**候補提示** するシステムである。

---

## 非目標（No World Expansion 原則）

**World is Truth を崩さない。**

- ❌ 新しいオブジェクトを「捏造」しない
- ❌ シナリオ定義に存在しないオブジェクトを自動追加しない
- ❌ GM の応答を「正しい」として World を更新しない

Semantic Matcher は **既存 World 内のオブジェクト集合に対してのみ** マッチを行う。
存在しないオブジェクトへのマッチは常に「不一致」として報告する。

---

## 評価ハーネス

### 入力データソース

評価ハーネスは以下のログファイルからMISSING_OBJECTサンプルを抽出:

| ファイル | 抽出フィールド | 説明 |
|----------|----------------|------|
| `turns_log.json` | `invented_objects` | LLMが発明したオブジェクト名 |
| `turns_log.json` | `blocked_target_before/after` | GMにブロックされたターゲット |
| `turns_log.json` | `denied_reason == "MISSING_OBJECT"` | ハード拒否されたケース |
| `world_canonical.json` | `props` | 有効なオブジェクト一覧 |

### Ground Truth (GT) の決定方法

GTは以下のヒューリスティクスで自動推定:

1. **部分文字列マッチ**: クエリがワールドオブジェクトの部分文字列
   - 例: "カップ" → "マグカップ"
2. **resolved_target フィールド**: ターンログに解決済みターゲットがある場合
3. **marker_targets_after**: 事後マーカーターゲットに有効オブジェクトがある場合

**重要**: GTが推定できないサンプルは `excluded_samples` としてカウントし、
メトリクス計算からは除外する。

### 評価メトリクス

```
Recall (救出率)    = TP / Total Samples
Precision (精度)   = TP / (TP + FP)
FP Rate (誤提示率) = FP / Total Samples
F1 Score           = 2 * Precision * Recall / (Precision + Recall)
```

### Threshold Grid

| 閾値 | 用途 |
|------|------|
| 0.70 | 緩い閾値（Recall重視） |
| 0.75 | 中間 |
| 0.80 | バランス |
| 0.85 | 中間 |
| 0.90 | 厳しい閾値（Precision重視） |

**Best threshold は F1 Score で決定。**

### CLI 使用方法

```bash
# 最新のrun結果を評価
python -m experiments.semantic_matcher.eval --run results/gm_2x2_dev_*/

# カスタム閾値で評価
python -m experiments.semantic_matcher.eval --thresholds 0.7,0.8,0.9

# 出力先を指定
python -m experiments.semantic_matcher.eval --output results/my_eval/
```

### 出力ファイル

| ファイル | 内容 |
|----------|------|
| `summary.json` | 全メトリクスのJSON形式 |
| `summary.md` | マークダウンレポート |
| `samples.json` | 評価サンプル一覧 |
| `audit.jsonl` | 全マッチング操作のログ |

---

## 方式案

### 案 A: Fuzzy String Matching（rapidfuzz）✅ 採用

**概要**: 文字列の編集距離・類似度スコアに基づくマッチング。

**メリット**:
- 依存ライブラリが軽量（rapidfuzz のみ）
- 処理速度が高速
- 実装がシンプル
- 日本語でも動作

**デメリット**:
- 意味的な類似性を捉えられない（"椅子" と "座席" は低スコア）
- 閾値チューニングが必要

```python
from rapidfuzz import fuzz, process

def fuzzy_match(query: str, candidates: list[str], threshold: float = 0.7) -> list[MatchCandidate]:
    results = process.extract(query, candidates, scorer=fuzz.ratio, limit=5)
    return [
        MatchCandidate(name=name, score=score/100)
        for name, score, _ in results
        if score/100 >= threshold
    ]
```

### 案 B: Embedding + Vector Search（将来検討）

**概要**: テキストをベクトル化し、コサイン類似度で検索。

**実装優先度**: **低**（案Aで不足の場合に検討）

---

## ガードレール

### 1. Auto-Adopt 禁止（評価中）

```python
matcher = FuzzyMatcher(
    suggest_threshold=0.7,
    allow_auto_adopt=False,  # CRITICAL: 評価中は常にFalse
)
```

### 2. 一般名詞の除外

```python
GENERIC_NOUNS = {"床", "壁", "天井", "空気", "部屋", "場所"}
# これらは自動採用禁止
```

### 3. 監査ログ必須

全てのマッチング操作をJSONL形式で記録:

```json
{
  "timestamp": "2026-01-26T15:30:00Z",
  "input_query": "コーヒー",
  "world_objects": ["コーヒー豆", "コーヒーメーカー", "マグカップ"],
  "candidates": [
    {"name": "コーヒー豆", "score": 0.85, "method": "fuzzy"}
  ],
  "adopted": null,
  "status": "suggested"
}
```

---

## ディレクトリ構成

```
experiments/semantic_matcher/
├── PLAN.md              # この計画書
├── __init__.py
├── types.py             # DTO定義（MatchCandidate, MatchResult, AuditLogEntry）
├── matcher.py           # Matcher インターフェース
├── fuzzy.py             # Fuzzy matching 実装
├── audit_log.py         # 監査ログ出力
├── eval_types.py        # 評価ハーネス用DTO
├── extractor.py         # ログからサンプル抽出
├── evaluator.py         # 評価エンジン
└── eval.py              # CLI エントリポイント
```

---

## 実装フェーズ

### Phase 1: 骨組み ✅ 完了

- [x] ディレクトリ構成
- [x] types.py（DTO）
- [x] matcher.py（インターフェース）
- [x] fuzzy.py（rapidfuzz/difflib fallback）
- [x] audit_log.py（JSONL出力）
- [x] 最小テスト（35件パス）

### Phase 2: 評価ハーネス ✅ 完了

- [x] eval_types.py（MissingObjectSample, EvalResult, EvalMetrics）
- [x] extractor.py（turns_log.json からサンプル抽出）
- [x] evaluator.py（Threshold Grid 評価）
- [x] eval.py（CLI）
- [x] tests/test_semantic_matcher_eval.py（19件パス）

### Phase 3: 実データ評価 ✅ 完了

- [x] 既存 results/ での MISSING_OBJECT 集計
- [x] Semantic Matcher 適用評価
- [x] False Positive 率計測
- [x] レポート作成

**評価結果サマリー** (2026-01-26):
- **FP率**: 0.0% (全閾値で誤提案なし) ✅
- **Recall**: 14.3% (7件中1件を救済)
- **Precision**: 100.0%
- 詳細: `results/semantic_matcher_eval/REPORT.md`

### Phase 4: 統合検討（将来）

- [ ] main への統合判断
- [ ] GM 2x2 Runner との連携設計
- [ ] P0 Freeze 解除の要否検討

---

## FP分析と追加ガード案 (Phase 3実測結果)

### 実測結果

| 項目 | 値 |
|------|-----|
| 評価サンプル数 | 9件 (GT判定可能) |
| FP発生数 | **0件** |
| FP率 | **0.0%** |

**結論**: 現状の fuzzy matching では FP は発生していない。

### 未マッチパターン分析

FP=0だが、Recall向上のため未マッチパターンを分析:

| パターン | 例 | 失敗理由 | 発生頻度 |
|----------|-----|----------|----------|
| `Xの〜` | `冷蔵庫の牛乳` | 修飾部分が類似度を下げる | 高 |
| 長文記述 | `ソファーに深く腰掛け、少し間` | 動作記述が混入 | 中 |
| 複合修飾 | `本棚の植物図鑑らしき本` | 多段修飾で類似度極低 | 中 |

### FP抑制のための追加ガード案

**重要**: Auto-adopt は禁止のまま、suggestion 限定で以下を検討。

#### 案 1: 「Xの〜」パターン抽出

```python
import re

def extract_container_noun(query: str) -> str | None:
    """「Xの〜」パターンからXを抽出。"""
    match = re.match(r'^(.+?)の', query)
    if match:
        return match.group(1)
    return None
```

**リスク**: 「テレビのリモコン」→「テレビ」は正しいが、
「姉のカバン」→「姉」は誤り（姉はオブジェクトではない）。
→ **world_objects に存在する場合のみ採用** で回避。

#### 案 2: 長さフィルタ

```python
MAX_QUERY_LENGTH = 20  # これ以上は suggestion しない

def should_skip_long_query(query: str) -> bool:
    return len(query) > MAX_QUERY_LENGTH
```

**理由**: 長文は「アクション記述」である可能性が高く、
オブジェクト名マッチには適さない。

#### 案 3: 同スコア近接時の棄却

```python
MIN_SCORE_GAP = 0.1

def has_ambiguous_candidates(candidates: list) -> bool:
    if len(candidates) >= 2:
        gap = candidates[0].score - candidates[1].score
        return gap < MIN_SCORE_GAP
    return False
```

**理由**: 同程度のスコアで複数候補がある場合、
どちらが正解か判断できないため suggestion を控える。

---

## リスク

| リスク | 対策 |
|--------|------|
| 誤マッチによる評価精度低下 | 自動採用禁止、監査ログ必須 |
| パフォーマンス劣化 | キャッシュ、バッチ処理 |
| 日本語特有の問題 | 形態素解析の追加検討 |
| World Expansion の誘発 | No World Expansion ガードレール |
| GT不在サンプル過多 | exclusion_rate モニタリング |

---

## 成功基準

1. **MISSING_OBJECT 5% → 1% 以下**（True Positive 改善）
2. **False Positive 2% 以下**（誤マッチ抑制）
3. **監査ログで全操作追跡可能**
4. **main コードへの変更なし**（実験隔離）

---

*Last Updated: 2026-01-26*
