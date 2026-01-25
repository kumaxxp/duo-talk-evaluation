# GM 2×2 Experiment Report

Generated: 2026-01-25T15:29:35.316200
Git SHA: `04da1524-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm017_gate |
| profile | gate |
| conditions | B, D |
| mode | real |
| model | gemma3:12b |
| seeds | 5 (0-4) |
| scenarios | coffee_trap,missing_tool,wrong_location |
| max_turns | 10 |
| temperature | 0.7 |
| max_tokens | 256 |
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

| Metric | B (ON/OFF) | D (ON/ON) |
|--------|---------- | ----------|
| Turns | 50 | 50 |
| Success Rate | 100.0% | 100.0% |
| Retry Rate | 0.00 | 0.00 |
| addressing_violation_rate_raw | 6.0% | 2.0% |
| addressing_violation_rate_final | 6.0% | 2.0% |
| impossible_action_rate | 0.0% | 0.0% |
| Stall Event Rate | 0.0% | 0.0% |
| Stall Recovery Rate | 0.0% | 0.0% |
| GM Intervention Rate | 0.0% | 100.0% |
| Latency p50 (ms) | 1593.2 | 1647.0 |
| Latency p95 (ms) | 2016.1 | 2319.7 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 50
- GM injections: 50 (100.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 50 |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| B | 2016.0 | 0.0 | 2016.1 |
| D | 2318.2 | 1.6 | 2319.7 |

## 分析

### C vs A (GM効果)

### B vs A (Inject効果)

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=2319.7ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.