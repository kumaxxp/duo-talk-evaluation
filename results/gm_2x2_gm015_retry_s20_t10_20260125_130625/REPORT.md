# GM 2×2 Experiment Report

Generated: 2026-01-25T13:30:32.304017
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm015_retry_s20_t10 |
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
| addressing_violation_rate_raw | 1.5% | 1.5% | 0.0% | 0.0% |
| addressing_violation_rate_final | 1.5% | 1.5% | 0.0% | 0.0% |
| impossible_action_rate | 0.0% | 0.0% | 5.0% | 5.0% |
| Stall Event Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Recovery Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| GM Intervention Rate | 0.0% | 0.0% | 21.0% | 21.0% |
| Latency p50 (ms) | 1848.0 | 1929.4 | 1836.3 | 1836.8 |
| Latency p95 (ms) | 2521.0 | 2649.8 | 2599.3 | 2597.3 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 400
- GM injections: 84 (21.0%)
- GM denials (impossible_actions): 20 (5.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### impossible_actions.breakdown

| Reason | Count |
|--------|-------|
| MISSING_OBJECT | 16 |
| NOT_OWNED | 4 |

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 62 |
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

### GM-015: Preflight Guidance

| Metric | Count | Rate |
|--------|-------|------|
| preflight_retry_suggested | 0 | 0.0% |
| preflight_retry_executed | 0 | 0.0% |
| preflight_hard_denied | 20 | 5.0% |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| A | 2521.0 | 0.0 | 2521.0 |
| B | 2649.7 | 0.0 | 2649.8 |
| C | 2597.2 | 2.1 | 2599.3 |
| D | 2595.5 | 1.8 | 2597.3 |

## 分析

### C vs A (GM効果)

- Stall Rate: A=0.0% → C=0.0% (diff: +0.0%)
- GM Intervention Rate: C=21.0%

### B vs A (Inject効果)

- Success Rate: A=100.0% → B=100.0%

### D vs others (相乗効果)

- Success Rate: D=95.0%
- Latency p95: D=2597.3ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.