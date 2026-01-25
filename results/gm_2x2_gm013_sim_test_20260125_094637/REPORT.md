# GM 2×2 Experiment Report

Generated: 2026-01-25T09:46:37.799021
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm013_sim_test |
| mode | sim |
| model | simulation |
| seeds | 2 (0-1) |
| scenarios | default |
| max_turns | 3 |
| temperature | 0.7 |
| max_tokens | 300 |
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

| Metric | A (OFF/OFF) | B (ON/OFF) | C (OFF/ON) | D (ON/ON) |
|--------|-------------|------------|------------|-----------|
| Turns | 6 | 6 | 6 | 6 |
| Success Rate | 100.0% | 100.0% | 100.0% | 100.0% |
| Retry Rate | 0.00 | 0.00 | 0.00 | 0.00 |
| addressing_violation_rate | TBD | TBD | TBD | TBD |
| impossible_action_rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Event Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Recovery Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| GM Intervention Rate | 0.0% | 0.0% | 50.0% | 50.0% |
| Latency p50 (ms) | 0.0 | 0.0 | 1.1 | 1.0 |
| Latency p95 (ms) | 0.0 | 0.0 | 1.2 | 1.0 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 12
- GM injections: 6 (50.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| world_delta | 6 |

### GM-013: Move Metrics (exits interpretation)

- move_attempts_total: 2
- move_attempts_valid: 2 (100.0%)
- move_attempts_invalid: 0 (0.0%)
- move_corrected_within_2_turns: 0 (N/A)

## 分析

### C vs A (GM効果)

- Stall Rate: A=0.0% → C=0.0% (diff: +0.0%)
- GM Intervention Rate: C=50.0%

### B vs A (Inject効果)

- Success Rate: A=100.0% → B=100.0%

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=1.0ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.