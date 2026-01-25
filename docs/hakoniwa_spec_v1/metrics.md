# HAKONIWA-G3 仕様 v1.0: メトリクス定義

## 1. Gate-3A メトリクス（P0必須：安全性）

**Gate-3A はP0ブロッカー。FAILの場合はリリース不可。**

### 1.1 give_up_rate

**定義**: リトライ上限（max_retries）に達して諦めた割合

```
give_up_rate = give_up_count / total_turns
```

**目標値**: < 10%

**Priority**: P0

**意味**: ほとんどのケースでリトライ内に解決できていることを示す

### 1.2 avg_retry_steps_extra

**定義**: 1ターンあたりの追加LLM呼び出し回数

```
retry_steps_extra = total_generation_calls - 1
avg_retry_steps_extra = Σ(retry_steps_extra) / total_turns
```

**目標値**: < 0.5

**Priority**: P0

**意味**: 効率的なリトライ（少ない回数で修正完了）ができていることを示す

### 1.3 hard_denied_count

**定義**: Preflightでhard_deny=Trueが返った回数

```
hard_denied_count = Σ(1 for turn where hard_deny=True)
```

**目標値**: = 0

**Priority**: P0

**意味**: P0ではhard_denyは禁止。GIVE_UP（PASS + log）を使うこと

### 1.4 GM Crash

**定義**: 例外によるクラッシュ回数

**目標値**: = 0

**Priority**: P0

**意味**: GMは例外で落ちてはならない（SchemaValidationErrorは起動前なのでOK）

---

## 2. Gate-3B メトリクス（P1改善：品質向上）

**Gate-3B はP1 Backlog。FAILでもP0リリースはブロックしない。**

### 2.1 retry_success_rate

**定義**: Preflight でリトライが実行された後、最終的に allowed=True となった割合

```
retry_success_rate = retry_success_count / preflight_retry_executed_count
```

**目標値**: > 80%

**Priority**: P1

**意味**: リトライ機構が正しく機能し、モデルが自己修正できていることを示す

### 2.2 silent_correction_rate

**定義**: 謝罪なしで行動が変わった割合

```
silent_correction_rate = silent_correction_count / total_turns
```

**目標値**: > 50%

**Priority**: P1

**意味**: 高いほど良い（謝罪なしで自然に修正）

---

## 2. Silent Correction

### 2.1 定義

**Silent Correction**: リトライ後に行動が変わったが、謝罪語を含まない状態

```python
silent_correction = (action_changed_after_retry == True) AND (final_speech NOT match apology_regex)
```

### 2.2 判定基準

1. **action_changed**: raw_action_intents ≠ final_action_intents
2. **no_apology**: final_speech に謝罪語が含まれない

### 2.3 謝罪語リスト（apology_regex）

**日本語:**
- すみません
- ごめん
- ごめんなさい
- 間違え
- 失礼
- 申し訳
- すいません

**英語（将来対応）:**
- sorry
- apologize
- mistake
- my bad

### 2.4 silent_correction_rate

```
silent_correction_rate = silent_correction_count / total_turns
```

**目標**: 高いほど良い（謝罪なしで自然に修正）

---

## 3. Format Break メトリクス

### 3.1 format_break_total

LLM出力がフォーマット規約に違反した回数

### 3.2 format_repaired_total

GM Serviceが修復に成功した回数

### 3.3 repair_success_rate

```
repair_success_rate = format_repaired_total / format_break_total
```

**目標値**: > 90%

### 3.4 repair_steps

修復に適用したtransformの段数:
- 0: 修復不要
- 1: STRIP（軽微な修復）
- 2: TRAILING_CUT（中程度の修復）
- 3+: FALLBACK（重い修復）

---

## 4. Preflight メトリクス

### 4.1 preflight_triggered

Preflightチェックが発動した回数（不可能行動の検出）

### 4.2 preflight_retry_suggested

GMが「リトライを推奨」と返した回数

### 4.3 preflight_retry_executed

実際にリトライが実行された回数

### 4.4 preflight_hard_denied

リトライ上限後もdenyされた回数

---

## 5. 品質メトリクス

### 5.1 impossible_action_rate

```
impossible_action_rate = gm_denied_count / total_turns
```

### 5.2 stall_rate

```
stall_rate = stall_event_count / total_turns
```

stall_event: stall_score > 0.5

### 5.3 addressing_violation_rate

```
addressing_violation_rate_raw = raw_violations / total_turns
addressing_violation_rate_final = final_violations / total_turns
```

---

## 6. レイテンシメトリクス

### 6.1 latency_breakdown

| Component | Description |
|-----------|-------------|
| llm_latency_ms | LLM API呼び出し時間 |
| gm_latency_ms | GM Service呼び出し時間 |
| total_latency_ms | 合計（llm + gm + overhead） |

### 6.2 統計値

- p50: 中央値
- p95: 95パーセンタイル
- avg: 平均値

---

*GM-015/GM-017/GM-018: Gate-3 メトリクス定義*
