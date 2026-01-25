# GM 2×2 Experiment Report

Generated: 2026-01-25T15:42:51.314423
Git SHA: `04da1524-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | normal_conv |
| profile | dev |
| conditions | D |
| mode | real |
| model | gemma3:12b |
| seeds | 1 (0-0) |
| scenarios | default |
| max_turns | 8 |
| temperature | 0.7 |
| max_tokens | 192 |
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

| Metric | D (ON/ON) |
|--------|----------|
| Turns | 8 |
| Success Rate | 100.0% |
| Retry Rate | 0.00 |
| addressing_violation_rate_raw | 0.0% |
| addressing_violation_rate_final | 0.0% |
| impossible_action_rate | 0.0% |
| Stall Event Rate | 0.0% |
| Stall Recovery Rate | 0.0% |
| GM Intervention Rate | 100.0% |
| Latency p50 (ms) | 1903.5 |
| Latency p95 (ms) | 2524.3 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 8
- GM injections: 8 (100.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 8 |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| D | 2522.8 | 1.5 | 2524.3 |

## 分析

### C vs A (GM効果)

### B vs A (Inject効果)

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=2524.3ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.