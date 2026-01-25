# GM 2×2 Experiment Report

Generated: 2026-01-25T09:02:08.216140
Git SHA: `a481b474-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | smoke_test |
| seeds | 1 (0-0) |
| scenarios | default |
| max_turns | 3 |
| temperature | 0.7 |
| max_retries | 3 |
| gm_base_url | http://localhost:8001 |

## Experiment Matrix

| Condition | Inject | GM | Description |
|-----------|--------|-----|-------------|
| A | OFF | OFF | Baseline |
| B | ON | OFF | Phase 3.2 |
| C | OFF | ON | GM only |
| D | ON | ON | Full |

## Summary by Condition

| Condition | Runs | Success Rate | Retry Rate | GM Denied | Stall Events | Mean Stall | Latency p95 |
|-----------|------|--------------|------------|-----------|--------------|------------|-------------|
| A | 1 | 100.0% | 0.00 | 0 | 0 | 0.000 | 0.0ms |
| B | 1 | 100.0% | 0.00 | 0 | 0 | 0.000 | 0.0ms |
| C | 1 | 100.0% | 0.00 | 0 | 0 | 0.292 | 1.3ms |
| D | 1 | 100.0% | 0.00 | 0 | 0 | 0.292 | 1.1ms |

## GM Metrics (Conditions C, D)

- Total GM injections: 2 / 6 turns (33.3%)
- Total GM denials: 0 / 6 turns (0.0%)
- Stall events (score > 0.5): 0

### Injection Trigger Counts

| Trigger | Count |
|---------|-------|
| world_delta | 2 |

## Raw Data

See accompanying JSON file for detailed results.

See `examples_index.csv` for qualitative analysis index.