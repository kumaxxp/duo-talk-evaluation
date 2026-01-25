# GM 2×2 Experiment Report

Generated: 2026-01-25T10:49:14.048313
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm013_real_s20_t10 |
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
| addressing_violation_rate | TBD | TBD | TBD | TBD |
| impossible_action_rate | 0.0% | 0.0% | 5.0% | 5.0% |
| Stall Event Rate | 0.0% | 0.0% | 82.0% | 82.0% |
| Stall Recovery Rate | 0.0% | 0.0% | 1.2% | 1.2% |
| GM Intervention Rate | 0.0% | 0.0% | 21.0% | 21.0% |
| Latency p50 (ms) | 1850.7 | 1923.8 | 1828.6 | 1830.0 |
| Latency p95 (ms) | 2505.1 | 2642.6 | 2588.9 | 2589.8 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 400
- GM injections: 84 (21.0%)
- GM denials (impossible_actions): 20 (5.0%)
- Stall events: 328 (82.0%)
- Stall recoveries (K=2): 4 (1.2%)

### impossible_actions.breakdown

| Reason | Count |
|--------|-------|
| MISSING_OBJECT | 16 |
| NOT_OWNED | 4 |

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 40 |
| stall | 22 |
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
| A | 2505.1 | 0.0 | 2505.1 |
| B | 2642.6 | 0.0 | 2642.6 |
| C | 2587.3 | 1.6 | 2588.9 |
| D | 2588.2 | 1.6 | 2589.8 |

## 分析

### C vs A (GM効果)

- Stall Rate: A=0.0% → C=82.0% (diff: +82.0%)
- GM Intervention Rate: C=21.0%

### B vs A (Inject効果)

- Success Rate: A=100.0% → B=100.0%

### D vs others (相乗効果)

- Success Rate: D=95.0%
- Latency p95: D=2589.8ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.