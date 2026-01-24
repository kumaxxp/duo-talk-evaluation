# Thoughtログ評価指標仕様

**Version**: 1.0
**Date**: 2026-01-24
**Status**: Draft

---

## 概要

ThoughtLoggerが収集するログデータから、対話品質を評価するための指標を定義する。

## データソース

ThoughtLogEntryから取得可能なフィールド:

| フィールド | 型 | 説明 |
|-----------|-----|------|
| thought | str | Thought本文 |
| thought_length | int | Thought長 (文字数) |
| thought_missing | bool | Thought欠落フラグ |
| speaker | str | 話者 (やな/あゆ) |
| emotion | str | 検出感情 |
| emotion_intensity | float | 感情強度 (0.0-1.0) |
| relationship_tone | str | 関係性トーン |
| state_confidence | float | StateExtractor信頼度 |

---

## 評価指標

### 1. 基本品質指標

| 指標 | 計算式 | 目標 | 説明 |
|------|--------|------|------|
| thought_missing_rate | 欠落数 / 総ターン数 | ≤ 1% | Thought欠落率 |
| thought_length_avg | 総文字数 / 総ターン数 | ≥ 50文字 | 平均Thought長 |
| thought_length_min | min(全thought_length) | ≥ 20文字 | 最短Thought長 |

### 2. キャラクター別指標

| 指標 | 計算式 | 説明 |
|------|--------|------|
| yana_thought_avg | やなのthought_length平均 | やなのThought平均長 |
| ayu_thought_avg | あゆのthought_length平均 | あゆのThought平均長 |
| character_balance | abs(yana_avg - ayu_avg) / max(yana_avg, ayu_avg) | キャラクター間バランス (0に近いほど良い) |

### 3. 感情分布指標

| 指標 | 計算式 | 目標 | 説明 |
|------|--------|------|------|
| emotion_diversity | ユニーク感情数 / 総ターン数 | ≥ 0.3 | 感情の多様性 |
| neutral_rate | NEUTRAL数 / 総ターン数 | ≤ 50% | NEUTRAL率 (低いほど表現豊か) |
| high_intensity_rate | (intensity > 0.7)数 / 総ターン数 | 10-30% | 高強度感情率 |

### 4. キャラクター感情プロファイル

#### やな (姉) の期待プロファイル

| 感情 | 期待頻度 | 説明 |
|------|---------|------|
| JOY | 高 (30-50%) | 明るく元気 |
| WORRY | 中 (10-20%) | 妹を心配 |
| CONFIDENCE | 中 (10-20%) | 行動派 |
| NEUTRAL | 低 (≤20%) | - |

#### あゆ (妹) の期待プロファイル

| 感情 | 期待頻度 | 説明 |
|------|---------|------|
| SKEPTICAL | 高 (20-40%) | 姉に辛辣 |
| NEUTRAL | 中 (20-30%) | 冷静 |
| TRUST | 中 (10-20%) | 姉への信頼 (隠れた) |
| ANNOYANCE | 中 (10-20%) | ツンデレ |

### 5. 関係性トーン指標

| 指標 | 計算式 | 目標 | 説明 |
|------|--------|------|------|
| supportive_rate | SUPPORTIVE数 / 総ターン数 | 20-40% | 支持的トーン率 |
| teasing_rate | TEASING数 / 総ターン数 | 10-30% | からかいトーン率 |
| cold_rate | COLD数 / 総ターン数 | ≤ 20% | 冷淡トーン率 |

---

## 評価関数

### ThoughtQualityScore

```python
def calculate_thought_quality_score(entries: list[ThoughtLogEntry]) -> float:
    """Calculate overall thought quality score (0.0-1.0)"""

    # 基本品質 (40%)
    missing_score = 1.0 - min(missing_rate / 0.01, 1.0)  # 1%以下で満点
    length_score = min(avg_length / 80, 1.0)  # 80文字以上で満点
    basic_score = (missing_score * 0.6 + length_score * 0.4) * 0.4

    # 感情多様性 (30%)
    diversity_score = min(emotion_diversity / 0.5, 1.0)  # 0.5以上で満点
    neutral_penalty = max(0, neutral_rate - 0.5) * 2  # 50%超過でペナルティ
    emotion_score = (diversity_score * 0.7 + (1.0 - neutral_penalty) * 0.3) * 0.3

    # キャラクター一貫性 (30%)
    profile_match = calculate_profile_match(entries)  # 期待プロファイルとの一致度
    character_score = profile_match * 0.3

    return basic_score + emotion_score + character_score
```

---

## 実装計画

### Phase 1: 基本指標 (即時実装可能)

1. `ThoughtMetricsCalculator` クラス作成
2. 基本品質指標の実装
3. ベンチマークへの統合

### Phase 2: 感情分析 (StateExtractor統合後)

1. 感情分布指標の実装
2. キャラクター感情プロファイル評価
3. 関係性トーン評価

### Phase 3: 高度な評価 (ログ蓄積後)

1. 時系列分析 (感情の流れ)
2. シナリオ別分析
3. 異常検知

---

## 使用例

```python
from duo_talk_director.logging import ThoughtLogger
from evaluation.thought_metrics import ThoughtMetricsCalculator

# ログ収集
logger = ThoughtLogger()
entries = logger.log_store.read_all("thought")

# 評価
calculator = ThoughtMetricsCalculator()
metrics = calculator.calculate(entries)

print(f"Missing Rate: {metrics.missing_rate:.2%}")
print(f"Avg Length: {metrics.avg_length:.1f}")
print(f"Quality Score: {metrics.quality_score:.2f}")
```

---

## 次のステップ

1. [ ] ThoughtMetricsCalculatorの実装
2. [ ] ベンチマークへの統合
3. [ ] レポート出力機能追加
4. [ ] ログ蓄積後のプロファイル分析
