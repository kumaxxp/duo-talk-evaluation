# GM 2×2 Experiment Report

Generated: 2026-01-25T14:51:00.613232
Git SHA: `04da1524-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | taste3_coffee_trap |
| profile | dev |
| conditions | D |
| mode | real |
| model | gemma3:12b |
| seeds | 1 (0-0) |
| scenarios | coffee_trap |
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
| Retry Rate | 0.40 |
| addressing_violation_rate_raw | 0.0% |
| addressing_violation_rate_final | 0.0% |
| impossible_action_rate | 0.0% |
| Stall Event Rate | 0.0% |
| Stall Recovery Rate | 0.0% |
| GM Intervention Rate | 80.0% |
| Latency p50 (ms) | 1581.1 |
| Latency p95 (ms) | 5406.0 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 5
- GM injections: 4 (80.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 4 |

### GM-015: Preflight Guidance

| Metric | Count | Rate |
|--------|-------|------|
| preflight_retry_suggested | 1 | 20.0% |
| preflight_retry_executed | 1 | 20.0% |
| preflight_hard_denied | 0 | 0.0% |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| D | 1860.8 | 4.2 | 5406.0 |

## 分析

### C vs A (GM効果)

### B vs A (Inject効果)

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=5406.0ms

## Taste-3: Retry/Give-up Metrics

| Metric | Value | Status |
|--------|-------|--------|
| preflight_triggered | 1 | - |
| preflight_retry_executed | 1 | - |
| retry_success_rate | 100.0% | 🟢 (>80% target) |
| avg_retry_steps | 2.00 | 🔴 (<1.5 target) |
| give_up_count | 0 | - |
| give_up_rate | 0.0% | 🟢 (<10% target, >=20% red) |
| silent_correction_count | 1 | - |

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.