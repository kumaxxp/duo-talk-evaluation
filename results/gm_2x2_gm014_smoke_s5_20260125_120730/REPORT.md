# GM 2×2 Experiment Report

Generated: 2026-01-25T12:07:30.468211
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm014_smoke_s5 |
| mode | sim |
| model | simulation |
| seeds | 5 (0-4) |
| scenarios | default |
| max_turns | 10 |
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
| Turns | 50 | 50 | 50 | 50 |
| Success Rate | 100.0% | 100.0% | 100.0% | 100.0% |
| Retry Rate | 0.00 | 0.00 | 0.00 | 0.00 |
| addressing_violation_rate | 0.0% | 0.0% | 0.0% | 0.0% |
| impossible_action_rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Event Rate | 0.0% | 0.0% | 20.0% | 20.0% |
| Stall Recovery Rate | 0.0% | 0.0% | 100.0% | 100.0% |
| GM Intervention Rate | 0.0% | 0.0% | 60.0% | 60.0% |
| Latency p50 (ms) | 0.0 | 0.0 | 1.2 | 1.1 |
| Latency p95 (ms) | 0.0 | 0.0 | 1.3 | 1.2 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 100
- GM injections: 60 (60.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 20 (20.0%)
- Stall recoveries (K=2): 20 (100.0%)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| world_delta | 40 |
| stall | 20 |

### GM-013: Move Metrics (exits interpretation)

- move_attempts_total: 20
- move_attempts_valid: 20 (100.0%)
- move_attempts_invalid: 0 (0.0%)
- move_corrected_within_2_turns: 0 (N/A)

### GM-013: Resolution Method Distribution

| Method | Count | Rate |
|--------|-------|------|
| exact | 20 | 20.0% |
| alias | 0 | 0.0% |
| derived | 0 | 0.0% |
| none | 0 | 0.0% |

## 分析

### C vs A (GM効果)

- Stall Rate: A=0.0% → C=20.0% (diff: +20.0%)
- GM Intervention Rate: C=60.0%

### B vs A (Inject効果)

- Success Rate: A=100.0% → B=100.0%

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=1.2ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.