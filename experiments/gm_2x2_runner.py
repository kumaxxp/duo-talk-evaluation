"""GM 2×2 Experiment Runner (GM-010).

Runs 2×2 experiment matrix:
- A: Observe + GM OFF (baseline)
- B: Inject + GM OFF (Phase 3.2)
- C: Observe + GM ON (GM only)
- D: Inject + GM ON (full)

Usage:
    python -m experiments.gm_2x2_runner \
        --experiment_id exp001 \
        --seeds 10 \
        --scenarios scenarios/*.yaml \
        --max_turns 10
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Experiment conditions
CONDITIONS = ["A", "B", "C", "D"]

# Condition flags
CONDITION_CONFIG = {
    "A": {"inject_enabled": False, "gm_enabled": False},
    "B": {"inject_enabled": True, "gm_enabled": False},
    "C": {"inject_enabled": False, "gm_enabled": True},
    "D": {"inject_enabled": True, "gm_enabled": True},
}


@dataclass
class ExperimentConfig:
    """Configuration for 2×2 experiment."""

    experiment_id: str
    seeds: list[int] = field(default_factory=lambda: list(range(10)))
    scenarios: list[str] = field(default_factory=list)
    max_turns: int = 10
    temperature: float = 0.7
    max_retries: int = 3
    gm_base_url: str = "http://localhost:8001"
    output_dir: Path = field(default_factory=lambda: Path("results"))


@dataclass
class TurnResult:
    """Result of a single dialogue turn."""

    turn_number: int
    speaker: str
    raw_output: str
    parsed_thought: Optional[str]
    parsed_speech: Optional[str]
    allowed: bool
    denied_reason: Optional[str]
    world_delta: list[dict]
    stall_score: float
    fact_cards: list[str]
    retry_count: int
    latency_ms: float
    gm_latency_ms: Optional[float]


@dataclass
class RunResult:
    """Result of a single experiment run."""

    condition: str
    scenario: str
    seed: int
    inject_enabled: bool
    gm_enabled: bool
    turns: list[TurnResult]
    total_retries: int
    success_rate: float
    gm_injected_count: int
    gm_denied_count: int
    mean_stall_score: float
    latency_p50_ms: float
    latency_p95_ms: float
    timestamp: str


class GMClient:
    """HTTP client for GM Service."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def step(
        self,
        session_id: str,
        turn_number: int,
        speaker: str,
        raw_output: str,
        world_state: dict
    ) -> tuple[dict, float]:
        """Call GM /v1/gm/step endpoint.

        Returns:
            (response_data, latency_ms)
        """
        start = time.perf_counter()

        response = await self.client.post(
            f"{self.base_url}/v1/gm/step",
            json={
                "session_id": session_id,
                "turn_number": turn_number,
                "speaker": speaker,
                "raw_output": raw_output,
                "world_state": world_state,
            }
        )
        response.raise_for_status()

        latency_ms = (time.perf_counter() - start) * 1000
        return response.json(), latency_ms

    async def clear_session(self, session_id: str) -> None:
        """Clear GM session."""
        await self.client.delete(f"{self.base_url}/v1/gm/session/{session_id}")

    async def health_check(self) -> bool:
        """Check if GM service is healthy."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class ExperimentRunner:
    """Runner for 2×2 experiment."""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.gm_client = GMClient(config.gm_base_url)

    async def run_all(self) -> list[RunResult]:
        """Run all experiment conditions."""
        results: list[RunResult] = []

        # Check GM health if any GM-enabled conditions
        if any(CONDITION_CONFIG[c]["gm_enabled"] for c in CONDITIONS):
            if not await self.gm_client.health_check():
                logger.warning("GM service not available, skipping GM-enabled conditions")
                conditions = [c for c in CONDITIONS if not CONDITION_CONFIG[c]["gm_enabled"]]
            else:
                conditions = CONDITIONS
                logger.info("GM service healthy")
        else:
            conditions = CONDITIONS

        total_runs = len(conditions) * len(self.config.scenarios) * len(self.config.seeds)
        current_run = 0

        for condition in conditions:
            for scenario in self.config.scenarios:
                for seed in self.config.seeds:
                    current_run += 1
                    logger.info(
                        f"Run {current_run}/{total_runs}: "
                        f"condition={condition}, scenario={scenario}, seed={seed}"
                    )

                    result = await self.run_single(
                        condition=condition,
                        scenario=scenario,
                        seed=seed
                    )
                    results.append(result)

        await self.gm_client.close()
        return results

    async def run_single(
        self,
        condition: str,
        scenario: str,
        seed: int
    ) -> RunResult:
        """Run a single experiment condition."""
        config = CONDITION_CONFIG[condition]
        inject_enabled = config["inject_enabled"]
        gm_enabled = config["gm_enabled"]

        session_id = f"{self.config.experiment_id}_{condition}_{scenario}_{seed}"
        turns: list[TurnResult] = []
        total_retries = 0
        gm_injected_count = 0
        gm_denied_count = 0
        stall_scores: list[float] = []
        latencies: list[float] = []

        # Load scenario
        world_state = self._load_scenario(scenario)

        # Clear GM session
        if gm_enabled:
            await self.gm_client.clear_session(session_id)

        # Simulate dialogue turns
        for turn_number in range(self.config.max_turns):
            speaker = "やな" if turn_number % 2 == 0 else "あゆ"

            # Simulate LLM output (placeholder for actual integration)
            raw_output = self._simulate_output(turn_number, speaker, seed)

            # Track timing
            start = time.perf_counter()
            retry_count = 0
            gm_latency_ms = None

            # Call GM if enabled
            if gm_enabled:
                gm_response, gm_latency_ms = await self.gm_client.step(
                    session_id=session_id,
                    turn_number=turn_number,
                    speaker=speaker,
                    raw_output=raw_output,
                    world_state=world_state
                )

                allowed = gm_response["allowed"]
                denied_reason = gm_response.get("denied_reason")
                world_delta = gm_response.get("world_delta", [])
                stall_score = gm_response.get("stall_score", 0.0)
                fact_cards = gm_response.get("fact_cards", [])
                parsed = gm_response.get("parsed", {})

                if not allowed:
                    gm_denied_count += 1

                if fact_cards:
                    gm_injected_count += 1

                stall_scores.append(stall_score)
            else:
                # GM disabled - mock response
                allowed = True
                denied_reason = None
                world_delta = []
                stall_score = 0.0
                fact_cards = []
                parsed = {"thought": None, "speech": raw_output}

            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

            turn_result = TurnResult(
                turn_number=turn_number,
                speaker=speaker,
                raw_output=raw_output,
                parsed_thought=parsed.get("thought"),
                parsed_speech=parsed.get("speech"),
                allowed=allowed,
                denied_reason=denied_reason,
                world_delta=world_delta,
                stall_score=stall_score,
                fact_cards=fact_cards,
                retry_count=retry_count,
                latency_ms=latency_ms,
                gm_latency_ms=gm_latency_ms,
            )
            turns.append(turn_result)
            total_retries += retry_count

        # Calculate metrics
        success_rate = sum(1 for t in turns if t.allowed) / len(turns) if turns else 0.0
        mean_stall = sum(stall_scores) / len(stall_scores) if stall_scores else 0.0
        sorted_latencies = sorted(latencies)
        p50_idx = int(len(sorted_latencies) * 0.5)
        p95_idx = int(len(sorted_latencies) * 0.95)
        latency_p50 = sorted_latencies[p50_idx] if sorted_latencies else 0.0
        latency_p95 = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)] if sorted_latencies else 0.0

        return RunResult(
            condition=condition,
            scenario=scenario,
            seed=seed,
            inject_enabled=inject_enabled,
            gm_enabled=gm_enabled,
            turns=turns,
            total_retries=total_retries,
            success_rate=success_rate,
            gm_injected_count=gm_injected_count,
            gm_denied_count=gm_denied_count,
            mean_stall_score=mean_stall,
            latency_p50_ms=latency_p50,
            latency_p95_ms=latency_p95,
            timestamp=datetime.now().isoformat(),
        )

    def _load_scenario(self, scenario: str) -> dict:
        """Load scenario from file or return default."""
        # Default kitchen morning scenario
        return {
            "version": "0.1",
            "time": {"label": "朝", "turn": 0},
            "location": {"current": "キッチン", "known": ["キッチン", "リビング"]},
            "characters": {
                "やな": {"status": ["起床済み"], "holding": [], "location": "キッチン"},
                "あゆ": {"status": ["起床済み"], "holding": [], "location": "キッチン"},
            },
            "props": {
                "マグカップ": {"location": "キッチン", "state": ["clean"]},
                "コーヒーメーカー": {"location": "キッチン", "state": ["off"]},
            },
            "events": [],
        }

    def _simulate_output(self, turn: int, speaker: str, seed: int) -> str:
        """Simulate LLM output for testing.

        TODO: Replace with actual LLM call in production.
        """
        # Simple rotation of test outputs
        outputs = [
            "Thought: (朝のキッチン)\nOutput: おはよう、{other}！",
            "Thought: (コーヒー飲みたい)\nOutput: *マグカップを取る* コーヒー淹れようか",
            "Thought: (何食べよう)\nOutput: 今日の朝ごはん何にする？",
            "Thought: (リビング行こうかな)\nOutput: *リビングに移動* ちょっとテレビ見てくるね",
            "Thought: (同意)\nOutput: うん、そうだね",
        ]
        other = "あゆ" if speaker == "やな" else "姉様"
        return outputs[(turn + seed) % len(outputs)].format(other=other)


def generate_report(results: list[RunResult], output_path: Path) -> None:
    """Generate experiment report."""
    report_lines = [
        "# GM 2×2 Experiment Report",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Experiment Matrix",
        "",
        "| Condition | Inject | GM | Description |",
        "|-----------|--------|-----|-------------|",
        "| A | OFF | OFF | Baseline |",
        "| B | ON | OFF | Phase 3.2 |",
        "| C | OFF | ON | GM only |",
        "| D | ON | ON | Full |",
        "",
        "## Summary by Condition",
        "",
        "| Condition | Runs | Success Rate | Retry Rate | GM Denied | Mean Stall | Latency p95 |",
        "|-----------|------|--------------|------------|-----------|------------|-------------|",
    ]

    # Aggregate by condition
    for condition in CONDITIONS:
        cond_results = [r for r in results if r.condition == condition]
        if not cond_results:
            continue

        runs = len(cond_results)
        avg_success = sum(r.success_rate for r in cond_results) / runs
        avg_retry = sum(r.total_retries for r in cond_results) / runs
        total_denied = sum(r.gm_denied_count for r in cond_results)
        avg_stall = sum(r.mean_stall_score for r in cond_results) / runs
        avg_latency = sum(r.latency_p95_ms for r in cond_results) / runs

        report_lines.append(
            f"| {condition} | {runs} | {avg_success:.1%} | {avg_retry:.2f} | "
            f"{total_denied} | {avg_stall:.3f} | {avg_latency:.1f}ms |"
        )

    report_lines.extend([
        "",
        "## GM Metrics (Conditions C, D)",
        "",
    ])

    # GM-specific metrics
    gm_results = [r for r in results if r.gm_enabled]
    if gm_results:
        total_injected = sum(r.gm_injected_count for r in gm_results)
        total_denied = sum(r.gm_denied_count for r in gm_results)
        total_turns = sum(len(r.turns) for r in gm_results)

        report_lines.extend([
            f"- Total GM injections: {total_injected} / {total_turns} turns ({total_injected/total_turns:.1%})",
            f"- Total GM denials: {total_denied} / {total_turns} turns ({total_denied/total_turns:.1%})",
            "",
        ])

    report_lines.extend([
        "## Raw Data",
        "",
        "See accompanying JSON file for detailed results.",
    ])

    # Write report
    report_path = output_path / "REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    logger.info(f"Report written to {report_path}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GM 2×2 Experiment Runner")
    parser.add_argument("--experiment_id", type=str, required=True, help="Experiment ID")
    parser.add_argument("--seeds", type=int, default=10, help="Number of seeds")
    parser.add_argument("--scenarios", type=str, nargs="+", default=["default"], help="Scenario files")
    parser.add_argument("--max_turns", type=int, default=10, help="Max turns per run")
    parser.add_argument("--gm_url", type=str, default="http://localhost:8001", help="GM service URL")
    parser.add_argument("--output_dir", type=str, default="results", help="Output directory")

    args = parser.parse_args()

    config = ExperimentConfig(
        experiment_id=args.experiment_id,
        seeds=list(range(args.seeds)),
        scenarios=args.scenarios,
        max_turns=args.max_turns,
        gm_base_url=args.gm_url,
        output_dir=Path(args.output_dir),
    )

    # Create output directory
    output_path = config.output_dir / f"gm_2x2_{config.experiment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_path.mkdir(parents=True, exist_ok=True)

    # Run experiment
    runner = ExperimentRunner(config)
    results = await runner.run_all()

    # Save results
    results_file = output_path / "results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(
            [
                {
                    "condition": r.condition,
                    "scenario": r.scenario,
                    "seed": r.seed,
                    "inject_enabled": r.inject_enabled,
                    "gm_enabled": r.gm_enabled,
                    "total_retries": r.total_retries,
                    "success_rate": r.success_rate,
                    "gm_injected_count": r.gm_injected_count,
                    "gm_denied_count": r.gm_denied_count,
                    "mean_stall_score": r.mean_stall_score,
                    "latency_p50_ms": r.latency_p50_ms,
                    "latency_p95_ms": r.latency_p95_ms,
                    "timestamp": r.timestamp,
                    "turns": [
                        {
                            "turn_number": t.turn_number,
                            "speaker": t.speaker,
                            "allowed": t.allowed,
                            "denied_reason": t.denied_reason,
                            "stall_score": t.stall_score,
                            "fact_cards": t.fact_cards,
                            "latency_ms": t.latency_ms,
                        }
                        for t in r.turns
                    ],
                }
                for r in results
            ],
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"Results saved to {results_file}")

    # Generate report
    generate_report(results, output_path)

    logger.info(f"Experiment complete. Output: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
