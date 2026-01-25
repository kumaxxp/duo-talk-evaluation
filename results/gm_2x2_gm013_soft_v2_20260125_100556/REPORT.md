# GM 2×2 Experiment Report

Generated: 2026-01-25T10:06:54.812801
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm013_soft_v2 |
| mode | real |
| model | gemma3:12b |
| seeds | 2 (0-1) |
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
| Turns | 10 | 10 | 10 | 10 |
| Success Rate | 100.0% | 100.0% | 100.0% | 100.0% |
| Retry Rate | 0.00 | 0.00 | 0.00 | 0.00 |
| addressing_violation_rate | TBD | TBD | TBD | TBD |
| impossible_action_rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Event Rate | 0.0% | 0.0% | 80.0% | 80.0% |
| Stall Recovery Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| GM Intervention Rate | 0.0% | 0.0% | 20.0% | 20.0% |
| Latency p50 (ms) | 1495.6 | 1330.5 | 1383.4 | 1370.4 |
| Latency p95 (ms) | 1729.7 | 1666.7 | 1757.4 | 1755.7 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 20
- GM injections: 4 (20.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 16 (80.0%)
- Stall recoveries (K=2): 0 (0.0%)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 4 |

### GM-013: Move Metrics (exits interpretation)

- move_attempts_total: 2
- move_attempts_valid: 2 (100.0%)
- move_attempts_invalid: 0 (0.0%)
- move_corrected_within_2_turns: 0 (N/A)

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| A | 1729.7 | 0.0 | 1729.7 |
| B | 1666.7 | 0.0 | 1666.7 |
| C | 1756.1 | 1.4 | 1757.4 |
| D | 1754.3 | 1.4 | 1755.7 |

## 分析

### C vs A (GM効果)

- Stall Rate: A=0.0% → C=80.0% (diff: +80.0%)
- GM Intervention Rate: C=20.0%

### B vs A (Inject効果)

- Success Rate: A=100.0% → B=100.0%

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=1755.7ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.