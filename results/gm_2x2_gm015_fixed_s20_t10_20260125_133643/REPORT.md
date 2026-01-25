# GM 2×2 Experiment Report

Generated: 2026-01-25T14:01:33.018823
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm015_fixed_s20_t10 |
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
| Success Rate | 100.0% | 100.0% | 100.0% | 100.0% |
| Retry Rate | 0.00 | 0.00 | 0.04 | 0.04 |
| addressing_violation_rate_raw | 1.5% | 1.5% | 1.0% | 1.0% |
| addressing_violation_rate_final | 1.5% | 1.5% | 0.5% | 0.5% |
| impossible_action_rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Event Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| Stall Recovery Rate | 0.0% | 0.0% | 0.0% | 0.0% |
| GM Intervention Rate | 0.0% | 0.0% | 19.0% | 19.0% |
| Latency p50 (ms) | 1932.8 | 1935.0 | 1792.7 | 1795.4 |
| Latency p95 (ms) | 2646.3 | 2651.2 | 3331.5 | 3336.1 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 400
- GM injections: 76 (19.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| format_break | 74 |
| world_delta | 2 |

### GM-013: Move Metrics (exits interpretation)

- move_attempts_total: 2
- move_attempts_valid: 2 (100.0%)
- move_attempts_invalid: 0 (0.0%)
- move_corrected_within_2_turns: 0 (N/A)

### GM-013: missing_object Resolution

| Classification | Count | Rate |
|----------------|-------|------|
| soft_absorbed (alias/derived) | 74 | 18.5% |
| hard_denied (non-existent) | 0 | 0.0% |
| **TOTAL** | 74 | 18.5% |

### GM-013: Resolution Method Distribution

| Method | Count | Rate |
|--------|-------|------|
| exact | 2 | 0.5% |
| alias | 74 | 18.5% |
| derived | 0 | 0.0% |
| none | 0 | 0.0% |

### GM-015: Format Break Resilience

| Metric | Count | Rate |
|--------|-------|------|
| format_break_total | 4 | 1.0% |
| format_repaired_total | 4 | 1.0% |
| format_break_final | 0 | 0.0% |

#### format_break_type breakdown

| Type | Count | Rate |
|------|-------|------|
| TRAILING_GARBAGE | 4 | 1.0% |

### GM-015: Preflight Guidance

| Metric | Count | Rate |
|--------|-------|------|
| preflight_retry_suggested | 16 | 4.0% |
| preflight_retry_executed | 16 | 4.0% |
| preflight_hard_denied | 0 | 0.0% |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| A | 2646.3 | 0.0 | 2646.3 |
| B | 2651.1 | 0.0 | 2651.2 |
| C | 2522.9 | 2.3 | 3331.5 |
| D | 2523.9 | 2.3 | 3336.1 |

## 分析

### C vs A (GM効果)

- Stall Rate: A=0.0% → C=0.0% (diff: +0.0%)
- GM Intervention Rate: C=19.0%

### B vs A (Inject効果)

- Success Rate: A=100.0% → B=100.0%

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=3336.1ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.