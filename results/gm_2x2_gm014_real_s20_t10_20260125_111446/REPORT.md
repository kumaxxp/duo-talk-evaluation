# GM 2×2 Experiment Report

Generated: 2026-01-25T11:38:56.543981
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm014_real_s20_t10 |
| mode | real |
| model | gemma3:12b |
| seeds | 20 (0-19) |
| scenarios | default |
| max_turns | 10 |
| temperature | 0.7 |
| max_tokens | 300 |
| max_retries | 3 |
| gm_base_url | http://localhost:8001 |
| llm_url | http://localhost:11434 |

## Experiment Matrix

| Condition | Inject | GM | Description |
|-----------|--------|-----|-------------|
| A | OFF | OFF | Baseline |
| B | ON | OFF | Phase 3.2 |
| C | OFF | ON | GM only |
| D | ON | ON | Full |

## 2×2 Results Summary

| Metric | A (OFF/OFF) | B (ON/OFF) | C (OFF/ON) | D (ON/ON) |
|--------|-------------|------------|------------|-----------|
| Turns | 200 | 200 | 200 | 200 |
| Success Rate | 100.0% | 100.0% | 95.0% | 95.0% |
| Retry Rate | 0.00 | 0.00 | 0.00 | 0.00 |
| addressing_violation_rate | 1.5% | 1.5% | 0.0% | 0.0% |
| impossible_action_rate | 0.0% | 0.0% | 5.0% | 5.0% |
| Stall Event Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Recovery Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| GM Intervention Rate | 0.0% | 0.0% | 21.0% | 21.0% |
| Latency p50 (ms) | 1855.7 | 1930.6 | 1830.4 | 1834.7 |
| Latency p95 (ms) | 2503.2 | 2647.9 | 2595.2 | 2597.3 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 400
- GM injections: 84 (21.0%)
- GM denials (impossible_actions): 20 (5.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### impossible_actions.breakdown

| Reason | Count |
|--------|-------|
| MISSING_OBJECT | 16 |
| NOT_OWNED | 4 |

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 62 |
| deny | 20 |
| world_delta | 2 |

### GM-013: Move Metrics (exits interpretation)

- move_attempts_total: 2
- move_attempts_valid: 2 (100.0%)
- move_attempts_invalid: 0 (0.0%)
- move_corrected_within_2_turns: 0 (N/A)

### GM-013: Creativity vs Hallucination

| Type | Count | Rate |
|------|-------|------|
| MISSING_OBJECT | 16 | 4.0% |
| NOT_OWNED | 4 | 1.0% |
| CONTRADICTS_WORLD | 0 | 0.0% |
| **TOTAL_HALLUCINATION** | 20 | 5.0% |

### GM-013: missing_object Resolution

| Classification | Count | Rate |
|----------------|-------|------|
| soft_absorbed (alias/derived) | 62 | 15.5% |
| hard_denied (non-existent) | 16 | 4.0% |
| **TOTAL** | 78 | 19.5% |

### GM-013: Resolution Method Distribution

| Method | Count | Rate |
|--------|-------|------|
| exact | 2 | 0.5% |
| alias | 62 | 15.5% |
| derived | 0 | 0.0% |
| none | 20 | 5.0% |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| A | 2503.2 | 0.0 | 2503.2 |
| B | 2647.9 | 0.0 | 2647.9 |
| C | 2593.5 | 1.9 | 2595.2 |
| D | 2595.6 | 1.8 | 2597.3 |

## GM-014: Stall Detection Redesign

### 設計変更

| 項目 | GM-013 | GM-014 |
|------|--------|--------|
| Primary Indicator | no_world_delta | speech_repeat (hash/similarity) |
| speech_repeat weight | 0.00 | 0.70 |
| no_world_delta weight | 0.70 | 0.20 |
| short_response weight | 0.10 | 0.10 |
| Cooldown | 2 turns | 5 turns |
| Similarity method | N/A | Jaccard (2-gram) |
| Threshold | 0.7 | 0.8 (stalled) |

### GM-014 Stall Metrics

| Metric | GM-013 | GM-014 | 改善 |
|--------|--------|--------|------|
| Stall Event Rate | 82.0% | 0.0% | **-82.0%** |
| Stall Trigger Count | 22 | 0 | **-100%** |
| False Positive Rate | High | 0% | ✓ |

### Key Changes

1. **Speech Repetition Primary (0.70)**: ハッシュ一致 + Jaccard類似度による発話繰り返し検出
2. **no_world_delta Demoted (0.20)**: 雑談シナリオでの誤検出を防止
3. **Cooldown 5 Turns**: 連続警告を抑制
4. **GM-injected Exclusion**: GM注入ターンはrepetition検査から除外

## 分析

### C vs A (GM効果)

- Stall Rate: A=0.0% → C=0.0% (diff: +0.0%)
- GM Intervention Rate: C=21.0%

### B vs A (Inject効果)

- Success Rate: A=100.0% → B=100.0%

### D vs others (相乗効果)

- Success Rate: D=95.0%
- Latency p95: D=2597.3ms

### GM-014 vs GM-013 Comparison

| Metric | GM-013 | GM-014 | 変化 |
|--------|--------|--------|------|
| Stall Event Rate (C/D) | 82.0% | 0.0% | **-82%** |
| Stall Trigger in gm_interventions | 22 | 0 | **-100%** |
| addressing_violation_rate (A/B) | TBD | 1.5% | 数値化 |
| addressing_violation_rate (C/D) | TBD | 0.0% | GM効果 |

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.