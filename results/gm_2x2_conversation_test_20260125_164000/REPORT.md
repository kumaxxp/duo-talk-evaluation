# GM 2×2 Experiment Report

Generated: 2026-01-25T16:40:00.610506
Git SHA: `04da1524-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | conversation_test |
| profile | dev |
| conditions | D |
| mode | sim |
| model | simulation |
| seeds | 1 (0-0) |
| scenarios | default |
| max_turns | 6 |
| temperature | 0.7 |
| max_tokens | 192 |
| max_retries | 3 |
| gm_base_url | http://localhost:8001 |

## Experiment Matrix

| Condition | Inject | GM | Description |
|-----------|--------|-----|-------------|
| A | OFF | OFF | Baseline |
| B | ON | OFF | Phase 3.2 |
| C | OFF | ON | GM only |
| D | ON | ON | Full |

## 2×2 Results Summary

| Metric | D (ON/ON) |
|--------|----------|
| Turns | 6 |
| Success Rate | 100.0% |
| Retry Rate | 0.00 |
| addressing_violation_rate_raw | 0.0% |
| addressing_violation_rate_final | 0.0% |
| impossible_action_rate | 0.0% |
| Stall Event Rate | 0.0% |
| Stall Recovery Rate | 0.0% |
| GM Intervention Rate | 100.0% |
| Latency p50 (ms) | 1.1 |
| Latency p95 (ms) | 1.2 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 6
- GM injections: 6 (100.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 6 |

### GM-013: Move Metrics (exits interpretation)

- move_attempts_total: 1
- move_attempts_valid: 1 (100.0%)
- move_attempts_invalid: 0 (0.0%)
- move_corrected_within_2_turns: 0 (N/A)

## 分析

### C vs A (GM効果)

### B vs A (Inject効果)

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=1.2ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.