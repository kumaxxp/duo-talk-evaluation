# GM 2×2 Experiment Report

Generated: 2026-01-25T17:58:42.707544
Git SHA: `04da1524-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gm018_verify |
| profile | dev |
| conditions | D |
| mode | real |
| model | gemma3:12b |
| seeds | 1 (0-0) |
| scenarios | default |
| max_turns | 4 |
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

## 用語定義 (GM-018)

| 用語 | 定義 |
|------|------|
| **gm_injection** | fact_cardsを付与した（毎ターンで発生しうる） |
| **gm_intervention** | 何かを変えた/止めた/直した（format repair, deny, retry, stall suggestion等） |
| **trigger** | interventionの契機（world_delta / deny / stall / format_break / none） |

- `trigger=none` は「何もしなかった」を意味する
- `gm_injection` は `gm_intervention` の一部ではない（独立した概念）

## 2×2 Results Summary

| Metric | D (ON/ON) |
|--------|----------|
| Turns | 4 |
| Success Rate | 100.0% |
| Retry Rate | 0.00 |
| addressing_violation_rate_raw | 0.0% |
| addressing_violation_rate_final | 0.0% |
| impossible_action_rate | 0.0% |
| Stall Event Rate | 0.0% |
| Stall Recovery Rate | 0.0% |
| GM Intervention Rate | 100.0% |
| Latency p50 (ms) | 1232.4 |
| Latency p95 (ms) | 1539.9 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 4
- GM injections: 4 (100.0%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| none | 4 |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| D | 1538.5 | 1.4 | 1539.9 |

## 分析

### C vs A (GM効果)

### B vs A (Inject効果)

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=1539.9ms

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.