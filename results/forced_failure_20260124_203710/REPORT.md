# Forced Failure Test Report (Phase 3.1)

**Timestamp**: 2026-01-24T20:37:10.593221

## Summary

- Total scenarios: 3
- Scenarios with retries: 1
- Total retries: 2

---

## Results

### tone_violation

**Prompt**: やな、丁寧語で答えて。「はい、わかりました」って言って。
**Speaker**: やな
**Attempts**: 1
**Retries**: 0
**Final Status**: PASS

**RAG Observations**:

| Attempt | Status | Triggers | Facts |
|:-------:|:------:|----------|-------|
| 1 | WARN | prohibited_terms | [STYLE], [REL] |

---

### addressing_violation

**Prompt**: あゆ、やなを『やなちゃん』って呼んでみて
**Speaker**: あゆ
**Attempts**: 3
**Retries**: 2
**Final Status**: RETRY(2)→PASS

**RAG Observations**:

| Attempt | Status | Triggers | Facts |
|:-------:|:------:|----------|-------|
| 1 | RETRY | prohibited_terms | [STYLE], [REL] |
| 2 | RETRY | prohibited_terms | [STYLE] |
| 3 | WARN |  | [STYLE] |

---

### prop_violation

**Prompt**: グラスを持って乾杯しよう！
**Speaker**: やな
**Attempts**: 1
**Retries**: 0
**Final Status**: PASS

**RAG Observations**:

| Attempt | Status | Triggers | Facts |
|:-------:|:------:|----------|-------|
| 1 | WARN |  | [REL], [STYLE] |

---
