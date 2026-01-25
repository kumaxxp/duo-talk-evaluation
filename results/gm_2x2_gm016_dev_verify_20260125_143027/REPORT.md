# GM 2×2 Experiment Report

Generated: 2026-01-25T14:30:37.877633
Git SHA: `04da1524-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm016_dev_verify |
| profile | dev |
| conditions | D |
| mode | real |
| model | gemma3:12b |
| seeds | 1 (0-0) |
| scenarios | default |
| max_turns | 5 |
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
| Turns | 5 |
| Success Rate | 100.0% |
| Retry Rate | 0.00 |
| addressing_violation_rate_raw | 0.0% |
| addressing_violation_rate_final | 0.0% |
| impossible_action_rate | 0.0% |
| Stall Event Rate | 0.0% |
| Stall Recovery Rate | 0.0% |
| GM Intervention Rate | 20.0% |
| Latency p50 (ms) | 1240.3 |
| Latency p95 (ms) | 2250.1 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 5
- GM injections: 1 (20.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 1 |

### GM-013: missing_object Resolution

| Classification | Count | Rate |
|----------------|-------|------|
| soft_absorbed (alias/derived) | 1 | 20.0% |
| hard_denied (non-existent) | 0 | 0.0% |
| **TOTAL** | 1 | 20.0% |

### GM-013: Resolution Method Distribution

| Method | Count | Rate |
|--------|-------|------|
| exact | 0 | 0.0% |
| alias | 1 | 20.0% |
| derived | 0 | 0.0% |
| none | 0 | 0.0% |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| D | 2248.5 | 1.7 | 2250.1 |

## 分析

### C vs A (GM効果)

### B vs A (Inject効果)

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=2250.1ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.