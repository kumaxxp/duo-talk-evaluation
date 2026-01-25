"""GM 2×2 Experiment Runner (GM-010, GM-013).

Runs 2×2 experiment matrix:
- A: Observe + GM OFF (baseline)
- B: Inject + GM OFF (Phase 3.2)
- C: Observe + GM ON (GM only)
- D: Inject + GM ON (full)

GM-013: Real LLM Integration
- --mode sim|real: Switch between simulation and real LLM
- --llm_model: Ollama model name (default: gemma3:12b)
- --llm_url: Ollama API URL (default: http://localhost:11434)
- latency_breakdown: LLM / GM HTTP / total tracking

Usage:
    # Simulation mode (default)
    python -m experiments.gm_2x2_runner \
        --experiment_id exp001 \
        --seeds 10 \
        --max_turns 10

    # Real LLM mode (Ollama)
    python -m experiments.gm_2x2_runner \
        --experiment_id gm013_real \
        --mode real \
        --llm_model gemma3:12b \
        --seeds 2 \
        --max_turns 5
"""

import argparse
import asyncio
import csv
import json
import logging
import subprocess
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from experiments.generators import Generator, create_generator

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

# Profile presets for experiment configuration
PROFILE_CONFIG = {
    "dev": {
        "conditions": ["D"],
        "seeds": 3,
        "max_turns": 6,
        "max_tokens": 192,
    },
    "gate": {
        "conditions": ["B", "D"],
        "seeds": 5,
        "max_turns": 8,
        "max_tokens": 256,
    },
    "full": {
        "conditions": ["A", "B", "C", "D"],
        "seeds": 20,
        "max_turns": 10,
        "max_tokens": 300,
    },
}


# GM-014: Addressing violation detection patterns
import re

# やな should not refer to herself as あゆ, or talk to herself as "姉様"
YANA_VIOLATION_PATTERNS = [
    r"姉様",  # やな calling herself 姉様 is wrong
    r"私はあゆ",  # やな claiming to be あゆ
]

# あゆ should not call やな "あゆ" or refer to herself as "姉"
AYU_VIOLATION_PATTERNS = [
    r"姉様.*あゆ",  # あゆ calling やな by her name directly (rare)
    r"私はやな",  # あゆ claiming to be やな
    r"（姉に向かって）あゆ",  # Addressing やな as あゆ
]


def detect_addressing_violation(speaker: str, speech: str) -> bool:
    """Detect if the speaker is addressing the wrong person (GM-014).

    Args:
        speaker: Current speaker ("やな" or "あゆ")
        speech: Speech content

    Returns:
        True if addressing violation detected
    """
    if not speech:
        return False

    if speaker == "やな":
        for pattern in YANA_VIOLATION_PATTERNS:
            if re.search(pattern, speech):
                return True
    elif speaker == "あゆ":
        for pattern in AYU_VIOLATION_PATTERNS:
            if re.search(pattern, speech):
                return True

    return False


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
    # GM-013: LLM configuration
    mode: str = "sim"  # sim or real
    llm_model: str = "gemma3:12b"
    llm_url: str = "http://localhost:11434"
    max_tokens: int = 300
    # GM-013: Warmup to exclude cold start from latency stats
    warmup_requests: int = 1  # Number of warmup requests per condition
    # Profile support: conditions to run
    conditions: list[str] = field(default_factory=lambda: CONDITIONS.copy())
    profile: str = "dev"  # dev, gate, full
    # Log control
    save_full_logs: bool = False  # If False, only save minimal examples_index.csv
    # Parallel execution
    jobs: int = 1  # Number of concurrent seed runs (1=sequential, >1=parallel)


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
    # Injection trigger tracking
    injection_trigger: Optional[str] = None  # world_delta / deny / stall / format_break
    # GM-013: Move tracking
    has_move_intent: bool = False
    move_validity: Optional[str] = None  # valid / invalid / none
    action_intents: list[str] = field(default_factory=list)  # Intent types detected
    # GM-013: Latency breakdown
    llm_latency_ms: Optional[float] = None
    latency_breakdown: dict[str, float] = field(default_factory=dict)
    # GM-013: Resolution tracking
    resolution_method: Optional[str] = None  # exact / alias / derived / none
    resolved_target: Optional[str] = None  # Canonical prop name
    soft_correction: Optional[str] = None  # Soft correction message
    missing_soft_hard: Optional[str] = None  # soft / hard (for MISSING_OBJECT)
    # GM-014/GM-015: Addressing violation (raw vs final)
    addressing_violation: bool = False  # True if addressing the wrong person (final)
    addressing_violation_raw: bool = False  # GM-015: Before GM intervention
    addressing_violation_final: bool = False  # GM-015: After GM intervention
    # GM-015: Format break tracking
    format_break_type: Optional[str] = None  # Type of format break detected
    repair_method: Optional[str] = None  # Repair method used
    repaired: bool = False  # Whether the output was repaired
    # GM-015: Preflight guidance
    suggest_retry: bool = False  # Whether retry was suggested (after any retry loop)
    guidance_cards: list[str] = field(default_factory=list)  # Preflight guidance hints
    # GM-015: Preflight retry tracking
    preflight_retry_suggested: bool = False  # Whether first GM call suggested retry
    preflight_retry_executed: bool = False  # Whether retry was actually executed


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
    # Extended metrics (GM-011)
    denied_reason_histogram: dict[str, int] = field(default_factory=dict)
    injection_trigger_counts: dict[str, int] = field(default_factory=dict)
    stall_event_count: int = 0  # stall_score > 0.5
    stall_recovery_count: int = 0  # stall後K=2ターン以内にworld_delta非空
    addressing_violations: int = 0  # Total addressing violations (for backward compat)
    addressing_violations_raw: int = 0  # GM-015: Before GM intervention
    addressing_violations_final: int = 0  # GM-015: After GM intervention
    impossible_actions_total: int = 0  # = gm_denied_count (alias)
    # GM-013: Move tracking (exits interpretation)
    move_attempts_total: int = 0
    move_attempts_invalid: int = 0
    move_attempts_valid: int = 0
    move_corrected_within_2_turns: int = 0  # invalid MOVE → valid MOVE within 2 turns
    # GM-013: Creativity vs Hallucination
    soft_creativity_events: int = 0  # allowed but referenced undefined props (descriptive, not action)
    # GM-013: Latency breakdown (p95)
    latency_breakdown_p95: dict[str, float] = field(default_factory=dict)
    # GM-013: missing_object soft/hard classification
    missing_soft_absorbed: int = 0  # alias/derived resolved → allowed
    missing_hard_denied: int = 0  # truly non-existent → denied
    # GM-015: Format break tracking
    format_break_total: int = 0  # Total format breaks detected
    format_repaired_total: int = 0  # Successfully repaired
    format_break_final: int = 0  # Unrepaired format breaks
    format_break_by_type: dict[str, int] = field(default_factory=dict)  # Breakdown by type
    # GM-015: Preflight guidance
    preflight_retry_count: int = 0  # Retry suggestions (deprecated, use preflight_retry_suggested_count)
    preflight_hard_deny_count: int = 0  # Hard denies after budget exhausted
    # GM-015: Preflight retry tracking
    preflight_retry_suggested_count: int = 0  # Turns where first GM call suggested retry
    preflight_retry_executed_count: int = 0  # Turns where retry was actually executed


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

    def __init__(self, config: ExperimentConfig, generator: Optional[Generator] = None):
        self.config = config
        self.gm_client = GMClient(config.gm_base_url)
        # GM-013: Use provided generator or create based on config
        self.generator = generator or create_generator(
            mode=config.mode,
            model=config.llm_model,
            base_url=config.llm_url,
        )

    async def run_all(self) -> list[RunResult]:
        """Run all experiment conditions."""
        results: list[RunResult] = []

        # Use conditions from config (profile-based)
        requested_conditions = self.config.conditions

        # GM-013: Check LLM generator health (for real mode)
        if self.config.mode == "real":
            if not await self.generator.health_check():
                logger.error(f"LLM generator not available: {self.generator.get_model_name()}")
                raise RuntimeError("LLM generator health check failed")
            logger.info(f"LLM generator healthy: {self.generator.get_model_name()}")

        # Check GM health if any GM-enabled conditions
        if any(CONDITION_CONFIG[c]["gm_enabled"] for c in requested_conditions):
            if not await self.gm_client.health_check():
                logger.warning("GM service not available, skipping GM-enabled conditions")
                conditions = [c for c in requested_conditions if not CONDITION_CONFIG[c]["gm_enabled"]]
            else:
                conditions = requested_conditions
                logger.info("GM service healthy")
        else:
            conditions = requested_conditions

        logger.info(f"Profile: {self.config.profile}, Conditions: {conditions}, Jobs: {self.config.jobs}")

        # GM-013: Warmup to exclude cold start latency
        if self.config.mode == "real" and self.config.warmup_requests > 0:
            await self._run_warmup(conditions)

        total_runs = len(conditions) * len(self.config.scenarios) * len(self.config.seeds)

        # Build list of all runs
        all_runs = [
            (condition, scenario, seed)
            for condition in conditions
            for scenario in self.config.scenarios
            for seed in self.config.seeds
        ]

        # Parallel execution with semaphore
        if self.config.jobs > 1:
            semaphore = asyncio.Semaphore(self.config.jobs)
            completed = [0]  # Mutable counter for progress

            async def run_with_semaphore(condition: str, scenario: str, seed: int) -> RunResult:
                async with semaphore:
                    completed[0] += 1
                    logger.info(
                        f"Run {completed[0]}/{total_runs}: "
                        f"condition={condition}, scenario={scenario}, seed={seed}"
                    )
                    return await self.run_single(
                        condition=condition,
                        scenario=scenario,
                        seed=seed
                    )

            tasks = [
                run_with_semaphore(cond, scen, seed)
                for cond, scen, seed in all_runs
            ]
            results = await asyncio.gather(*tasks)
        else:
            # Sequential execution
            results = []
            for i, (condition, scenario, seed) in enumerate(all_runs):
                logger.info(
                    f"Run {i+1}/{total_runs}: "
                    f"condition={condition}, scenario={scenario}, seed={seed}"
                )
                result = await self.run_single(
                    condition=condition,
                    scenario=scenario,
                    seed=seed
                )
                results.append(result)

        await self.gm_client.close()
        return list(results)

    async def _run_warmup(self, conditions: list[str]) -> None:
        """Run warmup requests to exclude cold start from latency stats (GM-013).

        Performs N warmup requests for LLM (and GM if enabled) before actual runs.
        Results are not recorded.
        """
        logger.info(f"Starting warmup ({self.config.warmup_requests} requests)...")

        warmup_scenario = self.config.scenarios[0] if self.config.scenarios else "default"
        world_state = self._load_scenario(warmup_scenario)

        for i in range(self.config.warmup_requests):
            # Warmup LLM
            context = self._build_context_prompt(world_state, [])
            gen_result = await self.generator.generate_turn(
                prompt=context,
                speaker="やな",
                turn_number=0,
                seed=999,  # Fixed seed for warmup
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            logger.info(f"  Warmup LLM {i+1}/{self.config.warmup_requests}: {gen_result.latency_ms:.0f}ms")

            # Warmup GM if any GM-enabled conditions
            if any(CONDITION_CONFIG[c]["gm_enabled"] for c in conditions):
                _, gm_latency = await self.gm_client.step(
                    session_id=f"warmup_{i}",
                    turn_number=0,
                    speaker="やな",
                    raw_output=gen_result.raw_output,
                    world_state=world_state
                )
                await self.gm_client.clear_session(f"warmup_{i}")
                logger.info(f"  Warmup GM {i+1}/{self.config.warmup_requests}: {gm_latency:.1f}ms")

        logger.info("Warmup complete.")

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
        # Extended metrics tracking
        denied_reasons: list[str] = []
        injection_triggers: list[str] = []
        stall_event_count = 0

        # Load scenario
        world_state = self._load_scenario(scenario)

        # Clear GM session
        if gm_enabled:
            await self.gm_client.clear_session(session_id)

        # Simulate dialogue turns
        for turn_number in range(self.config.max_turns):
            speaker = "やな" if turn_number % 2 == 0 else "あゆ"

            # GM-013: Generate LLM output using generator
            start_total = time.perf_counter()

            # Build context prompt
            context = self._build_context_prompt(world_state, turns)
            gen_result = await self.generator.generate_turn(
                prompt=context,
                speaker=speaker,
                turn_number=turn_number,
                seed=seed,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            raw_output = gen_result.raw_output
            llm_latency_ms = gen_result.latency_ms
            latency_breakdown = gen_result.latency_breakdown.copy()

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
                # GM-013: Resolution tracking
                resolution_method = gm_response.get("resolution_method")
                resolved_target = gm_response.get("resolved_target")
                soft_correction = gm_response.get("soft_correction")
                # GM-015: Format break tracking
                format_break_type = gm_response.get("format_break_type", "NONE")
                repair_method = gm_response.get("repair_method", "NONE")
                repaired = gm_response.get("repaired", False)
                # GM-015: Preflight guidance
                suggest_retry = gm_response.get("suggest_retry", False)
                guidance_cards = gm_response.get("guidance_cards", [])

                # GM-015: Track preflight retry suggestion (before retry loop)
                preflight_retry_suggested = suggest_retry
                preflight_retry_executed = False

                # GM-015: Retry loop with guidance injection (max 1 retry per turn)
                if suggest_retry and guidance_cards and retry_count < 1:
                    preflight_retry_executed = True
                    retry_count += 1
                    # Build context with guidance cards injected
                    context_with_guidance = self._build_context_with_guidance(
                        world_state, turns, guidance_cards
                    )
                    # Regenerate LLM output
                    retry_gen_result = await self.generator.generate_turn(
                        prompt=context_with_guidance,
                        speaker=speaker,
                        turn_number=turn_number,
                        seed=seed + 1000,  # Different seed for retry
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                    )
                    raw_output = retry_gen_result.raw_output
                    llm_latency_ms += retry_gen_result.latency_ms

                    # Re-call GM with new output
                    gm_response, retry_gm_latency_ms = await self.gm_client.step(
                        session_id=session_id,
                        turn_number=turn_number,
                        speaker=speaker,
                        raw_output=raw_output,
                        world_state=world_state
                    )
                    gm_latency_ms = (gm_latency_ms or 0) + (retry_gm_latency_ms or 0)

                    # Update all response fields
                    allowed = gm_response["allowed"]
                    denied_reason = gm_response.get("denied_reason")
                    world_delta = gm_response.get("world_delta", [])
                    stall_score = gm_response.get("stall_score", 0.0)
                    fact_cards = gm_response.get("fact_cards", [])
                    parsed = gm_response.get("parsed", {})
                    resolution_method = gm_response.get("resolution_method")
                    resolved_target = gm_response.get("resolved_target")
                    soft_correction = gm_response.get("soft_correction")
                    format_break_type = gm_response.get("format_break_type", "NONE")
                    repair_method = gm_response.get("repair_method", "NONE")
                    repaired = gm_response.get("repaired", False)
                    suggest_retry = gm_response.get("suggest_retry", False)
                    guidance_cards = gm_response.get("guidance_cards", [])

                if not allowed:
                    gm_denied_count += 1
                    if denied_reason:
                        denied_reasons.append(denied_reason)

                # Track injection triggers
                injection_trigger = None
                if fact_cards:
                    gm_injected_count += 1
                    # Determine trigger: world_delta > deny > stall > format_break
                    if world_delta:
                        injection_trigger = "world_delta"
                    elif not allowed:
                        injection_trigger = "deny"
                    elif stall_score > 0.5:
                        injection_trigger = "stall"
                    else:
                        injection_trigger = "format_break"
                    injection_triggers.append(injection_trigger)

                # GM-014: Track stall events only when stall triggers injection
                if injection_trigger == "stall":
                    stall_event_count += 1

                stall_scores.append(stall_score)

                # GM-013: Extract action intents for move tracking
                action_intents = []
                has_move_intent = False
                move_validity = None
                if "action_intents" in parsed:
                    action_intents = [ai.get("intent", "") for ai in parsed.get("action_intents", [])]
                    has_move_intent = "MOVE" in action_intents
                    if has_move_intent:
                        # Determine validity: allowed=True for MOVE means valid
                        if allowed:
                            move_validity = "valid"
                        elif denied_reason in ("OUT_OF_SCOPE", "INVALID_STATE"):
                            move_validity = "invalid"
            else:
                # GM disabled - mock response
                allowed = True
                denied_reason = None
                world_delta = []
                stall_score = 0.0
                fact_cards = []
                parsed = {"thought": None, "speech": raw_output}
                injection_trigger = None
                # GM-013: No move tracking when GM disabled
                action_intents = []
                has_move_intent = False
                move_validity = None
                # GM-013: No resolution tracking when GM disabled
                resolution_method = None
                resolved_target = None
                soft_correction = None
                # GM-015: No format break tracking when GM disabled
                format_break_type = None
                repair_method = None
                repaired = False
                suggest_retry = False
                guidance_cards = []
                # GM-015: No preflight retry tracking when GM disabled
                preflight_retry_suggested = False
                preflight_retry_executed = False

            # GM-013: Classify MISSING_OBJECT as soft/hard
            missing_soft_hard = None
            if denied_reason == "MISSING_OBJECT":
                # If resolution_method indicates an attempt was made, it's HARD
                missing_soft_hard = "hard"
            elif soft_correction and "MISSING_OBJECT" not in str(denied_reason or ""):
                # Action allowed but with soft correction = absorbed
                missing_soft_hard = "soft"

            # GM-013: Calculate total latency and breakdown
            total_latency_ms = (time.perf_counter() - start_total) * 1000
            latency_breakdown["gm_http"] = gm_latency_ms or 0.0
            latency_breakdown["total"] = total_latency_ms
            latencies.append(total_latency_ms)

            # GM-014/GM-015: Detect addressing violation (raw vs final)
            # Raw: Check against raw_output before any GM processing
            addressing_violation_raw = detect_addressing_violation(speaker, raw_output)
            # Final: Check against parsed speech (after GM processing)
            speech_final = parsed.get("speech", "") or raw_output
            addressing_violation_final = detect_addressing_violation(speaker, speech_final)
            # Backward compat: use final as the main flag
            addressing_violation = addressing_violation_final

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
                latency_ms=total_latency_ms,
                gm_latency_ms=gm_latency_ms,
                injection_trigger=injection_trigger,
                # GM-013: Move tracking
                has_move_intent=has_move_intent,
                move_validity=move_validity,
                action_intents=action_intents,
                # GM-013: Latency breakdown
                llm_latency_ms=llm_latency_ms,
                latency_breakdown=latency_breakdown,
                # GM-013: Resolution tracking
                resolution_method=resolution_method,
                resolved_target=resolved_target,
                soft_correction=soft_correction,
                missing_soft_hard=missing_soft_hard,
                # GM-014/GM-015: Addressing violation (raw vs final)
                addressing_violation=addressing_violation,
                addressing_violation_raw=addressing_violation_raw,
                addressing_violation_final=addressing_violation_final,
                # GM-015: Format break tracking
                format_break_type=format_break_type,
                repair_method=repair_method,
                repaired=repaired,
                # GM-015: Preflight guidance
                suggest_retry=suggest_retry,
                guidance_cards=guidance_cards,
                # GM-015: Preflight retry tracking
                preflight_retry_suggested=preflight_retry_suggested,
                preflight_retry_executed=preflight_retry_executed,
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

        # Calculate stall recovery (K=2 window)
        stall_recovery_count = 0
        k_window = 2
        for i, turn in enumerate(turns):
            if turn.stall_score > 0.5:
                # Check if any of the next K turns has world_delta
                for j in range(i + 1, min(i + 1 + k_window, len(turns))):
                    if turns[j].world_delta:
                        stall_recovery_count += 1
                        break

        # GM-013: Calculate move metrics
        move_attempts_total = sum(1 for t in turns if t.has_move_intent)
        move_attempts_invalid = sum(1 for t in turns if t.move_validity == "invalid")
        move_attempts_valid = sum(1 for t in turns if t.move_validity == "valid")

        # GM-013: Calculate move correction within 2 turns
        move_corrected_within_2_turns = 0
        for i, turn in enumerate(turns):
            if turn.move_validity == "invalid":
                # Check if any of the next 2 turns has a valid MOVE
                for j in range(i + 1, min(i + 3, len(turns))):
                    if turns[j].move_validity == "valid":
                        move_corrected_within_2_turns += 1
                        break

        # GM-013: Calculate missing_object soft/hard metrics
        missing_soft_absorbed = sum(1 for t in turns if t.missing_soft_hard == "soft")
        missing_hard_denied = sum(1 for t in turns if t.missing_soft_hard == "hard")

        # GM-014/GM-015: Calculate addressing violations (raw vs final)
        addressing_violations = sum(1 for t in turns if t.addressing_violation)
        addressing_violations_raw = sum(1 for t in turns if t.addressing_violation_raw)
        addressing_violations_final = sum(1 for t in turns if t.addressing_violation_final)

        # GM-013: Calculate latency breakdown p95
        latency_breakdown_p95 = {}
        breakdown_keys = ["llm", "gm_http", "total"]
        for key in breakdown_keys:
            key_latencies = sorted([t.latency_breakdown.get(key, 0) for t in turns if t.latency_breakdown])
            if key_latencies:
                p95_idx = min(int(len(key_latencies) * 0.95), len(key_latencies) - 1)
                latency_breakdown_p95[key] = key_latencies[p95_idx]

        # GM-015: Calculate format break metrics
        format_break_total = sum(1 for t in turns if t.format_break_type and t.format_break_type != "NONE")
        format_repaired_total = sum(1 for t in turns if t.repaired)
        format_break_final = format_break_total - format_repaired_total
        format_break_by_type: Counter[str] = Counter()
        for t in turns:
            if t.format_break_type and t.format_break_type != "NONE":
                format_break_by_type[t.format_break_type] += 1

        # GM-015: Calculate preflight metrics
        preflight_retry_count = sum(1 for t in turns if t.suggest_retry)
        preflight_hard_deny_count = sum(
            1 for t in turns
            if not t.allowed and t.denied_reason and not t.suggest_retry
        )
        # GM-015: Preflight retry tracking
        preflight_retry_suggested_count = sum(1 for t in turns if t.preflight_retry_suggested)
        preflight_retry_executed_count = sum(1 for t in turns if t.preflight_retry_executed)

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
            # Extended metrics (GM-011)
            denied_reason_histogram=dict(Counter(denied_reasons)),
            injection_trigger_counts=dict(Counter(injection_triggers)),
            stall_event_count=stall_event_count,
            stall_recovery_count=stall_recovery_count,
            addressing_violations=addressing_violations,  # GM-014: backward compat
            addressing_violations_raw=addressing_violations_raw,  # GM-015: before GM
            addressing_violations_final=addressing_violations_final,  # GM-015: after GM
            impossible_actions_total=gm_denied_count,
            # GM-013: Move metrics
            move_attempts_total=move_attempts_total,
            move_attempts_invalid=move_attempts_invalid,
            move_attempts_valid=move_attempts_valid,
            move_corrected_within_2_turns=move_corrected_within_2_turns,
            soft_creativity_events=0,  # TBD: Requires prop detection in speech
            # GM-013: Latency breakdown
            latency_breakdown_p95=latency_breakdown_p95,
            # GM-013: missing_object soft/hard
            missing_soft_absorbed=missing_soft_absorbed,
            missing_hard_denied=missing_hard_denied,
            # GM-015: Format break tracking
            format_break_total=format_break_total,
            format_repaired_total=format_repaired_total,
            format_break_final=format_break_final,
            format_break_by_type=dict(format_break_by_type),
            # GM-015: Preflight guidance
            preflight_retry_count=preflight_retry_count,
            preflight_hard_deny_count=preflight_hard_deny_count,
            # GM-015: Preflight retry tracking
            preflight_retry_suggested_count=preflight_retry_suggested_count,
            preflight_retry_executed_count=preflight_retry_executed_count,
        )

    def _load_scenario(self, scenario: str) -> dict:
        """Load scenario from file or return default.

        GM-012: Added 2-room layout with Navigational Affordance.
        - キッチン ⇄ リビング (bidirectional connection)
        """
        # Default kitchen-living morning scenario
        # GM-012: Includes locations with exits for Navigational Affordance
        return {
            "version": "0.1",
            "time": {"label": "朝", "turn": 0},
            "location": {"current": "キッチン"},
            # GM-012: Navigational Affordance - define locations and exits
            "locations": {
                "キッチン": {
                    "description": "朝日が差し込むキッチン",
                    "exits": ["リビング"],
                },
                "リビング": {
                    "description": "広々としたリビングルーム",
                    "exits": ["キッチン"],
                },
            },
            "characters": {
                "やな": {"status": ["起床済み"], "holding": [], "location": "キッチン"},
                "あゆ": {"status": ["起床済み"], "holding": [], "location": "キッチン"},
            },
            "props": {
                "マグカップ": {"location": "キッチン", "state": ["clean"]},
                "コーヒーメーカー": {"location": "キッチン", "state": ["off"]},
                "テレビ": {"location": "リビング", "state": ["off"]},
                "ソファ": {"location": "リビング", "state": ["empty"]},
            },
            "events": [],
        }

    def _build_context_prompt(self, world_state: dict, turns: list[TurnResult]) -> str:
        """Build context prompt for LLM generation (GM-013).

        Args:
            world_state: Current world state
            turns: Previous turn results

        Returns:
            Context string for LLM prompt
        """
        # Current location and time
        location = world_state.get("location", {}).get("current", "不明")
        time_label = world_state.get("time", {}).get("label", "")

        # Available props at location
        props_at_location = []
        for prop_name, prop_data in world_state.get("props", {}).items():
            if prop_data.get("location") == location:
                props_at_location.append(prop_name)

        # Build conversation history (last 5 turns)
        history_lines = []
        for t in turns[-5:]:
            speech = t.parsed_speech or t.raw_output
            history_lines.append(f"{t.speaker}: {speech}")

        context = f"""現在地: {location}
時間: {time_label}
周囲のもの: {', '.join(props_at_location) if props_at_location else 'なし'}

会話履歴:
{chr(10).join(history_lines) if history_lines else '(なし)'}"""

        return context

    def _build_context_with_guidance(
        self,
        world_state: dict,
        turns: list[TurnResult],
        guidance_cards: list[str]
    ) -> str:
        """Build context prompt with GM-015 guidance cards injected.

        Args:
            world_state: Current world state
            turns: Previous turn results
            guidance_cards: GM-015 guidance hints from preflight check

        Returns:
            Context string with guidance appended
        """
        base_context = self._build_context_prompt(world_state, turns)

        # Append guidance as hints
        guidance_section = "\n\n[GM Guidance]\n" + "\n".join(guidance_cards)

        return base_context + guidance_section

    def _simulate_output(self, turn: int, speaker: str, seed: int) -> str:
        """Simulate LLM output for testing.

        DEPRECATED: Use Generator abstraction instead.
        Kept for backward compatibility.
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


def get_git_info() -> dict:
    """Get git information for reproducibility."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        short_sha = sha[:8]

        # Check for dirty state
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        dirty = "-dirty" if status else ""

        return {"sha": sha, "short": f"{short_sha}{dirty}"}
    except Exception:
        return {"sha": "unknown", "short": "unknown"}


def generate_report(
    results: list[RunResult],
    output_path: Path,
    config: Optional["ExperimentConfig"] = None
) -> None:
    """Generate experiment report with extended metrics (GM-011 format)."""
    git_info = get_git_info()

    report_lines = [
        "# GM 2×2 Experiment Report",
        "",
        f"Generated: {datetime.now().isoformat()}",
        f"Git SHA: `{git_info['short']}`",
        "",
    ]

    # Execution Parameters
    if config:
        model_name = config.llm_model if config.mode == "real" else "simulation"
        report_lines.extend([
            "## 実験諸元",
            "",
            "| Parameter | Value |",
            "|-----------|-------|",
            f"| experiment_id | {config.experiment_id} |",
            f"| profile | {config.profile} |",
            f"| conditions | {', '.join(config.conditions)} |",
            f"| mode | {config.mode} |",
            f"| model | {model_name} |",
            f"| seeds | {len(config.seeds)} ({min(config.seeds)}-{max(config.seeds)}) |",
            f"| scenarios | {', '.join(config.scenarios)} |",
            f"| max_turns | {config.max_turns} |",
            f"| temperature | {config.temperature} |",
            f"| max_tokens | {config.max_tokens} |",
            f"| max_retries | {config.max_retries} |",
            f"| gm_base_url | {config.gm_base_url} |",
        ])
        if config.mode == "real":
            report_lines.append(f"| llm_url | {config.llm_url} |")
        report_lines.append("")

    report_lines.extend([
        "## Experiment Matrix",
        "",
        "| Condition | Inject | GM | Description |",
        "|-----------|--------|-----|-------------|",
        "| A | OFF | OFF | Baseline |",
        "| B | ON | OFF | Phase 3.2 |",
        "| C | OFF | ON | GM only |",
        "| D | ON | ON | Full |",
        "",
    ])

    # Calculate stats per condition for 2x2 table
    # Use conditions from config if available, otherwise use global
    active_conditions = config.conditions if config else CONDITIONS
    cond_stats = {}
    for condition in active_conditions:
        cond_results = [r for r in results if r.condition == condition]
        if not cond_results:
            continue

        total_turns = sum(len(r.turns) for r in cond_results)
        total_success = sum(sum(1 for t in r.turns if t.allowed) for r in cond_results)
        total_retries = sum(r.total_retries for r in cond_results)
        total_denied = sum(r.gm_denied_count for r in cond_results)
        total_stall_events = sum(r.stall_event_count for r in cond_results)
        total_stall_recoveries = sum(r.stall_recovery_count for r in cond_results)
        total_injections = sum(r.gm_injected_count for r in cond_results)
        # GM-014/GM-015: Calculate addressing violations (raw vs final)
        total_addressing_violations = sum(r.addressing_violations for r in cond_results)
        total_addressing_violations_raw = sum(r.addressing_violations_raw for r in cond_results)
        total_addressing_violations_final = sum(r.addressing_violations_final for r in cond_results)
        avg_latency_p95 = sum(r.latency_p95_ms for r in cond_results) / len(cond_results)
        avg_latency_p50 = sum(r.latency_p50_ms for r in cond_results) / len(cond_results)

        cond_stats[condition] = {
            "turns": total_turns,
            "success": total_success,
            "success_rate": total_success / total_turns if total_turns else 0,
            "retries": total_retries,
            "retry_rate": total_retries / total_turns if total_turns else 0,
            "denied": total_denied,
            "denied_rate": total_denied / total_turns if total_turns else 0,
            "stall_events": total_stall_events,
            "stall_rate": total_stall_events / total_turns if total_turns else 0,
            "stall_recoveries": total_stall_recoveries,
            "recovery_rate": total_stall_recoveries / total_stall_events if total_stall_events else 0,
            "injections": total_injections,
            "injection_rate": total_injections / total_turns if total_turns else 0,
            # GM-014/GM-015: addressing violations (raw vs final)
            "addressing_violations": total_addressing_violations,
            "addressing_violation_rate": total_addressing_violations / total_turns if total_turns else 0,
            "addressing_violations_raw": total_addressing_violations_raw,
            "addressing_violation_rate_raw": total_addressing_violations_raw / total_turns if total_turns else 0,
            "addressing_violations_final": total_addressing_violations_final,
            "addressing_violation_rate_final": total_addressing_violations_final / total_turns if total_turns else 0,
            "latency_p50": avg_latency_p50,
            "latency_p95": avg_latency_p95,
        }

    # 2×2 Comparison Table (adaptive based on conditions)
    condition_headers = {
        "A": "A (OFF/OFF)",
        "B": "B (ON/OFF)",
        "C": "C (OFF/ON)",
        "D": "D (ON/ON)",
    }
    header_cells = " | ".join(condition_headers.get(c, c) for c in active_conditions)
    separator = " | ".join("-" * 10 for _ in active_conditions)
    report_lines.extend([
        "## 2×2 Results Summary",
        "",
        f"| Metric | {header_cells} |",
        f"|--------|{separator}|",
    ])

    def get_val(cond: str, key: str, fmt: str = ".1%") -> str:
        if cond not in cond_stats:
            return "-"
        val = cond_stats[cond].get(key, 0)
        if fmt == ".1%":
            return f"{val:.1%}"
        elif fmt == ".2f":
            return f"{val:.2f}"
        elif fmt == "d":
            return str(int(val))
        elif fmt == ".1f":
            return f"{val:.1f}"
        return str(val)

    metrics = [
        ("Turns", "turns", "d"),
        ("Success Rate", "success_rate", ".1%"),
        ("Retry Rate", "retry_rate", ".2f"),
        ("addressing_violation_rate_raw", "addressing_violation_rate_raw", ".1%"),  # GM-015
        ("addressing_violation_rate_final", "addressing_violation_rate_final", ".1%"),  # GM-015
        ("impossible_action_rate", "denied_rate", ".1%"),
        ("Stall Event Rate", "stall_rate", ".1%"),
        ("Stall Recovery Rate", "recovery_rate", ".1%"),
        ("GM Intervention Rate", "injection_rate", ".1%"),
        ("Latency p50 (ms)", "latency_p50", ".1f"),
        ("Latency p95 (ms)", "latency_p95", ".1f"),
    ]

    for label, key, fmt in metrics:
        if key is None:
            # TBD metric
            tbd_cells = " | ".join("TBD" for _ in active_conditions)
            report_lines.append(f"| {label} | {tbd_cells} |")
        else:
            vals = [get_val(c, key, fmt) for c in active_conditions]
            val_cells = " | ".join(vals)
            report_lines.append(f"| {label} | {val_cells} |")

    report_lines.append("")

    # GM-specific detailed metrics
    report_lines.extend([
        "## GM Detailed Metrics (Conditions C, D)",
        "",
    ])

    gm_results = [r for r in results if r.gm_enabled]
    if gm_results:
        total_injected = sum(r.gm_injected_count for r in gm_results)
        total_denied = sum(r.gm_denied_count for r in gm_results)
        total_turns = sum(len(r.turns) for r in gm_results)
        total_stall_events = sum(r.stall_event_count for r in gm_results)
        total_stall_recoveries = sum(r.stall_recovery_count for r in gm_results)

        report_lines.extend([
            f"- Total turns: {total_turns}",
            f"- GM injections: {total_injected} ({total_injected/total_turns:.1%})",
            f"- GM denials (impossible_actions): {total_denied} ({total_denied/total_turns:.1%})",
            f"- Stall events: {total_stall_events} ({total_stall_events/total_turns:.1%})",
            f"- Stall recoveries (K=2): {total_stall_recoveries} ({total_stall_recoveries/total_stall_events:.1%})" if total_stall_events else f"- Stall recoveries: {total_stall_recoveries} (N/A)",
            "",
        ])

        # denied_reason histogram (impossible_actions.breakdown)
        all_denied_reasons: Counter[str] = Counter()
        for r in gm_results:
            all_denied_reasons.update(r.denied_reason_histogram)

        if all_denied_reasons:
            report_lines.extend([
                "### impossible_actions.breakdown",
                "",
                "| Reason | Count |",
                "|--------|-------|",
            ])
            for reason, count in all_denied_reasons.most_common():
                report_lines.append(f"| {reason} | {count} |")
            report_lines.append("")

        # injection_trigger counts
        all_triggers: Counter[str] = Counter()
        for r in gm_results:
            all_triggers.update(r.injection_trigger_counts)

        if all_triggers:
            report_lines.extend([
                "### gm_interventions.triggers",
                "",
                "| Trigger | Count |",
                "|---------|-------|",
            ])
            for trigger, count in all_triggers.most_common():
                report_lines.append(f"| {trigger} | {count} |")
            report_lines.append("")

        # GM-013: Move metrics (exits interpretation)
        total_move_attempts = sum(r.move_attempts_total for r in gm_results)
        total_move_invalid = sum(r.move_attempts_invalid for r in gm_results)
        total_move_valid = sum(r.move_attempts_valid for r in gm_results)
        total_move_corrected = sum(r.move_corrected_within_2_turns for r in gm_results)

        if total_move_attempts > 0:
            report_lines.extend([
                "### GM-013: Move Metrics (exits interpretation)",
                "",
                f"- move_attempts_total: {total_move_attempts}",
                f"- move_attempts_valid: {total_move_valid} ({total_move_valid/total_move_attempts:.1%})",
                f"- move_attempts_invalid: {total_move_invalid} ({total_move_invalid/total_move_attempts:.1%})",
                f"- move_corrected_within_2_turns: {total_move_corrected} ({total_move_corrected/total_move_invalid:.1%})" if total_move_invalid else f"- move_corrected_within_2_turns: {total_move_corrected} (N/A)",
                "",
            ])

        # GM-013: Hallucination breakdown (MISSING_OBJECT, NOT_OWNED, CONTRADICTS_WORLD)
        hallucination_reasons = ["MISSING_OBJECT", "NOT_OWNED", "CONTRADICTS_WORLD"]
        hallucination_counts = {r: all_denied_reasons.get(r, 0) for r in hallucination_reasons}
        total_hallucination = sum(hallucination_counts.values())

        if total_hallucination > 0 or any(all_denied_reasons):
            report_lines.extend([
                "### GM-013: Creativity vs Hallucination",
                "",
                "| Type | Count | Rate |",
                "|------|-------|------|",
            ])
            for reason in hallucination_reasons:
                count = hallucination_counts[reason]
                rate = count / total_turns if total_turns else 0
                report_lines.append(f"| {reason} | {count} | {rate:.1%} |")
            report_lines.append(f"| **TOTAL_HALLUCINATION** | {total_hallucination} | {total_hallucination/total_turns:.1%} |")
            report_lines.append("")

        # GM-013: missing_object soft/hard breakdown
        total_soft_absorbed = sum(r.missing_soft_absorbed for r in gm_results)
        total_hard_denied = sum(r.missing_hard_denied for r in gm_results)
        total_missing = total_soft_absorbed + total_hard_denied

        if total_missing > 0 or total_soft_absorbed > 0 or total_hard_denied > 0:
            report_lines.extend([
                "### GM-013: missing_object Resolution",
                "",
                "| Classification | Count | Rate |",
                "|----------------|-------|------|",
                f"| soft_absorbed (alias/derived) | {total_soft_absorbed} | {total_soft_absorbed/total_turns:.1%} |",
                f"| hard_denied (non-existent) | {total_hard_denied} | {total_hard_denied/total_turns:.1%} |",
                f"| **TOTAL** | {total_missing} | {total_missing/total_turns:.1%} |",
                "",
            ])

        # GM-013: resolution_method distribution
        resolution_methods: Counter[str] = Counter()
        for r in gm_results:
            for t in r.turns:
                if t.resolution_method:
                    resolution_methods[t.resolution_method] += 1

        if resolution_methods:
            report_lines.extend([
                "### GM-013: Resolution Method Distribution",
                "",
                "| Method | Count | Rate |",
                "|--------|-------|------|",
            ])
            for method in ["exact", "alias", "derived", "none"]:
                count = resolution_methods.get(method, 0)
                rate = count / total_turns if total_turns else 0
                report_lines.append(f"| {method} | {count} | {rate:.1%} |")
            report_lines.append("")

        # GM-015: Format break metrics
        total_format_break = sum(r.format_break_total for r in gm_results)
        total_repaired = sum(r.format_repaired_total for r in gm_results)
        total_format_break_final = sum(r.format_break_final for r in gm_results)

        if total_format_break > 0:
            report_lines.extend([
                "### GM-015: Format Break Resilience",
                "",
                "| Metric | Count | Rate |",
                "|--------|-------|------|",
                f"| format_break_total | {total_format_break} | {total_format_break/total_turns:.1%} |",
                f"| format_repaired_total | {total_repaired} | {total_repaired/total_turns:.1%} |",
                f"| format_break_final | {total_format_break_final} | {total_format_break_final/total_turns:.1%} |",
                "",
            ])

            # Breakdown by type
            all_break_types: Counter[str] = Counter()
            for r in gm_results:
                all_break_types.update(r.format_break_by_type)

            if all_break_types:
                report_lines.extend([
                    "#### format_break_type breakdown",
                    "",
                    "| Type | Count | Rate |",
                    "|------|-------|------|",
                ])
                for break_type, count in all_break_types.most_common():
                    rate = count / total_turns if total_turns else 0
                    report_lines.append(f"| {break_type} | {count} | {rate:.1%} |")
                report_lines.append("")

        # GM-015: Preflight metrics
        total_preflight_retry = sum(r.preflight_retry_count for r in gm_results)
        total_preflight_hard_deny = sum(r.preflight_hard_deny_count for r in gm_results)
        total_preflight_retry_suggested = sum(r.preflight_retry_suggested_count for r in gm_results)
        total_preflight_retry_executed = sum(r.preflight_retry_executed_count for r in gm_results)

        if total_preflight_retry_suggested > 0 or total_preflight_hard_deny > 0:
            report_lines.extend([
                "### GM-015: Preflight Guidance",
                "",
                "| Metric | Count | Rate |",
                "|--------|-------|------|",
                f"| preflight_retry_suggested | {total_preflight_retry_suggested} | {total_preflight_retry_suggested/total_turns:.1%} |",
                f"| preflight_retry_executed | {total_preflight_retry_executed} | {total_preflight_retry_executed/total_turns:.1%} |",
                f"| preflight_hard_denied | {total_preflight_hard_deny} | {total_preflight_hard_deny/total_turns:.1%} |",
                "",
            ])

    # GM-013: Latency breakdown (for Real mode)
    if config and config.mode == "real":
        report_lines.extend([
            "## GM-013: Latency Breakdown (p95)",
            "",
            "| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |",
            "|-----------|----------|--------------|------------|",
        ])
        for cond in active_conditions:
            cond_results = [r for r in results if r.condition == cond]
            if not cond_results:
                report_lines.append(f"| {cond} | - | - | - |")
                continue

            # Aggregate latency breakdown p95 across runs
            llm_latencies = []
            gm_latencies = []
            total_latencies = []
            for r in cond_results:
                if r.latency_breakdown_p95:
                    llm_latencies.append(r.latency_breakdown_p95.get("llm", 0))
                    gm_latencies.append(r.latency_breakdown_p95.get("gm_http", 0))
                    total_latencies.append(r.latency_breakdown_p95.get("total", 0))

            llm_p95 = sum(llm_latencies) / len(llm_latencies) if llm_latencies else 0
            gm_p95 = sum(gm_latencies) / len(gm_latencies) if gm_latencies else 0
            total_p95 = sum(total_latencies) / len(total_latencies) if total_latencies else 0

            report_lines.append(f"| {cond} | {llm_p95:.1f} | {gm_p95:.1f} | {total_p95:.1f} |")
        report_lines.append("")

    # Analysis section
    report_lines.extend([
        "## 分析",
        "",
        "### C vs A (GM効果)",
        "",
    ])

    if "A" in cond_stats and "C" in cond_stats:
        a, c = cond_stats["A"], cond_stats["C"]
        stall_diff = c["stall_rate"] - a["stall_rate"]
        report_lines.append(f"- Stall Rate: A={a['stall_rate']:.1%} → C={c['stall_rate']:.1%} (diff: {stall_diff:+.1%})")
        report_lines.append(f"- GM Intervention Rate: C={c['injection_rate']:.1%}")
        report_lines.append("")

    report_lines.extend([
        "### B vs A (Inject効果)",
        "",
    ])

    if "A" in cond_stats and "B" in cond_stats:
        a, b = cond_stats["A"], cond_stats["B"]
        report_lines.append(f"- Success Rate: A={a['success_rate']:.1%} → B={b['success_rate']:.1%}")
        report_lines.append("")

    report_lines.extend([
        "### D vs others (相乗効果)",
        "",
    ])

    if "D" in cond_stats:
        d = cond_stats["D"]
        report_lines.append(f"- Success Rate: D={d['success_rate']:.1%}")
        report_lines.append(f"- Latency p95: D={d['latency_p95']:.1f}ms")
        report_lines.append("")

    report_lines.extend([
        "## Raw Data",
        "",
        "See `results.json` for detailed per-run data.",
        "",
        "See `examples_index.csv` for qualitative analysis index.",
    ])

    # Write report
    report_path = output_path / "REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    logger.info(f"Report written to {report_path}")


def _summarize_world_delta(delta: list[dict]) -> str:
    """Summarize world_delta for preview column (GM-012).

    Extracts key operations for fast log tracing.

    Examples:
        [{"op":"replace","path":"/location/current","value":"リビング"}] -> "location→リビング"
        [{"op":"add","path":"/events/-","value":"移動した"}] -> "+event:移動した"
    """
    if not delta:
        return ""

    parts = []
    for op in delta:
        path = op.get("path", "")
        value = op.get("value", "")
        operation = op.get("op", "")

        if "/location/current" in path:
            parts.append(f"loc→{value}")
        elif "/characters/" in path and "/location" in path:
            # Extract character name
            char = path.split("/")[2] if len(path.split("/")) > 2 else "?"
            parts.append(f"{char}→{value}")
        elif "/events/-" in path:
            parts.append(f"+ev:{value[:15]}...")
        elif "/holding" in path:
            if operation == "add":
                parts.append(f"+hold:{value}")
            elif operation == "remove":
                parts.append(f"-hold")
        elif "/props/" in path:
            prop = path.split("/")[2] if len(path.split("/")) > 2 else "?"
            parts.append(f"prop:{prop}")
        else:
            parts.append(f"{operation}:{path[-20:]}")

    return " | ".join(parts[:3])  # Max 3 parts


def generate_examples_index(
    results: list[RunResult],
    output_path: Path,
    config: Optional["ExperimentConfig"] = None
) -> None:
    """Generate CSV index for qualitative analysis (GM-011/GM-012/GM-013 format).

    GM-012: Added preview columns for faster log tracing.
    GM-013: Added move_validity and action tracking columns.

    Log reduction: When config.save_full_logs=False, only save:
    - Failed turns (allowed=False)
    - Turns with GM interventions
    - Turns with addressing violations
    - Turns with format breaks
    """
    rows = []
    save_full = config.save_full_logs if config else True

    for r in results:
        session_id = f"{config.experiment_id if config else 'exp'}_{r.condition}_{r.scenario}_{r.seed}"
        for t in r.turns:
            # Log reduction: skip "boring" turns when not saving full logs
            if not save_full:
                is_interesting = (
                    not t.allowed  # Failed
                    or t.injection_trigger  # GM intervention
                    or t.addressing_violation  # Violation detected
                    or t.format_break_type  # Format break
                    or t.preflight_retry_suggested  # Preflight retry
                    or t.denied_reason  # Denied
                    or t.stall_score > 0.5  # High stall risk
                )
                if not is_interesting:
                    continue
            # Determine trigger (none if no injection)
            trigger = t.injection_trigger or "none"

            # Extract injected tags from fact_cards
            injected_tags = []
            gm_feedback_parts = []
            world_state_parts = []

            for card in t.fact_cards:
                if "世界状態" in card or "WORLD_STATE" in card:
                    injected_tags.append("WORLD_STATE")
                    world_state_parts.append(card)
                if "FACT:" in card:
                    injected_tags.append("GM_FEEDBACK")
                    gm_feedback_parts.append(card.replace("FACT: ", ""))

            # GM-012: Generate preview strings (1-line truncated)
            gm_feedback_preview = " | ".join(gm_feedback_parts)[:80] if gm_feedback_parts else ""
            world_delta_preview = _summarize_world_delta(t.world_delta)[:60] if t.world_delta else ""

            # GM-013: Determine impossible_reason category (hallucination type)
            impossible_reason = ""
            if t.denied_reason in ("MISSING_OBJECT", "NOT_OWNED", "CONTRADICTS_WORLD"):
                impossible_reason = t.denied_reason  # Hallucination indicators

            rows.append({
                "condition": r.condition,
                "seed": r.seed,
                "session_id": session_id,
                "turn_number": t.turn_number,
                "trigger": trigger,
                "denied_reason": t.denied_reason or "",
                "impossible_reason": impossible_reason,  # GM-013: Hallucination tracking
                "move_validity": t.move_validity or "",  # GM-013: exits interpretation
                "has_move_intent": t.has_move_intent,  # GM-013: move tracking
                "stall_score": f"{t.stall_score:.3f}",
                "injected_tags": "|".join(set(injected_tags)) if injected_tags else "",
                "gm_feedback_preview": gm_feedback_preview,  # GM-012: for fast log tracing
                "world_delta_preview": world_delta_preview,  # GM-012: for fast log tracing
                "director_status": "TBD",  # TBD: Director integration
                "speaker": t.speaker,
                "allowed": t.allowed,
                "fact_cards_count": len(t.fact_cards),
                "has_world_delta": len(t.world_delta) > 0,
                "parsed_thought": (t.parsed_thought or "")[:50],
                "parsed_speech": (t.parsed_speech or "")[:50],
                "action_intents": "|".join(t.action_intents) if t.action_intents else "",  # GM-013
                # GM-013: Resolution tracking
                "resolution_method": t.resolution_method or "",
                "resolved_target": t.resolved_target or "",
                "soft_correction_preview": (t.soft_correction or "")[:40],
                "missing_soft_hard": t.missing_soft_hard or "",
                # GM-014/GM-015: Addressing violation (raw vs final)
                "addressing_violation": t.addressing_violation,
                "addressing_violation_raw": t.addressing_violation_raw,
                "addressing_violation_final": t.addressing_violation_final,
                # GM-015: Format break tracking
                "format_break_type": t.format_break_type or "",
                "repair_method": t.repair_method or "",
                "repaired": t.repaired,
                # GM-015: Preflight guidance
                "suggest_retry": t.suggest_retry,
                "guidance_cards_count": len(t.guidance_cards),
                "guidance_preview": (t.guidance_cards[0][:40] if t.guidance_cards else ""),
                # GM-015: Preflight retry tracking
                "preflight_retry_suggested": t.preflight_retry_suggested,
                "preflight_retry_executed": t.preflight_retry_executed,
            })

    # Calculate total turns for logging
    total_turns = sum(len(r.turns) for r in results)

    csv_path = output_path / "examples_index.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    if save_full:
        logger.info(f"Examples index written to {csv_path} ({len(rows)} rows)")
    else:
        logger.info(f"Examples index written to {csv_path} ({len(rows)}/{total_turns} interesting rows)")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GM 2×2 Experiment Runner")
    parser.add_argument("--experiment_id", type=str, required=True, help="Experiment ID")
    # Profile-based configuration
    parser.add_argument("--profile", type=str, default="dev", choices=["dev", "gate", "full"],
                        help="Experiment profile (dev: fast, gate: CI, full: comprehensive)")
    parser.add_argument("--seeds", type=int, default=None,
                        help="Number of seeds (overrides profile default)")
    parser.add_argument("--max_turns", type=int, default=None,
                        help="Max turns per run (overrides profile default)")
    parser.add_argument("--conditions", type=str, nargs="+", default=None,
                        help="Conditions to run (overrides profile default)")
    parser.add_argument("--scenarios", type=str, nargs="+", default=["default"], help="Scenario files")
    parser.add_argument("--gm_url", type=str, default="http://localhost:8001", help="GM service URL")
    parser.add_argument("--output_dir", type=str, default="results", help="Output directory")
    # GM-013: LLM configuration
    parser.add_argument("--mode", type=str, default="sim", choices=["sim", "real"],
                        help="Generation mode: sim (simulation) or real (Ollama)")
    parser.add_argument("--llm_model", type=str, default="gemma3:12b",
                        help="Ollama model name (for real mode)")
    parser.add_argument("--llm_url", type=str, default="http://localhost:11434",
                        help="Ollama API URL (for real mode)")
    parser.add_argument("--max_tokens", type=int, default=None,
                        help="Max tokens for LLM generation (overrides profile default)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Temperature for LLM generation")
    parser.add_argument("--warmup_requests", type=int, default=1,
                        help="Number of warmup requests to exclude cold start latency")
    # Log control
    parser.add_argument("--save_full_logs", action="store_true",
                        help="Save full raw output in results (default: minimal)")
    # Parallel execution
    parser.add_argument("--jobs", type=int, default=1,
                        help="Number of concurrent seed runs (default: 1, max: 4)")

    args = parser.parse_args()

    # Apply profile defaults
    profile = PROFILE_CONFIG[args.profile]
    seeds = args.seeds if args.seeds is not None else profile["seeds"]
    max_turns = args.max_turns if args.max_turns is not None else profile["max_turns"]
    max_tokens = args.max_tokens if args.max_tokens is not None else profile["max_tokens"]
    conditions = args.conditions if args.conditions is not None else profile["conditions"]

    config = ExperimentConfig(
        experiment_id=args.experiment_id,
        seeds=list(range(seeds)),
        scenarios=args.scenarios,
        max_turns=max_turns,
        gm_base_url=args.gm_url,
        output_dir=Path(args.output_dir),
        # GM-013: LLM configuration
        mode=args.mode,
        llm_model=args.llm_model,
        llm_url=args.llm_url,
        max_tokens=max_tokens,
        temperature=args.temperature,
        warmup_requests=args.warmup_requests,
        # Profile settings
        conditions=conditions,
        profile=args.profile,
        save_full_logs=args.save_full_logs,
        # Parallel execution (capped at 4)
        jobs=min(args.jobs, 4),
    )

    logger.info(f"Experiment config: profile={args.profile}, conditions={conditions}, "
                f"seeds={seeds}, max_turns={max_turns}, max_tokens={max_tokens}, jobs={config.jobs}")

    # Create output directory
    output_path = config.output_dir / f"gm_2x2_{config.experiment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_path.mkdir(parents=True, exist_ok=True)

    # Run experiment with wall time tracking
    experiment_start = time.perf_counter()
    runner = ExperimentRunner(config)
    results = await runner.run_all()
    experiment_wall_time = time.perf_counter() - experiment_start

    # Save results with aggregated condition stats (GM-011 format)
    git_info = get_git_info()
    results_file = output_path / "results.json"

    # Aggregate stats by condition
    conditions_stats = {}
    for cond in config.conditions:
        cond_results = [r for r in results if r.condition == cond]
        if not cond_results:
            continue

        total_turns = sum(len(r.turns) for r in cond_results)
        total_success = sum(sum(1 for t in r.turns if t.allowed) for r in cond_results)
        total_retries = sum(r.total_retries for r in cond_results)
        total_denied = sum(r.gm_denied_count for r in cond_results)
        total_stall_events = sum(r.stall_event_count for r in cond_results)
        total_stall_recoveries = sum(r.stall_recovery_count for r in cond_results)
        total_injections = sum(r.gm_injected_count for r in cond_results)

        # Aggregate denied reasons
        all_denied: Counter[str] = Counter()
        for r in cond_results:
            all_denied.update(r.denied_reason_histogram)

        # Aggregate triggers
        all_triggers: Counter[str] = Counter()
        for r in cond_results:
            all_triggers.update(r.injection_trigger_counts)

        # Aggregate latencies
        all_latencies = [t.latency_ms for r in cond_results for t in r.turns]
        sorted_lat = sorted(all_latencies) if all_latencies else [0.0]
        p50_lat = sorted_lat[int(len(sorted_lat) * 0.5)]
        p95_lat = sorted_lat[min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)]

        conditions_stats[cond] = {
            "stats": {
                "turns": total_turns,
                "success": total_success,
                "retries_total": total_retries,
                "addressing_violations": 0,  # TBD: Director integration
                "impossible_actions": {
                    "total": total_denied,
                    "breakdown": dict(all_denied),
                },
                "stall_events": total_stall_events,
                "stall_recoveries": total_stall_recoveries,
                "gm_interventions": {
                    "count": total_injections,
                    "triggers": dict(all_triggers),
                },
                "gm_denied_count": total_denied,
                "latency_ms": {
                    "p50": round(p50_lat, 2),
                    "p95": round(p95_lat, 2),
                },
            },
            "runs": [
                {
                    "scenario": r.scenario,
                    "seed": r.seed,
                    "success_rate": r.success_rate,
                    "total_retries": r.total_retries,
                    "gm_injected_count": r.gm_injected_count,
                    "gm_denied_count": r.gm_denied_count,
                    "stall_event_count": r.stall_event_count,
                    "stall_recovery_count": r.stall_recovery_count,
                    "mean_stall_score": r.mean_stall_score,
                    "latency_p50_ms": r.latency_p50_ms,
                    "latency_p95_ms": r.latency_p95_ms,
                }
                for r in cond_results
            ],
        }

    # GM-013: Determine model name based on mode
    model_name = config.llm_model if config.mode == "real" else "simulation"

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "experiment_id": config.experiment_id,
                "mode": config.mode,
                "model": model_name,
                "seeds": len(config.seeds),
                "max_turns": config.max_turns,
                "metadata": {
                    "git_sha": git_info["sha"],
                    "git_short": git_info["short"],
                    "generated_at": datetime.now().isoformat(),
                    "scenarios": config.scenarios,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "max_retries": config.max_retries,
                    "gm_base_url": config.gm_base_url,
                    "llm_url": config.llm_url if config.mode == "real" else None,
                },
                "conditions": conditions_stats,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"Results saved to {results_file}")

    # Generate report and examples index
    generate_report(results, output_path, config)
    generate_examples_index(results, output_path, config)

    # Calculate and display performance stats
    all_latencies = [t.latency_ms for r in results for t in r.turns]
    total_turns = len(all_latencies)
    if all_latencies:
        sorted_lat = sorted(all_latencies)
        avg_llm_ms = sum(all_latencies) / len(all_latencies)
        p95_llm_ms = sorted_lat[min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)]
        turns_per_sec = total_turns / experiment_wall_time if experiment_wall_time > 0 else 0

        # Estimate full experiment runtime (all 4 conditions, 20 seeds, 10 turns)
        full_total_turns = 4 * 20 * 10  # A/B/C/D × 20 seeds × 10 turns
        current_total_turns = len(conditions) * len(config.seeds) * config.max_turns
        if turns_per_sec > 0:
            estimated_full_runtime_sec = full_total_turns / turns_per_sec
            estimated_full_runtime_min = estimated_full_runtime_sec / 60
        else:
            estimated_full_runtime_min = 0

        logger.info("=" * 60)
        logger.info("Performance Statistics:")
        logger.info(f"  Wall time: {experiment_wall_time:.1f}s ({experiment_wall_time/60:.1f}min)")
        logger.info(f"  Total turns: {total_turns}")
        logger.info(f"  Avg LLM latency: {avg_llm_ms:.1f}ms")
        logger.info(f"  P95 LLM latency: {p95_llm_ms:.1f}ms")
        logger.info(f"  Throughput: {turns_per_sec:.2f} turns/sec")
        logger.info(f"  Estimated full run (4×20×10): {estimated_full_runtime_min:.1f}min")
        logger.info("=" * 60)

    logger.info(f"Experiment complete. Mode: {config.mode}, Model: {model_name}, Output: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
