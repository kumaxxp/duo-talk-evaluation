# P-Next4 Topic A: Semantic Matcher 実験計画

**Branch**: `experiments/semantic_matcher`
**Created**: 2026-01-26
**Status**: 実験フェーズ（mainへの統合なし）

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

## 方式案

### 案 A: Fuzzy String Matching（rapidfuzz）

**概要**: 文字列の編集距離・類似度スコアに基づくマッチング。

**メリット**:
- 依存ライブラリが軽量（rapidfuzz のみ）
- 処理速度が高速
- 実装がシンプル
- 日本語でも動作

**デメリット**:
- 意味的な類似性を捉えられない（"椅子" と "座席" は低スコア）
- 閾値チューニングが必要

**実装優先度**: **高**（まずこちらで検証）

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

### 案 B: Embedding + Vector Search

**概要**: テキストをベクトル化し、コサイン類似度で検索。

**メリット**:
- 意味的な類似性を捉えられる
- "コーヒー" と "コーヒー豆" のような関連性を検出可能

**デメリット**:
- 外部API依存（OpenAI Embedding / SentenceTransformers）
- レイテンシが増加
- 実装が複雑
- モデルサイズ・コストの考慮が必要

**実装優先度**: **低**（案Aで不足の場合に検討）

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

def embedding_match(query: str, candidates: list[str], threshold: float = 0.8) -> list[MatchCandidate]:
    query_vec = model.encode(query)
    candidate_vecs = model.encode(candidates)
    similarities = cosine_similarity([query_vec], candidate_vecs)[0]
    ...
```

---

## ガードレール

### 1. マッチ対象の制限

```python
def match(query: str, world_objects: set[str]) -> list[MatchCandidate]:
    """
    マッチは world_objects 内のオブジェクトに対してのみ行う。
    world_objects に存在しないオブジェクトは絶対に返さない。
    """
    ...
```

### 2. Confidence 閾値

| 閾値 | 動作 |
|------|------|
| >= 0.9 | 自動採用（高信頼） |
| 0.7 - 0.9 | 候補提示（人間確認推奨） |
| < 0.7 | 不一致（マッチなし） |

**重要**: 初期実装では自動採用を禁止し、全て「候補提示」に留める。

### 3. 一般名詞の除外

「床」「壁」「空気」などの一般的すぎる名詞は、マッチ候補として
**提示はするが、採用は禁止** する。

```python
GENERIC_NOUNS = {"床", "壁", "天井", "空気", "部屋", "場所"}

def should_auto_adopt(candidate: MatchCandidate) -> bool:
    if candidate.name in GENERIC_NOUNS:
        return False  # 一般名詞は自動採用しない
    ...
```

### 4. 監査ログ

全てのマッチング操作をJSONL形式で記録:

```json
{
  "timestamp": "2026-01-26T15:30:00Z",
  "input_query": "コーヒー",
  "world_objects": ["コーヒー豆", "コーヒーメーカー", "マグカップ"],
  "candidates": [
    {"name": "コーヒー豆", "score": 0.85, "method": "fuzzy"},
    {"name": "コーヒーメーカー", "score": 0.72, "method": "fuzzy"}
  ],
  "adopted": null,
  "rejection_reason": "below_auto_threshold"
}
```

---

## 評価計画

### 1. 既存ログでの MISSING_OBJECT 再計測

```bash
# 既存の評価結果から MISSING_OBJECT を抽出
grep -r "MISSING_OBJECT" results/ | wc -l

# Semantic Matcher 適用後の再評価
python experiments/semantic_matcher/evaluate.py --results-dir results/
```

### 2. False Positive 率の監視（最重要）

誤マッチ（本来別のオブジェクトなのにマッチしてしまう）を重点監視:

| メトリクス | 目標 |
|-----------|------|
| True Positive Rate | >= 90% |
| False Positive Rate | <= 2% |
| Precision | >= 95% |

### 3. 可視化（2分確認）

NiceGUI または CLI ログで以下を確認可能にする:

- マッチング候補一覧
- スコア分布
- 採用/却下の理由

---

## ディレクトリ構成

```
experiments/semantic_matcher/
├── PLAN.md              # この計画書
├── __init__.py
├── types.py             # DTO定義（MatchCandidate, MatchResult, AuditLog）
├── matcher.py           # Matcher インターフェース
├── fuzzy.py             # Fuzzy matching 実装
├── audit_log.py         # 監査ログ出力
├── evaluate.py          # 評価スクリプト（将来）
└── tests/
    ├── __init__.py
    ├── test_fuzzy.py    # Fuzzy matcher テスト
    ├── test_matcher.py  # Matcher インターフェーステスト
    └── test_guardrails.py # ガードレールテスト
```

---

## 実装フェーズ

### Phase 1: 骨組み（今回実施）

- [x] ディレクトリ構成
- [ ] types.py（DTO）
- [ ] matcher.py（インターフェース）
- [ ] fuzzy.py（rapidfuzz 使用、なければ標準lib暫定）
- [ ] audit_log.py（JSONL出力）
- [ ] 最小テスト

### Phase 2: 評価（次回）

- [ ] 既存ログでの MISSING_OBJECT 集計
- [ ] Semantic Matcher 適用
- [ ] False Positive 率計測
- [ ] レポート作成

### Phase 3: 統合検討（将来）

- [ ] main への統合判断
- [ ] GM 2x2 Runner との連携設計
- [ ] P0 Freeze 解除の要否検討

---

## リスク

| リスク | 対策 |
|--------|------|
| 誤マッチによる評価精度低下 | 自動採用禁止、監査ログ必須 |
| パフォーマンス劣化 | キャッシュ、バッチ処理 |
| 日本語特有の問題 | 形態素解析の追加検討 |
| World Expansion の誘発 | No World Expansion ガードレール |

---

## 成功基準

1. **MISSING_OBJECT 5% → 1% 以下**（True Positive 改善）
2. **False Positive 2% 以下**（誤マッチ抑制）
3. **監査ログで全操作追跡可能**
4. **main コードへの変更なし**（実験隔離）

---

*Last Updated: 2026-01-26*
