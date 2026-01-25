# GM 2×2 Experiment Report

Generated: 2026-01-25T13:36:18.932148
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm015_fix_test |
| mode | real |
| model | gemma3:12b |
| seeds | 5 (0-4) |
| scenarios | default |
| max_turns | 5 |
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
| Turns | 25 | 25 | 25 | 25 |
| Success Rate | 100.0% | 100.0% | 100.0% | 100.0% |
| Retry Rate | 0.00 | 0.00 | 0.00 | 0.00 |
| addressing_violation_rate_raw | 4.0% | 4.0% | 0.0% | 0.0% |
| addressing_violation_rate_final | 4.0% | 4.0% | 0.0% | 0.0% |
| impossible_action_rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Event Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Recovery Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| GM Intervention Rate | 0.0% | 0.0% | 24.0% | 24.0% |
| Latency p50 (ms) | 1430.7 | 1373.5 | 1478.2 | 1480.9 |
| Latency p95 (ms) | 1631.9 | 1605.7 | 1804.7 | 1805.9 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 50
- GM injections: 12 (24.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 12 |

### GM-013: Move Metrics (exits interpretation)

- move_attempts_total: 2
- move_attempts_valid: 2 (100.0%)
- move_attempts_invalid: 0 (0.0%)
- move_corrected_within_2_turns: 0 (N/A)

### GM-013: missing_object Resolution

| Classification | Count | Rate |
|----------------|-------|------|
| soft_absorbed (alias/derived) | 12 | 24.0% |
| hard_denied (non-existent) | 0 | 0.0% |
| **TOTAL** | 12 | 24.0% |

### GM-013: Resolution Method Distribution

| Method | Count | Rate |
|--------|-------|------|
| exact | 0 | 0.0% |
| alias | 12 | 24.0% |
| derived | 0 | 0.0% |
| none | 0 | 0.0% |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| A | 1631.9 | 0.0 | 1631.9 |
| B | 1605.7 | 0.0 | 1605.7 |
| C | 1803.2 | 1.5 | 1804.7 |
| D | 1804.4 | 1.5 | 1805.9 |

## 分析

### C vs A (GM効果)

- Stall Rate: A=0.0% → C=0.0% (diff: +0.0%)
- GM Intervention Rate: C=24.0%

### B vs A (Inject効果)

- Success Rate: A=100.0% → B=100.0%

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=1805.9ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.