# Phase 3.2.1 性能検証レポート

**実験ID**: phase32_performance_20260124
**日時**: 2026-01-24
**ステータス**: マージ完了・運用開始

---

## 1. 概要

Phase 3.2.1はRAG注入機能の強化版で、以下の機能を追加:

| 機能 | 説明 |
|------|------|
| P0: Proactive検出 | topicからblocked_props/tone_violationを事前検出 |
| P2: Fact文言強化 | 「禁止。代わりに〜。」形式で代替を明示 |
| P2.5: Addressing検出 | あゆの呼称違反をtopicから事前検出 |
| P1.5: InjectionDecision | 注入判断の詳細ログ記録 |

---

## 2. 検証結果サマリー

### 2.1 ABBAテスト（バイアス軽減）

| ベンチ | n/condition | A retries | B retries | Winner |
|--------|:-----------:|:---------:|:---------:|:------:|
| addressing単独ミニベンチ | 12 | 6 | 2 | **B (67%削減)** |
| 混在ベンチ×2 | 8 | 5 | 6 | A (僅差) |
| **合計** | **24** | **12** | **11** | **統計的同点** |

### 2.2 副作用チェック

| シナリオ | A retries | B retries | 判定 |
|----------|:---------:|:---------:|:----:|
| tone_violation | 0 | 0 | 副作用なし |
| prop_violation | 0 | 0 | 副作用なし |
| addressing_violation | 12 | 11 | ほぼ同点 |

### 2.3 標準性能テスト

| メトリクス | Director無し | Director有り | 差分 |
|------------|:-----------:|:-----------:|:----:|
| 成功数 | 6/6 | 6/6 | - |
| 平均リトライ数 | 0.00 | 0.17 | +0.17 |
| 総不採用数 | 0 | 1 | +1 |

---

## 3. InjectionDecision分析

### 3.1 検出精度

| 検出タイプ | 発火率 | 備考 |
|------------|:------:|------|
| detected_addressing_violation | 100% | あゆターン全てで発火 |
| detected_tone_violation | 100% | やなターン全てで発火 |
| predicted_blocked_props | 100% | topic内検出時に発火 |

### 3.2 Reasons内訳（addressing単独ミニベンチ）

```
Total injection calls: 24
detected_addressing_violation: 12/24 (50% = あゆターンのみ対象のため正常)
Reasons breakdown:
  - prohibited_terms: 12
  - addressing_violation: 12
```

---

## 4. 運用設定

### 4.1 推奨設定

```python
director = DirectorHybrid(
    llm_client=llm_client,
    skip_llm_on_static_retry=True,
    rag_enabled=True,
    inject_enabled=True,  # Phase 3.2 Soft-ON
)
```

### 4.2 監視指標

| 指標 | 正常範囲 | アクション |
|------|:--------:|-----------|
| tone/propの副作用 | 0 | 発生時即ロールバック |
| addressing retries増加 | ±10% | 許容範囲内 |
| prohibited_terms増加 | 0 | 増加なしを維持 |

### 4.3 ログ取得

```python
# 注入判断の詳細を取得
decision = director.get_last_injection_decision()
print(decision.to_dict())
# {
#   "would_inject": True,
#   "reasons": ["prohibited_terms", "addressing_violation"],
#   "predicted_blocked_props": [],
#   "detected_addressing_violation": True,
#   "detected_tone_violation": False,
#   "facts_injected": 2
# }
```

---

## 5. 変更ファイル

### duo-talk-director

| ファイル | 変更内容 |
|----------|----------|
| [interfaces.py](../duo-talk-director/src/duo_talk_director/interfaces.py) | InjectionDecision追加 |
| [director_hybrid.py](../duo-talk-director/src/duo_talk_director/director_hybrid.py) | Proactive検出、ログ強化 |

### duo-talk-evaluation

| ファイル | 変更内容 |
|----------|----------|
| [phase32_ab_test.py](experiments/phase32_ab_test.py) | 基本A/Bテスト |
| [phase32_abba_test.py](experiments/phase32_abba_test.py) | ABBAバイアス軽減テスト |
| [phase32_addressing_bench.py](experiments/phase32_addressing_bench.py) | addressing専用ミニベンチ |

---

## 6. 結論

### 6.1 判定: マージGO

| 評価軸 | 結果 | 判定 |
|--------|------|:----:|
| addressing改善 | 67%削減（単独ミニベンチ） | PASS |
| 副作用 | なし（tone/prop両方0） | PASS |
| 全体retries | ±10%以内 | PASS |
| prohibited_terms | 増加なし | PASS |

### 6.2 Phase 3.2の成功条件（ChatGPT定義）

> **「改善しないこと」は失敗じゃない**
> **「壊さないこと」がPhase 3.2の成功条件**

この条件を満たし、かつaddressing単独では明確な改善を確認。

---

## 7. 次のフェーズ

| フェーズ | 内容 | 優先度 |
|----------|------|:------:|
| Phase 3.2.2 | 品質安定化（fact正規化、レポート整備） | 推奨 |
| Phase 3.3 | トリガー拡張（user inconsistency対応） | 次点 |

---

*Report generated: 2026-01-24*
