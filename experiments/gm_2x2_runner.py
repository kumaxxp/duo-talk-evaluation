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
import hashlib
import json
import logging
import subprocess
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from experiments.generators import Generator, create_generator
from experiments.scenario_registry import (
    SchemaValidationError,
    ScenarioRegistry,
    ValidationErrorCode,
    compute_scenario_hash,
    compute_world_hash,
    generate_world_summary,
    validate_scenario_integrity,
    world_state_to_canonical,
)

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

# Profile presets for experiment configuration (GM-016)
# dev: 最速反復（動作確認用）
# gate: PRチェック（統計は荒いが破壊検出向け）
# full: 本番計測（現状と同等）
PROFILE_CONFIG = {
    "dev": {
        "conditions": ["D"],
        "seeds": 1,
        "max_turns": 5,
        "max_tokens": 192,
    },
    "gate": {
        "conditions": ["B", "D"],
        "seeds": 5,
        "max_turns": 10,
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


# GM-020: Marker target extraction patterns (same as output_parser.py)
ACTION_PATTERN = re.compile(r"\*([^*]+)\*")
OBJECT_PATTERNS = [
    re.compile(r"(.+?)を(取|手に取|持|使|置|飲|食)"),
    re.compile(r"(マグカップ|コップ|グラス|カップ|皿|フォーク|スプーン|ナイフ)"),
    re.compile(r"(コーヒー|紅茶|水|ジュース|牛乳|パン|トースト)"),
    re.compile(r"(コーヒーメーカー|電子レンジ|冷蔵庫|テレビ|ドア|窓)"),
    re.compile(r"(ヨーグルト|フルーツ|砂糖|ミルク|バター|ジャム)"),  # GM-020: Extended patterns
]
LOCATION_PATTERNS = [
    re.compile(r"(リビング|キッチン|寝室|玄関|トイレ|浴室|ダイニング)"),
]


def extract_marker_targets(text: str) -> list[str]:
    """Extract action targets from *...* markers only (GM-020).

    This method extracts targets ONLY from text within asterisk markers,
    ignoring natural language mentions. Used for retry success comparison.

    Args:
        text: Text to extract from (typically speech/output)

    Returns:
        List of target names found within *...* markers
    """
    if not text:
        return []

    targets: list[str] = []
    action_texts = ACTION_PATTERN.findall(text)

    for action_text in action_texts:
        # Extract all possible targets from this action text
        for pattern in OBJECT_PATTERNS:
            match = pattern.search(action_text)
            if match:
                target = match.group(1).strip()
                if target and target not in targets:
                    targets.append(target)

        # Also check location patterns for MOVE actions
        for pattern in LOCATION_PATTERNS:
            match = pattern.search(action_text)
            if match:
                target = match.group(1).strip()
                if target and target not in targets:
                    targets.append(target)

    return targets


def extract_available_from_guidance(guidance_cards: list[str]) -> dict[str, list[str]]:
    """Extract available objects/holding/exits from guidance cards (P1a).

    Parses guidance cards to extract the candidate lists that were presented
    to the LLM. Used to check if retry targets are "invented" (not in lists).

    Args:
        guidance_cards: List of guidance card strings

    Returns:
        Dictionary with keys: objects_here, holding, exits
    """
    result = {
        "objects_here": [],
        "holding": [],
        "exits": [],
    }

    if not guidance_cards:
        return result

    # Patterns to extract lists from guidance cards
    objects_pattern = re.compile(r"OBJECTS_HERE:\s*([^\n]+)")
    holding_pattern = re.compile(r"HOLDING:\s*([^\n]+)")
    exits_pattern = re.compile(r"(?:AVAILABLE_)?EXITS:\s*([^\n]+)")

    for card in guidance_cards:
        # Extract OBJECTS_HERE
        match = objects_pattern.search(card)
        if match:
            items_str = match.group(1).strip()
            if items_str and items_str != "(none)":
                # Split by comma and clean up
                items = [item.strip() for item in items_str.split(",")]
                # Remove "(+N more)" suffix if present
                items = [re.sub(r"\s*\(\+\d+ more\)", "", item) for item in items]
                result["objects_here"] = [i for i in items if i]

        # Extract HOLDING
        match = holding_pattern.search(card)
        if match:
            items_str = match.group(1).strip()
            if items_str and items_str != "(none)":
                items = [item.strip() for item in items_str.split(",")]
                items = [re.sub(r"\s*\(\+\d+ more\)", "", item) for item in items]
                result["holding"] = [i for i in items if i]

        # Extract EXITS
        match = exits_pattern.search(card)
        if match:
            items_str = match.group(1).strip()
            if items_str and items_str != "(none)":
                items = [item.strip() for item in items_str.split(",")]
                items = [re.sub(r"\s*\(\+\d+ more\)", "", item) for item in items]
                result["exits"] = [i for i in items if i]

    return result


def normalize_text(text: str) -> str:
    """Normalize text for comparison (P1a improved).

    Applies normalization to handle:
    - Full-width/half-width conversion (NFKC)
    - Lowercase conversion
    - Whitespace stripping
    - Common punctuation removal

    Args:
        text: Text to normalize

    Returns:
        Normalized text for comparison
    """
    if not text:
        return ""
    # NFKC normalization (full-width → half-width, etc.)
    normalized = unicodedata.normalize("NFKC", text)
    # Lowercase
    normalized = normalized.lower()
    # Strip whitespace
    normalized = normalized.strip()
    # Remove common punctuation that might interfere with matching
    for char in ["、", "。", "・", "　", " ", "「", "」", "『", "』"]:
        normalized = normalized.replace(char, "")
    return normalized


@dataclass
class InventedResult:
    """Result of invented object check (P1a improved)."""

    invented: list[str]  # List of invented object names
    reasons: dict[str, str]  # target -> reason mapping
    available_empty: bool  # True if all available lists were empty


def check_invented_objects(
    marker_targets: list[str],
    available: dict[str, list[str]],
) -> list[str]:
    """Check which marker targets are NOT in the available lists (P1a).

    An "invented" object is one that the LLM mentioned in *...* markers
    but was not in the OBJECTS_HERE, HOLDING, or EXITS lists.

    Args:
        marker_targets: Targets extracted from *...* markers
        available: Dictionary from extract_available_from_guidance

    Returns:
        List of invented object names
    """
    result = check_invented_objects_detailed(marker_targets, available)
    return result.invented


def check_invented_objects_detailed(
    marker_targets: list[str],
    available: dict[str, list[str]],
) -> InventedResult:
    """Check which marker targets are NOT in the available lists (P1a improved).

    Enhanced version with normalization and detailed reasons.

    Args:
        marker_targets: Targets extracted from *...* markers
        available: Dictionary from extract_available_from_guidance

    Returns:
        InventedResult with invented objects and reasons
    """
    # Combine all available items first (to check if empty)
    objects_here = available.get("objects_here", [])
    holding = available.get("holding", [])
    exits = available.get("exits", [])
    all_available = objects_here + holding + exits

    # Check if available lists are empty
    available_empty = len(all_available) == 0

    if not marker_targets:
        return InventedResult(invented=[], reasons={}, available_empty=available_empty)

    # Pre-normalize all available items
    normalized_available = {normalize_text(item): item for item in all_available}

    # Find targets not in available lists
    invented = []
    reasons: dict[str, str] = {}

    for target in marker_targets:
        # Skip if target is too short (likely just a verb or particle)
        if len(target) <= 1:
            reasons[target] = "target_too_short"
            continue

        normalized_target = normalize_text(target)

        # Skip if normalized target is empty or too short
        if len(normalized_target) <= 1:
            reasons[target] = "normalized_too_short"
            continue

        # Check exact match first (after normalization)
        if normalized_target in normalized_available:
            reasons[target] = "exact_match"
            continue

        # Check partial match (substring in either direction)
        found = False
        for norm_avail, orig_avail in normalized_available.items():
            if normalized_target in norm_avail or norm_avail in normalized_target:
                found = True
                reasons[target] = f"partial_match:{orig_avail}"
                break

        if not found:
            if target not in invented:
                invented.append(target)
                if available_empty:
                    reasons[target] = "available_lists_empty"
                else:
                    reasons[target] = "no_match_in_available"

    return InventedResult(
        invented=invented,
        reasons=reasons,
        available_empty=available_empty,
    )


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
    # GM-018: Extended format break tracking
    format_break_triggered: bool = False  # True if break_type != NONE or repaired
    repair_steps: int = 0  # 0=none, 1=light, 2+=heavy
    repaired_output: Optional[str] = None  # Text after repair (full)
    parser_error: Optional[str] = None  # Error message if parse failed
    repair_notes: Optional[str] = None  # Short description of repair
    # GM-018: File references for turn_logs
    raw_output_ref: Optional[str] = None  # Path to raw.txt
    repaired_output_ref: Optional[str] = None  # Path to repaired.txt
    parsed_json_ref: Optional[str] = None  # Path to parsed.json
    # GM-015: Preflight guidance
    suggest_retry: bool = False  # Whether retry was suggested (after any retry loop)
    guidance_cards: list[str] = field(default_factory=list)  # Preflight guidance hints
    # GM-015: Preflight retry tracking
    preflight_retry_suggested: bool = False  # Whether first GM call suggested retry
    preflight_retry_executed: bool = False  # Whether retry was actually executed
    # Taste-3: Extended retry tracking
    preflight_triggered: bool = False  # Whether preflight was triggered at all
    guidance_level: int = 0  # 1 or 2 (which retry attempt)
    retry_steps: int = 0  # Number of retry steps executed (0/1/2)
    give_up: bool = False  # Whether GIVE_UP was returned
    silent_correction: bool = False  # Action changed without apology
    silent_correction_failed_reason: Optional[str] = None  # Reason why silent correction failed (e.g., "apology_hit")
    raw_speech: Optional[str] = None  # Speech before retry
    final_speech: Optional[str] = None  # Speech after retry (or same as raw if no retry)
    raw_action_intents: list[str] = field(default_factory=list)  # Action intents before retry
    final_action_intents: list[str] = field(default_factory=list)  # Action intents after retry
    # GM-017: Generation call tracking
    total_generation_calls: int = 1  # Total LLM calls this turn (initial=1, +1 per retry)
    # GM-018: Parse attempts tracking
    parse_attempts: int = 1  # Number of parse attempts (1=first try, 2+=retries)
    # Gate-3: Retry failure classification
    retry_fail_reason: Optional[str] = None  # Reason for retry failure (if retry executed but not allowed)
    # P1 Fix: Retry attempt details for artifact saving
    retry_attempts: list[dict] = field(default_factory=list)  # [{attempt: 1, guidance_cards: [...], context_sent: "...", raw_output: "..."}]
    # GM-020: Detailed retry success metrics
    retry_success_strict: bool = False  # allowed=True && !suggest_retry && !give_up after retry
    retry_success_action: bool = False  # *...* marker targets changed (even if give_up)
    marker_targets_before: list[str] = field(default_factory=list)  # Targets from raw_speech *...*
    marker_targets_after: list[str] = field(default_factory=list)  # Targets from final_speech *...*
    blocked_target_before: Optional[str] = None  # Target that was blocked initially
    blocked_target_after: Optional[str] = None  # Target that was blocked after retry (if any)
    # P1a: Enhanced retry analysis
    available_objects_here: list[str] = field(default_factory=list)  # From guidance cards
    available_holding: list[str] = field(default_factory=list)  # From guidance cards
    available_exits: list[str] = field(default_factory=list)  # From guidance cards
    invented_objects: list[str] = field(default_factory=list)  # Targets NOT in available lists
    invented_reasons: dict[str, str] = field(default_factory=dict)  # target -> reason mapping
    available_lists_empty: bool = False  # True if all available lists were empty
    retry_same_target: bool = False  # True if blocked_target_after == blocked_target_before
    retry_new_missing: bool = False  # True if give_up with different blocked target


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
    # GM-018: Extended format break metrics
    format_break_by_repair_method: dict[str, int] = field(default_factory=dict)  # Breakdown by repair method
    repair_steps_distribution: dict[int, int] = field(default_factory=dict)  # 0/1/2+ counts
    # GM-018: Parse attempts statistics
    parse_attempts_sum: int = 0  # Sum of parse_attempts for avg calculation
    parse_attempts_list: list[int] = field(default_factory=list)  # For p95 calculation
    # GM-015: Preflight guidance
    preflight_retry_count: int = 0  # Retry suggestions (deprecated, use preflight_retry_suggested_count)
    preflight_hard_deny_count: int = 0  # Hard denies after budget exhausted
    # GM-015: Preflight retry tracking
    preflight_retry_suggested_count: int = 0  # Turns where first GM call suggested retry
    preflight_retry_executed_count: int = 0  # Turns where retry was actually executed
    # Taste-3: Extended retry metrics
    preflight_triggered_count: int = 0  # Turns where preflight was triggered
    give_up_count: int = 0  # Turns where GIVE_UP was returned
    silent_correction_count: int = 0  # Turns where action changed without apology
    total_retry_steps: int = 0  # Sum of retry_steps across all turns
    retry_success_count: int = 0  # Retries that resulted in allowed=True
    # Gate-3: Retry failure classification
    retry_fail_count: int = 0  # Retries that did not result in allowed=True
    retry_fail_breakdown: dict[str, int] = field(default_factory=dict)  # Breakdown by fail reason
    # GM-017: Generation call tracking
    total_generation_calls_sum: int = 0  # Sum of total_generation_calls across all turns
    # GM-020: Detailed retry success metrics
    retry_success_strict_count: int = 0  # allowed=True && !suggest_retry && !give_up after retry
    retry_success_action_count: int = 0  # *...* marker targets changed (even if give_up)
    # P1a: Enhanced retry analysis
    retry_same_target_count: int = 0  # Retries where blocked_target_after == blocked_target_before
    retry_new_missing_count: int = 0  # Retries with give_up and different blocked target
    invented_object_count: int = 0  # Turns where invented objects were used
    available_lists_empty_count: int = 0  # Turns where available lists were empty (guidance failed)


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
        # Taste-3: Early stop tracking
        session_give_up_count = 0

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
                # GM-018: Extended format break tracking
                repair_steps = gm_response.get("repair_steps", 0)
                repaired_output = gm_response.get("repaired_output")
                parser_error = gm_response.get("parser_error")
                repair_notes = gm_response.get("repair_notes")
                # GM-018: format_break_triggered = break_type != NONE or repaired
                format_break_triggered = (
                    format_break_type not in (None, "NONE", "") or repaired
                )
                # GM-015: Preflight guidance
                suggest_retry = gm_response.get("suggest_retry", False)
                guidance_cards = gm_response.get("guidance_cards", [])

                # Taste-3: Track initial state before retry loop
                preflight_retry_suggested = suggest_retry
                preflight_retry_executed = False
                preflight_triggered = suggest_retry  # Any suggest_retry means preflight triggered
                guidance_level = 0
                retry_steps = 0
                give_up = False
                # P1 Fix: Save initial guidance_cards (the ones that triggered retry)
                initial_guidance_cards = list(guidance_cards) if suggest_retry else []
                # GM-017: Track total generation calls (initial call = 1)
                total_generation_calls = 1
                raw_speech = parsed.get("speech")  # Save initial speech
                raw_action_intents_list = [
                    intent.get("intent", "") for intent in parsed.get("action_intents", [])
                ] if parsed.get("action_intents") else []

                # Taste-3: Retry loop with guidance injection (max 2 retries per turn)
                # P1 Fix: Track retry attempts for artifact saving
                max_retry_steps = 2
                retry_attempts: list[dict] = []

                while suggest_retry and guidance_cards and retry_count < max_retry_steps:
                    preflight_retry_executed = True
                    retry_count += 1
                    retry_steps += 1
                    guidance_level = retry_count  # 1 or 2

                    # P1 Fix: Assert guidance_cards is non-empty
                    if not guidance_cards:
                        logger.warning(f"Retry skipped: guidance_cards empty at turn {turn_number}")
                        break

                    # Build context with guidance cards injected
                    context_with_guidance = self._build_context_with_guidance(
                        world_state, turns, guidance_cards
                    )

                    # P1 Fix: Record retry attempt details
                    retry_attempt = {
                        "attempt": retry_count,
                        "guidance_cards": list(guidance_cards),
                        "context_sent": context_with_guidance,
                        "has_system_signal": any("<<<SYSTEM_SIGNAL>>>" in card for card in guidance_cards),
                    }

                    # GM-017: Increment generation call count
                    total_generation_calls += 1
                    # Regenerate LLM output
                    retry_gen_result = await self.generator.generate_turn(
                        prompt=context_with_guidance,
                        speaker=speaker,
                        turn_number=turn_number,
                        seed=seed + 1000 * retry_count,  # Different seed for each retry
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                    )
                    raw_output = retry_gen_result.raw_output
                    llm_latency_ms += retry_gen_result.latency_ms

                    # P1 Fix: Complete retry attempt record
                    retry_attempt["raw_output"] = raw_output
                    retry_attempts.append(retry_attempt)

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
                    # GM-018: Extended format break tracking (update on retry)
                    repair_steps = gm_response.get("repair_steps", 0)
                    repaired_output = gm_response.get("repaired_output")
                    parser_error = gm_response.get("parser_error")
                    repair_notes = gm_response.get("repair_notes")
                    format_break_triggered = (
                        format_break_type not in (None, "NONE", "") or repaired
                    )
                    suggest_retry = gm_response.get("suggest_retry", False)
                    guidance_cards = gm_response.get("guidance_cards", [])

                    # Check for GIVE_UP in fact_cards
                    if any("[GIVE_UP]" in card for card in fact_cards):
                        give_up = True
                        break

                    # If no more retry suggested, exit loop
                    if not suggest_retry:
                        break

                # Taste-3: Get final action intents
                final_action_intents_list = [
                    intent.get("intent", "") for intent in parsed.get("action_intents", [])
                ] if parsed.get("action_intents") else []
                final_speech = parsed.get("speech")

                if not allowed:
                    gm_denied_count += 1
                    if denied_reason:
                        denied_reasons.append(denied_reason)

                # Track injection triggers
                injection_trigger = None
                if fact_cards:
                    gm_injected_count += 1
                    # GM-018: Determine trigger correctly
                    # world_delta > deny > stall > format_break (only if actual break) > none
                    if world_delta:
                        injection_trigger = "world_delta"
                    elif not allowed:
                        injection_trigger = "deny"
                    elif stall_score > 0.5:
                        injection_trigger = "stall"
                    elif format_break_triggered:
                        # GM-018: Only set format_break if actual break detected
                        injection_trigger = "format_break"
                    else:
                        # GM-018: Fall-through is now "none" (no specific trigger)
                        injection_trigger = "none"
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
                # GM-018: Extended format break tracking (all None when GM disabled)
                repair_steps = 0
                repaired_output = None
                parser_error = None
                repair_notes = None
                format_break_triggered = False
                suggest_retry = False
                guidance_cards = []
                # P1 Fix: No initial guidance when GM disabled
                initial_guidance_cards = []
                # GM-015: No preflight retry tracking when GM disabled
                preflight_retry_suggested = False
                preflight_retry_executed = False
                # Taste-3: No retry tracking when GM disabled
                preflight_triggered = False
                guidance_level = 0
                retry_steps = 0
                give_up = False
                raw_speech = raw_output
                final_speech = raw_output
                raw_action_intents_list = []
                final_action_intents_list = []
                # GM-017: Only 1 generation call when GM disabled (no retry)
                total_generation_calls = 1
                # P1 Fix: No retry attempts when GM disabled
                retry_attempts = []

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

            # Taste-3: Detect silent correction (action changed without apology)
            silent_correction = False
            silent_correction_failed_reason: Optional[str] = None
            action_changed = False
            has_apology = False
            apology_words = ["すみません", "ごめん", "間違え", "失礼", "申し訳", "ごめんなさい", "すいません"]
            if retry_steps > 0:
                # Check if action changed
                action_changed = set(raw_action_intents_list) != set(final_action_intents_list)
                # Check for apology words in final speech
                has_apology = any(word in (final_speech or "") for word in apology_words)
                if not give_up:
                    silent_correction = action_changed and not has_apology
                    # Track why silent correction failed
                    if action_changed and has_apology:
                        silent_correction_failed_reason = "apology_hit"
                    elif not action_changed:
                        silent_correction_failed_reason = "no_action_change"

            # Gate-3: Classify retry failure reason
            retry_fail_reason: Optional[str] = None
            if preflight_retry_executed and not (allowed and not give_up):
                # Retry was executed but did not result in success
                if give_up:
                    retry_fail_reason = "FAIL_GIVE_UP"
                elif not action_changed:
                    retry_fail_reason = "FAIL_NO_ACTION_CHANGE"
                elif format_break_triggered and not allowed:
                    retry_fail_reason = "FAIL_FORMAT_BREAK"
                elif denied_reason == "MISSING_OBJECT":
                    retry_fail_reason = "FAIL_STILL_MISSING_OBJECT"
                elif denied_reason == "NOT_OWNED":
                    retry_fail_reason = "FAIL_STILL_NOT_OWNED"
                elif denied_reason == "WRONG_LOCATION":
                    retry_fail_reason = "FAIL_STILL_WRONG_LOCATION"
                elif denied_reason in ("OUT_OF_SCOPE", "INVALID_STATE"):
                    retry_fail_reason = "FAIL_STILL_NAV_ERROR"
                elif denied_reason:
                    retry_fail_reason = "FAIL_NEW_ERROR_INTRODUCED"
                else:
                    retry_fail_reason = "FAIL_OTHER"

            # GM-020: Extract marker targets for detailed retry success metrics
            marker_targets_before = extract_marker_targets(raw_speech or "")
            marker_targets_after = extract_marker_targets(final_speech or "")

            # GM-020: Calculate retry_success_strict and retry_success_action
            retry_success_strict = False
            retry_success_action = False
            blocked_target_before: Optional[str] = None
            blocked_target_after: Optional[str] = None

            if preflight_retry_executed:
                # retry_success_strict: allowed=True && !suggest_retry && !give_up
                retry_success_strict = allowed and not suggest_retry and not give_up

                # retry_success_action: *...* marker targets changed
                # Even if give_up, if the targets changed, it's an action success
                retry_success_action = set(marker_targets_before) != set(marker_targets_after)

                # Extract blocked targets from guidance cards (if any)
                # Look for patterns like "Target: ヨーグルト" or "Object: 冷蔵庫"
                if initial_guidance_cards:
                    for card in initial_guidance_cards:
                        # Look for the target mentioned in the guidance
                        for target in marker_targets_before:
                            if target in card:
                                blocked_target_before = target
                                break
                        if blocked_target_before:
                            break

                # Check if retry introduced a new blocked target
                if give_up or (not allowed and denied_reason):
                    for target in marker_targets_after:
                        if target not in marker_targets_before:
                            blocked_target_after = target
                            break

            # P1a: Enhanced retry analysis
            available_objects_here: list[str] = []
            available_holding: list[str] = []
            available_exits: list[str] = []
            invented_objects: list[str] = []
            invented_reasons: dict[str, str] = {}
            available_lists_empty = False
            retry_same_target = False
            retry_new_missing = False

            if preflight_retry_executed and initial_guidance_cards:
                # Extract available lists from guidance cards
                available = extract_available_from_guidance(initial_guidance_cards)
                available_objects_here = available.get("objects_here", [])
                available_holding = available.get("holding", [])
                available_exits = available.get("exits", [])

                # Check for invented objects in final output (detailed version)
                invented_result = check_invented_objects_detailed(marker_targets_after, available)
                invented_objects = invented_result.invented
                invented_reasons = invented_result.reasons
                available_lists_empty = invented_result.available_empty

                # Check retry patterns
                if blocked_target_before and blocked_target_after:
                    retry_same_target = blocked_target_before == blocked_target_after
                if give_up and blocked_target_after and blocked_target_before != blocked_target_after:
                    retry_new_missing = True

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
                # GM-018: Extended format break tracking
                format_break_triggered=format_break_triggered,
                repair_steps=repair_steps,
                repaired_output=repaired_output,
                parser_error=parser_error,
                repair_notes=repair_notes,
                # GM-015: Preflight guidance
                suggest_retry=suggest_retry,
                guidance_cards=initial_guidance_cards,  # P1 Fix: Use initial cards that triggered retry
                # GM-015: Preflight retry tracking
                preflight_retry_suggested=preflight_retry_suggested,
                preflight_retry_executed=preflight_retry_executed,
                # Taste-3: Extended retry tracking
                preflight_triggered=preflight_triggered,
                guidance_level=guidance_level,
                retry_steps=retry_steps,
                give_up=give_up,
                silent_correction=silent_correction,
                silent_correction_failed_reason=silent_correction_failed_reason,
                raw_speech=raw_speech,
                final_speech=final_speech,
                raw_action_intents=raw_action_intents_list,
                final_action_intents=final_action_intents_list,
                # GM-017: Generation call tracking
                total_generation_calls=total_generation_calls,
                # Gate-3: Retry failure classification
                retry_fail_reason=retry_fail_reason,
                # P1 Fix: Retry attempt details
                retry_attempts=retry_attempts,
                # GM-020: Detailed retry success metrics
                retry_success_strict=retry_success_strict,
                retry_success_action=retry_success_action,
                marker_targets_before=marker_targets_before,
                marker_targets_after=marker_targets_after,
                blocked_target_before=blocked_target_before,
                blocked_target_after=blocked_target_after,
                # P1a: Enhanced retry analysis
                available_objects_here=available_objects_here,
                available_holding=available_holding,
                available_exits=available_exits,
                invented_objects=invented_objects,
                invented_reasons=invented_reasons,
                available_lists_empty=available_lists_empty,
                retry_same_target=retry_same_target,
                retry_new_missing=retry_new_missing,
            )
            turns.append(turn_result)
            total_retries += retry_count

            # Taste-3: Early stop - break if give_up count reaches 2
            if give_up:
                session_give_up_count += 1
                if session_give_up_count >= 2:
                    logger.info(f"Early stop: give_up count reached 2 at turn {turn_number}")
                    break

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

        # GM-018: Extended format break metrics
        format_break_by_repair_method: Counter[str] = Counter()
        repair_steps_distribution: Counter[int] = Counter()
        parse_attempts_list: list[int] = []
        for t in turns:
            if t.format_break_triggered:
                if t.repair_method:
                    format_break_by_repair_method[t.repair_method] += 1
                repair_steps_distribution[t.repair_steps] += 1
            # Track all parse_attempts (even for non-break turns)
            parse_attempts_list.append(t.parse_attempts)
        parse_attempts_sum = sum(parse_attempts_list)

        # GM-015: Calculate preflight metrics
        preflight_retry_count = sum(1 for t in turns if t.suggest_retry)
        preflight_hard_deny_count = sum(
            1 for t in turns
            if not t.allowed and t.denied_reason and not t.suggest_retry
        )
        # GM-015: Preflight retry tracking
        preflight_retry_suggested_count = sum(1 for t in turns if t.preflight_retry_suggested)
        preflight_retry_executed_count = sum(1 for t in turns if t.preflight_retry_executed)

        # Taste-3: Calculate extended retry metrics
        preflight_triggered_count = sum(1 for t in turns if t.preflight_triggered)
        give_up_count = sum(1 for t in turns if t.give_up)
        silent_correction_count = sum(1 for t in turns if t.silent_correction)
        total_retry_steps = sum(t.retry_steps for t in turns)
        # Retry success = retry executed and final result is allowed
        retry_success_count = sum(
            1 for t in turns if t.preflight_retry_executed and t.allowed and not t.give_up
        )
        # Gate-3: Retry failure count and breakdown
        retry_fail_count = sum(
            1 for t in turns if t.preflight_retry_executed and not (t.allowed and not t.give_up)
        )
        retry_fail_reasons = [t.retry_fail_reason for t in turns if t.retry_fail_reason]
        retry_fail_breakdown = dict(Counter(retry_fail_reasons))
        # GM-017: Total generation calls sum (for avg_retry_steps_extra calculation)
        total_generation_calls_sum = sum(t.total_generation_calls for t in turns)
        # GM-020: Detailed retry success metrics
        retry_success_strict_count = sum(1 for t in turns if t.retry_success_strict)
        retry_success_action_count = sum(1 for t in turns if t.retry_success_action)
        # P1a: Enhanced retry analysis
        retry_same_target_count = sum(1 for t in turns if t.retry_same_target)
        retry_new_missing_count = sum(1 for t in turns if t.retry_new_missing)
        invented_object_count = sum(1 for t in turns if t.invented_objects)
        available_lists_empty_count = sum(1 for t in turns if t.available_lists_empty)

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
            # GM-018: Extended format break metrics
            format_break_by_repair_method=dict(format_break_by_repair_method),
            repair_steps_distribution=dict(repair_steps_distribution),
            parse_attempts_sum=parse_attempts_sum,
            parse_attempts_list=parse_attempts_list,
            # GM-015: Preflight guidance
            preflight_retry_count=preflight_retry_count,
            preflight_hard_deny_count=preflight_hard_deny_count,
            # GM-015: Preflight retry tracking
            preflight_retry_suggested_count=preflight_retry_suggested_count,
            preflight_retry_executed_count=preflight_retry_executed_count,
            # Taste-3: Extended retry metrics
            preflight_triggered_count=preflight_triggered_count,
            give_up_count=give_up_count,
            silent_correction_count=silent_correction_count,
            total_retry_steps=total_retry_steps,
            retry_success_count=retry_success_count,
            # Gate-3: Retry failure classification
            retry_fail_count=retry_fail_count,
            retry_fail_breakdown=retry_fail_breakdown,
            # GM-017: Generation call tracking
            total_generation_calls_sum=total_generation_calls_sum,
            # GM-020: Detailed retry success metrics
            retry_success_strict_count=retry_success_strict_count,
            retry_success_action_count=retry_success_action_count,
            # P1a: Enhanced retry analysis
            retry_same_target_count=retry_same_target_count,
            retry_new_missing_count=retry_new_missing_count,
            invented_object_count=invented_object_count,
            available_lists_empty_count=available_lists_empty_count,
        )

    def _load_scenario(self, scenario: str) -> dict:
        """Load scenario from file or return default.

        GM-012: Added 2-room layout with Navigational Affordance.
        - キッチン ⇄ リビング (bidirectional connection)

        Taste-3: Support loading scenarios from JSON files.
        """
        # Try to load from file first
        scenario_path = Path(__file__).parent / "scenarios" / f"{scenario}.json"
        if scenario_path.exists():
            with open(scenario_path, encoding="utf-8") as f:
                scenario_data = json.load(f)
            # Convert to world_state format
            return self._convert_scenario_to_world_state(scenario_data)

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

    def _load_scenario_with_meta(self, scenario: str) -> tuple[dict, dict]:
        """Load scenario via Registry and compute metadata (GM-019).

        Uses ScenarioRegistry as single source of truth for scenario resolution.

        Returns:
            (world_state, scenario_meta)

        scenario_meta contains:
            - scenario_id: Scenario identifier
            - scenario_path: Relative path or "default"
            - scenario_resolved_path: Absolute path or "built-in"
            - registry_path: Path to registry.yaml
            - scenario_hash: SHA256 of scenario JSON (16 chars)
            - world_hash: SHA256 of canonical world_state (16 chars)
            - world_summary: {counts, objects_top10, locations}
            - validation_passed: bool
            - validation_errors: list of error codes (if any)

        Raises:
            SchemaValidationError: If scenario_id not in registry or validation fails
        """
        # GM-019: Use ScenarioRegistry for resolution
        registry = ScenarioRegistry()

        # Load scenario via registry (handles mismatch validation)
        scenario_data, base_meta = registry.load_scenario(scenario)

        # Convert to world_state
        if scenario_data is not None:
            world_state = self._convert_scenario_to_world_state(scenario_data)

            # GM-019: Validate scenario integrity
            validation_result = validate_scenario_integrity(scenario_data)
        else:
            # Built-in default scenario
            world_state = self._load_scenario(scenario)
            validation_result = validate_scenario_integrity(None)

        # Compute hashes - GM-019: scenario_hash from scenario, world_hash from WorldState
        try:
            scenario_hash = compute_scenario_hash(scenario_data)
            world_hash = compute_world_hash(world_state)
            world_summary = generate_world_summary(world_state)
            # GM-019: Store canonical JSON for artifact generation
            world_canonical = world_state_to_canonical(world_state)
        except Exception as e:
            raise SchemaValidationError(
                f"Failed to compute hashes for '{scenario}': {e}",
                ValidationErrorCode.HASH_COMPUTATION_ERROR,
                {"scenario": scenario, "error": str(e)},
            ) from e

        # Build scenario_meta with GM-019 fields
        scenario_meta = {
            "scenario_id": scenario,
            "scenario_path": base_meta["scenario_path"],
            "scenario_resolved_path": base_meta["scenario_resolved_path"],
            "registry_path": base_meta["registry_path"],
            "scenario_hash": scenario_hash,
            "world_hash": world_hash,
            "world_summary": world_summary,
            "world_canonical": world_canonical,  # GM-019: for artifact storage
            "validation_passed": validation_result.passed,
            "validation_errors": validation_result.error_codes,
            "tags": base_meta.get("tags", []),
            "description": base_meta.get("description", ""),
        }

        return world_state, scenario_meta

    def _convert_scenario_to_world_state(self, scenario_data: dict) -> dict:
        """Convert scenario JSON to world_state format (Taste-3).

        Args:
            scenario_data: Scenario JSON loaded from file

        Returns:
            World state dict compatible with GM service
        """
        locations = scenario_data.get("locations", {})
        characters = scenario_data.get("characters", {})
        time_of_day = scenario_data.get("time_of_day", "morning")

        # Build location data with exits
        location_dict = {}
        for loc_name, loc_data in locations.items():
            location_dict[loc_name] = {
                "description": loc_data.get("description", loc_name),
                "exits": loc_data.get("exits", []),
            }

        # Build character data
        character_dict = {}
        for char_name, char_data in characters.items():
            character_dict[char_name] = {
                "status": ["起床済み"],
                "holding": char_data.get("holding", []),
                "location": char_data.get("location", "キッチン"),
            }

        # Build props - collect from all locations
        props_dict = {}
        for loc_name, loc_data in locations.items():
            for prop_name in loc_data.get("props", []):
                props_dict[prop_name] = {
                    "location": loc_name,
                    "state": ["default"],
                }

        # Get current location (first character's location)
        current_location = "キッチン"
        if characters:
            first_char = list(characters.values())[0]
            current_location = first_char.get("location", "キッチン")

        # Time label mapping
        time_labels = {
            "morning": "朝",
            "afternoon": "昼",
            "evening": "夕方",
            "night": "夜",
        }

        return {
            "version": "0.1",
            "time": {"label": time_labels.get(time_of_day, "朝"), "turn": 0},
            "location": {"current": current_location},
            "locations": location_dict,
            "characters": character_dict,
            "props": props_dict,
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


async def fetch_gm_version(gm_base_url: str) -> Optional[dict]:
    """Fetch GM service version info for experiment reproducibility.

    Args:
        gm_base_url: GM service URL (e.g., http://localhost:8001)

    Returns:
        Version info dict or None if unavailable
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{gm_base_url}/version")
            if response.status_code == 200:
                version_info = response.json()
                logger.info(f"GM version: git_sha={version_info.get('git_sha', 'unknown')}, "
                           f"prompt_version={version_info.get('prompt_version', 'unknown')}")
                return version_info
            else:
                logger.warning(f"GM /version returned {response.status_code}")
                return None
    except httpx.TimeoutException:
        logger.warning("GM /version timed out")
        return None
    except httpx.ConnectError:
        logger.error("Cannot connect to GM service - is it running?")
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch GM version: {e}")
        return None


def _truncate_with_ends(text: str, head: int = 300, tail: int = 100) -> str:
    """Truncate text showing first N and last M chars with ellipsis (GM-018).

    Args:
        text: Text to truncate
        head: Number of chars to show from beginning
        tail: Number of chars to show from end

    Returns:
        Truncated text with "..." in middle if needed
    """
    if not text:
        return ""
    if len(text) <= head + tail + 10:  # +10 for "..." buffer
        return text
    return f"{text[:head]}...{text[-tail:]}"


def _collect_format_break_examples(
    gm_results: list[RunResult],
    max_examples: int = 3  # GM-018+1: Changed from 5 to 3
) -> list[dict]:
    """Collect format break examples for the report (GM-018+1).

    Prioritizes (as per spec):
    1. Higher repair_steps (desc)
    2. break_type (for grouping)
    3. Failed repairs first

    Returns:
        List of example dicts with RAW/REPAIRED previews (first 240 chars) and file refs
    """
    examples = []

    for r in gm_results:
        for t in r.turns:
            if not t.format_break_triggered:
                continue

            raw_text = t.raw_output or ""
            repaired_text = t.repaired_output or ""

            examples.append({
                "condition": r.condition,
                "seed": r.seed,
                "speaker": t.speaker,  # GM-018+1: Added
                "turn": t.turn_number,
                "break_type": t.format_break_type or "UNKNOWN",
                "repair_method": t.repair_method or "NONE",
                "repair_steps": t.repair_steps,
                "parse_attempts": t.parse_attempts,
                "repaired": t.repaired,
                "parser_error": t.parser_error,
                "repair_notes": t.repair_notes,
                # GM-018+1: Show first 240 chars (spec says 240)
                "raw_snippet": raw_text[:240] if raw_text else "",
                "raw_length": len(raw_text),
                "repaired_snippet": repaired_text[:240] if repaired_text else None,
                "repaired_length": len(repaired_text) if repaired_text else 0,
                "final_speech": t.parsed_speech,
                "final_action": "|".join(t.final_action_intents) if t.final_action_intents else "|".join(t.action_intents) if t.action_intents else None,
                # GM-018+1: File refs for artifacts
                "raw_output_ref": t.raw_output_ref,
                "repaired_output_ref": t.repaired_output_ref,
                "parsed_json_ref": t.parsed_json_ref,
            })

    # Sort by: repair_steps desc, then by break_type, then by not repaired (failed first)
    examples.sort(key=lambda x: (-x["repair_steps"], x["break_type"], x["repaired"]))

    return examples[:max_examples]


def generate_report(
    results: list[RunResult],
    output_path: Path,
    config: Optional["ExperimentConfig"] = None,
    scenarios_meta: Optional[dict[str, dict]] = None,
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

    # GM-018+1: run_meta section for reproducibility
    if scenarios_meta:
        report_lines.extend([
            "## run_meta (GM-018+1)",
            "",
        ])
        for scenario_id, meta in scenarios_meta.items():
            report_lines.extend([
                f"### Scenario: `{scenario_id}`",
                "",
                "| Key | Value |",
                "|-----|-------|",
                f"| scenario_path | `{meta.get('scenario_path', '-')}` |",
                f"| scenario_hash | `{meta.get('scenario_hash', '-')}` |",
                f"| world_hash | `{meta.get('world_hash', '-')}` |",
            ])
            summary = meta.get("world_summary", {})
            counts = summary.get("counts", {})
            report_lines.append(f"| locations | {counts.get('locations', 0)} |")
            report_lines.append(f"| objects | {counts.get('objects', 0)} |")
            report_lines.append(f"| characters | {counts.get('characters', 0)} |")
            objects_list = summary.get("objects_top10", [])
            if objects_list:
                report_lines.append(f"| objects_top10 | {', '.join(objects_list)} |")
            locations_list = summary.get("locations", [])
            if locations_list:
                report_lines.append(f"| location_names | {', '.join(locations_list)} |")
            report_lines.append("")
        report_lines.append("")

    report_lines.extend([
        "## 用語定義 (GM-018+1)",
        "",
        "| 用語 | 定義 |",
        "|------|------|",
        "| **gm_injection** | fact_cardsを付与した（毎ターンで発生しうる） |",
        "| **gm_intervention** | 何かを変えた/止めた/直した（format repair, deny, retry, stall suggestion等） |",
        "| **trigger** | interventionの契機（world_delta / deny / stall / format_break / none） |",
        "| **repair_steps** | 適用したrepair transformの段数（0=なし, 1=STRIP, 2=TRAILING_CUT等, 3+=FALLBACK） |",
        "| **parse_attempts** | パース試行回数 = `1 + repair_steps`（初回=1, repair1回→2, repair2回→3…） |",
        "",
        "- `trigger=none` は「何もしなかった」を意味する",
        "- `gm_injection` は `gm_intervention` の一部ではない（独立した概念）",
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

        # GM-015 + GM-018: Format break metrics
        total_format_break = sum(r.format_break_total for r in gm_results)
        total_repaired = sum(r.format_repaired_total for r in gm_results)
        total_format_break_final = sum(r.format_break_final for r in gm_results)

        if total_format_break > 0:
            # Calculate repair success rate
            repair_success_rate = total_repaired / total_format_break if total_format_break else 0
            repair_failure_rate = total_format_break_final / total_format_break if total_format_break else 0

            report_lines.extend([
                "### GM-015/GM-018: Format Break Resilience",
                "",
                "| Metric | Count | Rate |",
                "|--------|-------|------|",
                f"| format_break_total | {total_format_break} | {total_format_break/total_turns:.1%} |",
                f"| format_repaired_total | {total_repaired} | {total_repaired/total_turns:.1%} |",
                f"| format_break_final | {total_format_break_final} | {total_format_break_final/total_turns:.1%} |",
                f"| **修復成功率** | - | {repair_success_rate:.1%} |",
                f"| **修復不能率** | - | {repair_failure_rate:.1%} |",
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

            # GM-018: Breakdown by repair_method
            all_repair_methods: Counter[str] = Counter()
            for r in gm_results:
                all_repair_methods.update(r.format_break_by_repair_method)

            if all_repair_methods:
                report_lines.extend([
                    "#### repair_method breakdown",
                    "",
                    "| Method | Count | Rate |",
                    "|--------|-------|------|",
                ])
                for method, count in all_repair_methods.most_common():
                    rate = count / total_format_break if total_format_break else 0
                    report_lines.append(f"| {method} | {count} | {rate:.1%} |")
                report_lines.append("")

            # GM-018: repair_steps distribution
            all_repair_steps: Counter[int] = Counter()
            for r in gm_results:
                all_repair_steps.update(r.repair_steps_distribution)

            if all_repair_steps:
                report_lines.extend([
                    "#### repair_steps distribution",
                    "",
                    "| Steps | Count | Rate | Meaning |",
                    "|-------|-------|------|---------|",
                ])
                for steps in sorted(all_repair_steps.keys()):
                    count = all_repair_steps[steps]
                    rate = count / total_format_break if total_format_break else 0
                    meaning = "none" if steps == 0 else "light" if steps == 1 else "medium" if steps == 2 else "heavy"
                    report_lines.append(f"| {steps} | {count} | {rate:.1%} | {meaning} |")
                report_lines.append("")

            # GM-018: parse_attempts statistics
            all_parse_attempts: list[int] = []
            for r in gm_results:
                all_parse_attempts.extend(r.parse_attempts_list)

            if all_parse_attempts:
                avg_parse = sum(all_parse_attempts) / len(all_parse_attempts)
                sorted_attempts = sorted(all_parse_attempts)
                p95_idx = min(int(len(sorted_attempts) * 0.95), len(sorted_attempts) - 1)
                p95_parse = sorted_attempts[p95_idx]
                max_parse = max(all_parse_attempts)

                report_lines.extend([
                    "#### parse_attempts statistics",
                    "",
                    f"- **avg_parse_attempts**: {avg_parse:.2f}",
                    f"- **p95_parse_attempts**: {p95_parse}",
                    f"- **max_parse_attempts**: {max_parse}",
                    "",
                ])

            # GM-018+1: FormatBreak Examples section (max 3)
            format_break_examples = _collect_format_break_examples(gm_results, max_examples=3)
            report_lines.extend([
                "#### FormatBreak Examples",
                "",
            ])
            if not format_break_examples:
                report_lines.extend([
                    "**0件** - フォーマット破損は検出されませんでした。",
                    "",
                ])
            else:
                for i, ex in enumerate(format_break_examples, 1):
                    report_lines.extend([
                        f"##### Case {i}: cond={ex['condition']} seed={ex['seed']} turn={ex['turn']} speaker={ex['speaker']}",
                        "",
                        f"- **break_type**: `{ex['break_type']}`",
                        f"- **repair_method**: `{ex['repair_method']}`",
                        f"- **repair_steps**: {ex['repair_steps']}",
                        f"- **parse_attempts**: {ex['parse_attempts']}",
                        f"- **parser_error**: {ex['parser_error'] or '-'}",
                        f"- **repair_notes**: {ex['repair_notes'] or '-'}",
                        "",
                        f"**RAW** ({ex['raw_length']} chars, first 240):",
                        "```",
                        ex['raw_snippet'],
                        "```",
                        "",
                    ])
                    if ex.get('repaired_snippet'):
                        report_lines.extend([
                            f"**REPAIRED** ({ex['repaired_length']} chars, first 240):",
                            "```",
                            ex['repaired_snippet'],
                            "```",
                            "",
                        ])
                    report_lines.extend([
                        f"**FINAL SPEECH:** {ex['final_speech'] or '-'}",
                        "",
                        f"**FINAL ACTION:** {ex['final_action'] or '-'}",
                        "",
                    ])
                    # GM-018+1: File refs
                    if ex.get('raw_output_ref'):
                        report_lines.append(f"📁 `{ex['raw_output_ref']}`")
                    if ex.get('repaired_output_ref'):
                        report_lines.append(f"📁 `{ex['repaired_output_ref']}`")
                    if ex.get('parsed_json_ref'):
                        report_lines.append(f"📁 `{ex['parsed_json_ref']}`")
                    report_lines.extend(["", "---", ""])

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

    # Taste-3: Retry/Give-up Metrics
    total_preflight_triggered = sum(r.preflight_triggered_count for r in results)
    total_retry_steps = sum(r.total_retry_steps for r in results)
    total_retry_success = sum(r.retry_success_count for r in results)
    total_give_up = sum(r.give_up_count for r in results)
    total_silent_correction = sum(r.silent_correction_count for r in results)
    total_turns_all = sum(len(r.turns) for r in results)
    total_executed = sum(r.preflight_retry_executed_count for r in results)
    # GM-017: Total generation calls (for retry_steps_extra)
    total_generation_calls_sum = sum(r.total_generation_calls_sum for r in results)
    # retry_steps_extra = total_generation_calls - total_turns (extra calls beyond initial)
    total_retry_steps_extra = total_generation_calls_sum - total_turns_all

    if total_preflight_triggered > 0:
        retry_success_rate = total_retry_success / total_executed if total_executed > 0 else 0
        avg_retry_steps = total_retry_steps / total_preflight_triggered if total_preflight_triggered > 0 else 0
        give_up_rate = total_give_up / total_turns_all if total_turns_all > 0 else 0
        # GM-017: Average retry_steps_extra per turn
        avg_retry_steps_extra = total_retry_steps_extra / total_turns_all if total_turns_all > 0 else 0

        # Determine color indicators
        retry_success_color = "🟢" if retry_success_rate >= 0.8 else "🟡" if retry_success_rate >= 0.5 else "🔴"
        avg_steps_color = "🟢" if avg_retry_steps < 1.5 else "🟡" if avg_retry_steps < 2.0 else "🔴"
        give_up_color = "🟢" if give_up_rate < 0.1 else "🟡" if give_up_rate < 0.2 else "🔴"
        # GM-017: avg_retry_steps_extra color (target <0.3, warn <0.5, red >=0.5)
        avg_extra_color = "🟢" if avg_retry_steps_extra < 0.3 else "🟡" if avg_retry_steps_extra < 0.5 else "🔴"

        report_lines.extend([
            "## Taste-3: Retry/Give-up Metrics",
            "",
            "| Metric | Value | Status |",
            "|--------|-------|--------|",
            f"| preflight_triggered | {total_preflight_triggered} | - |",
            f"| preflight_retry_executed | {total_executed} | - |",
            f"| retry_success_rate | {retry_success_rate:.1%} | {retry_success_color} (>80% target) |",
            f"| avg_retry_steps | {avg_retry_steps:.2f} | {avg_steps_color} (<1.5 target) |",
            f"| avg_retry_steps_extra | {avg_retry_steps_extra:.2f} | {avg_extra_color} (<0.3 target) |",
            f"| give_up_count | {total_give_up} | - |",
            f"| give_up_rate | {give_up_rate:.1%} | {give_up_color} (<10% target, >=20% red) |",
            f"| silent_correction_count | {total_silent_correction} | - |",
            "",
        ])

    # Gate-3 Summary (consolidated view for gate testing)
    if total_preflight_triggered > 0 or gm_results:
        total_gen_calls = sum(r.total_generation_calls_sum for r in results)
        total_turns_for_gate = sum(len(r.turns) for r in results)
        retry_steps_extra_total = total_gen_calls - total_turns_for_gate
        avg_retry_steps_extra_gate = retry_steps_extra_total / total_turns_for_gate if total_turns_for_gate > 0 else 0

        # Calculate retry counts for Gate-3 (suggested/executed/success/fail)
        retry_suggested_total = sum(r.preflight_retry_suggested_count for r in results)
        retry_executed_total = sum(r.preflight_retry_executed_count for r in results)
        retry_success_total = sum(r.retry_success_count for r in results)
        retry_fail_total = sum(r.retry_fail_count for r in results)
        retry_success_rate_gate = retry_success_total / retry_executed_total if retry_executed_total > 0 else 1.0

        give_up_total = sum(r.give_up_count for r in results)
        give_up_rate_gate = give_up_total / total_turns_for_gate if total_turns_for_gate > 0 else 0

        silent_correction_total = sum(r.silent_correction_count for r in results)
        silent_correction_rate = silent_correction_total / total_turns_for_gate if total_turns_for_gate > 0 else 0

        # Collect preflight reasons breakdown
        preflight_reasons: Counter[str] = Counter()
        for r in results:
            preflight_reasons.update(r.denied_reason_histogram)

        # Gate-3: Collect retry failure breakdown
        retry_fail_breakdown_total: Counter[str] = Counter()
        for r in results:
            retry_fail_breakdown_total.update(r.retry_fail_breakdown)

        # Gate-3: Collect total_generation_calls distribution (0=error/1=no retry/2=1 retry/3=2 retries)
        gen_calls_distribution: Counter[int] = Counter()
        for r in results:
            for t in r.turns:
                gen_calls_distribution[t.total_generation_calls] += 1

        # Gate-3A (P0) pass/fail status - Safety metrics
        hard_denied_count = sum(r.preflight_hard_deny_count for r in results)
        extra_pass = avg_retry_steps_extra_gate < 0.5
        give_up_pass = give_up_rate_gate < 0.1
        hard_deny_pass = hard_denied_count == 0
        crash_count = 0  # Assumed 0 if we got this far
        crash_pass = crash_count == 0
        gate3a_pass = extra_pass and give_up_pass and hard_deny_pass and crash_pass

        # Gate-3B (P1) pass/fail status - Quality metrics
        retry_pass = retry_success_rate_gate > 0.8
        silent_correction_pass = silent_correction_rate > 0.5
        gate3b_pass = retry_pass and silent_correction_pass

        gate3a_status = "✅ PASS" if gate3a_pass else "❌ FAIL"
        gate3b_status = "✅ PASS" if gate3b_pass else "❌ FAIL (P1)"
        extra_icon = "✅" if extra_pass else "❌"
        give_up_icon = "✅" if give_up_pass else "❌"
        hard_deny_icon = "✅" if hard_deny_pass else "❌"
        crash_icon = "✅" if crash_pass else "❌"
        retry_icon = "✅" if retry_pass else "❌"
        silent_icon = "✅" if silent_correction_pass else "❌"

        report_lines.extend([
            "## Gate-3A Summary (P0必須：安全性)",
            "",
            f"**Gate-3A Status: {gate3a_status}**",
            "",
            "Gate-3A はP0ブロッカー。FAILの場合はリリース不可。",
            "",
            "| Metric | Value | Target | Status |",
            "|--------|-------|--------|--------|",
            f"| give_up_rate | {give_up_rate_gate:.1%} | <10% | {give_up_icon} |",
            f"| avg_retry_steps_extra | {avg_retry_steps_extra_gate:.2f} | <0.5 | {extra_icon} |",
            f"| hard_denied_count | {hard_denied_count} | =0 | {hard_deny_icon} |",
            f"| GM Crash | {crash_count} | =0 | {crash_icon} |",
            "",
            "---",
            "",
            "## Gate-3B Summary (P1参考：品質向上)",
            "",
            f"**Gate-3B Status: {gate3b_status}**",
            "",
            "Gate-3B はP1 Backlog。FAILでもP0リリースはブロックしない。",
            "",
            "| Metric | Value | Target | Status |",
            "|--------|-------|--------|--------|",
            f"| retry_success_rate | {retry_success_rate_gate:.1%} | >80% | {retry_icon} |",
            f"| silent_correction_rate | {silent_correction_rate:.1%} | >50% | {silent_icon} |",
            "",
            "---",
            "",
            "### Retry Metrics Detail",
            "",
            "| Metric | Count | Note |",
            "|--------|-------|------|",
            f"| retry_suggested_total | {retry_suggested_total} | First GM call suggested retry |",
            f"| retry_executed_total | {retry_executed_total} | Retries actually executed |",
            f"| retry_success_total | {retry_success_total} | Resulted in allowed=True |",
            f"| retry_fail_total | {retry_fail_total} | Did not result in allowed=True |",
            "",
            "### GM-020: Detailed Retry Success Metrics",
            "",
        ])

        # GM-020: Calculate detailed retry success metrics
        retry_success_strict_total = sum(r.retry_success_strict_count for r in results)
        retry_success_action_total = sum(r.retry_success_action_count for r in results)
        retry_success_strict_rate = retry_success_strict_total / retry_executed_total if retry_executed_total > 0 else 0
        retry_success_action_rate = retry_success_action_total / retry_executed_total if retry_executed_total > 0 else 0

        strict_icon = "✅" if retry_success_strict_rate >= 0.8 else "🟡" if retry_success_strict_rate >= 0.5 else "❌"
        action_icon = "✅" if retry_success_action_rate >= 0.8 else "🟡" if retry_success_action_rate >= 0.5 else "❌"

        report_lines.extend([
            "| Metric | Count | Rate | Status |",
            "|--------|-------|------|--------|",
            f"| retry_success_strict | {retry_success_strict_total} | {retry_success_strict_rate:.1%} | {strict_icon} (allowed=True & no give_up) |",
            f"| retry_success_action | {retry_success_action_total} | {retry_success_action_rate:.1%} | {action_icon} (*...* targets changed) |",
            "",
        ])

        # P1a: Enhanced retry analysis - invented object tracking
        retry_same_target_total = sum(r.retry_same_target_count for r in results)
        retry_new_missing_total = sum(r.retry_new_missing_count for r in results)
        invented_object_total = sum(r.invented_object_count for r in results)
        available_lists_empty_total = sum(r.available_lists_empty_count for r in results)
        retry_same_target_rate = retry_same_target_total / retry_executed_total if retry_executed_total > 0 else 0
        retry_new_missing_rate = retry_new_missing_total / retry_executed_total if retry_executed_total > 0 else 0
        invented_object_rate = invented_object_total / total_turns_for_gate if total_turns_for_gate > 0 else 0
        available_lists_empty_rate = available_lists_empty_total / retry_executed_total if retry_executed_total > 0 else 0

        # Icon: low = good (not repeating same target or inventing objects)
        same_target_icon = "✅" if retry_same_target_rate <= 0.2 else "🟡" if retry_same_target_rate <= 0.5 else "❌"
        new_missing_icon = "✅" if retry_new_missing_rate <= 0.2 else "🟡" if retry_new_missing_rate <= 0.5 else "❌"
        invented_icon = "✅" if invented_object_rate <= 0.05 else "🟡" if invented_object_rate <= 0.1 else "❌"
        empty_icon = "✅" if available_lists_empty_rate <= 0.1 else "🟡" if available_lists_empty_rate <= 0.3 else "❌"

        report_lines.extend([
            "### P1a: Invented Object Analysis",
            "",
            "| Metric | Count | Rate | Status |",
            "|--------|-------|------|--------|",
            f"| retry_same_target | {retry_same_target_total} | {retry_same_target_rate:.1%} | {same_target_icon} (blocked target repeated) |",
            f"| retry_new_missing | {retry_new_missing_total} | {retry_new_missing_rate:.1%} | {new_missing_icon} (give_up with different target) |",
            f"| invented_objects | {invented_object_total} | {invented_object_rate:.1%} | {invented_icon} (targets not in AVAILABLE_*) |",
            f"| available_lists_empty | {available_lists_empty_total} | {available_lists_empty_rate:.1%} | {empty_icon} (guidance had no candidates) |",
            "",
        ])

        # P1a: Scenario breakdown
        scenario_p1a_stats: dict[str, dict] = {}
        for r in results:
            if r.scenario not in scenario_p1a_stats:
                scenario_p1a_stats[r.scenario] = {
                    "turns": 0,
                    "retry_executed": 0,
                    "invented_objects": 0,
                    "retry_new_missing": 0,
                    "give_up": 0,
                }
            stats = scenario_p1a_stats[r.scenario]
            stats["turns"] += len(r.turns)
            stats["retry_executed"] += r.preflight_retry_executed_count
            stats["invented_objects"] += r.invented_object_count
            stats["retry_new_missing"] += r.retry_new_missing_count
            stats["give_up"] += r.give_up_count

        if len(scenario_p1a_stats) > 1:
            report_lines.extend([
                "### P1a: Scenario Breakdown",
                "",
                "| Scenario | Turns | Retry | Invented | NewMissing | GiveUp |",
                "|----------|-------|-------|----------|------------|--------|",
            ])
            for scenario_name, stats in sorted(scenario_p1a_stats.items()):
                turns = stats["turns"]
                retry_exec = stats["retry_executed"]
                invented = stats["invented_objects"]
                new_missing = stats["retry_new_missing"]
                give_up = stats["give_up"]
                invented_r = f"{invented/turns:.1%}" if turns > 0 else "-"
                new_missing_r = f"{new_missing/retry_exec:.1%}" if retry_exec > 0 else "-"
                give_up_r = f"{give_up/turns:.1%}" if turns > 0 else "-"
                report_lines.append(
                    f"| {scenario_name} | {turns} | {retry_exec} | {invented} ({invented_r}) | {new_missing} ({new_missing_r}) | {give_up} ({give_up_r}) |"
                )
            report_lines.append("")

        report_lines.extend([
            "### Generation Calls Distribution",
            "",
            "| gen_calls | Count | Rate |",
            "|-----------|-------|------|",
        ])
        for calls in sorted(gen_calls_distribution.keys()):
            count = gen_calls_distribution[calls]
            rate = count / total_turns_for_gate if total_turns_for_gate > 0 else 0
            report_lines.append(f"| {calls} | {count} | {rate:.1%} |")
        report_lines.append("")

        # Retry failure breakdown (Top 5)
        if retry_fail_breakdown_total:
            report_lines.extend([
                "### Retry Failure Breakdown (Top 5)",
                "",
                "| Reason | Count |",
                "|--------|-------|",
            ])
            for reason, count in retry_fail_breakdown_total.most_common(5):
                report_lines.append(f"| {reason} | {count} |")
            report_lines.append("")
        else:
            report_lines.extend([
                "### Retry Failure Breakdown",
                "",
                "No retry failures recorded.",
                "",
            ])

        # Format break summary
        total_fb = sum(r.format_break_total for r in results)
        total_repaired = sum(r.format_repaired_total for r in results)
        report_lines.extend([
            "### Format Break Summary",
            "",
            f"- **format_break_total**: {total_fb}",
            f"- **repaired_total**: {total_repaired}",
        ])

        # Break type breakdown
        all_break_types: Counter[str] = Counter()
        for r in results:
            all_break_types.update(r.format_break_by_type)
        if all_break_types:
            top_types = [f"{t}({c})" for t, c in all_break_types.most_common(3)]
            report_lines.append(f"- **top_break_types**: {', '.join(top_types)}")
        report_lines.append("")

        # Preflight reasons breakdown
        if preflight_reasons:
            report_lines.extend([
                "### top_preflight_reasons",
                "",
                "| Reason | Count |",
                "|--------|-------|",
            ])
            for reason, count in preflight_reasons.most_common(5):
                report_lines.append(f"| {reason} | {count} |")
            report_lines.append("")

        # Per-scenario breakdown
        if scenarios_meta:
            report_lines.extend([
                "### Scenario Hashes (GM-019)",
                "",
                "| scenario_id | scenario_hash | world_hash |",
                "|-------------|---------------|------------|",
            ])
            for sid, meta in scenarios_meta.items():
                report_lines.append(
                    f"| {sid} | `{meta.get('scenario_hash', '-')[:8]}` | `{meta.get('world_hash', '-')[:8]}` |"
                )
            report_lines.append("")

    # Gate-3: Extract retry failure examples (up to 3 per scenario)
    retry_failure_examples: list[dict] = []
    for r in results:
        for t in r.turns:
            if t.retry_fail_reason and len(retry_failure_examples) < 9:  # Max 9 examples (3 per scenario type)
                retry_failure_examples.append({
                    "scenario": r.scenario,
                    "turn": t.turn_number,
                    "speaker": t.speaker,
                    "fail_reason": t.retry_fail_reason,
                    "denied_reason": t.denied_reason,
                    "raw_speech": (t.raw_speech or "")[:100],
                    "final_speech": (t.final_speech or "")[:100],
                    "guidance_cards": t.guidance_cards[:1] if t.guidance_cards else [],
                    "raw_output": (t.raw_output or "")[:200],
                    "action_changed": set(t.raw_action_intents) != set(t.final_action_intents),
                    # GM-020: Marker targets for detailed analysis
                    "marker_targets_before": t.marker_targets_before,
                    "marker_targets_after": t.marker_targets_after,
                    "retry_success_action": t.retry_success_action,
                    "blocked_target_before": t.blocked_target_before,
                    "blocked_target_after": t.blocked_target_after,
                    # P1a: Available lists and invented objects
                    "available_objects_here": t.available_objects_here,
                    "available_holding": t.available_holding,
                    "available_exits": t.available_exits,
                    "invented_objects": t.invented_objects,
                    "invented_reasons": t.invented_reasons,
                    "available_lists_empty": t.available_lists_empty,
                    "retry_same_target": t.retry_same_target,
                    "retry_new_missing": t.retry_new_missing,
                })

    if retry_failure_examples:
        report_lines.extend([
            "## Retry Failure Examples",
            "",
            "Detailed examples of retry failures for analysis.",
            "",
        ])
        for i, ex in enumerate(retry_failure_examples[:6], 1):  # Show max 6
            targets_before = ", ".join(ex.get('marker_targets_before', [])) or "(none)"
            targets_after = ", ".join(ex.get('marker_targets_after', [])) or "(none)"
            action_success_icon = "✅" if ex.get('retry_success_action') else "❌"

            # P1a: Format invented objects and available lists
            invented_list = ", ".join(ex.get('invented_objects', [])) or "(none)"
            available_objects = ", ".join(ex.get('available_objects_here', [])) or "(none)"
            available_holding = ", ".join(ex.get('available_holding', [])) or "(none)"
            available_exits = ", ".join(ex.get('available_exits', [])) or "(none)"
            same_target_icon = "🔁" if ex.get('retry_same_target') else ""
            new_missing_icon = "🆕" if ex.get('retry_new_missing') else ""

            report_lines.extend([
                f"### Example {i}: {ex['scenario']} Turn {ex['turn']}",
                "",
                f"- **Fail Reason**: `{ex['fail_reason']}`",
                f"- **Denied Reason**: `{ex['denied_reason']}`",
                f"- **Speaker**: {ex['speaker']}",
                f"- **Action Changed (intent)**: {ex['action_changed']}",
                f"- **Action Changed (*...*)**: {action_success_icon} (`{targets_before}` → `{targets_after}`)",
                f"- **Blocked Target**: `{ex.get('blocked_target_before', 'N/A')}` → `{ex.get('blocked_target_after', 'N/A')}` {same_target_icon}{new_missing_icon}",
                "",
                "**P1a: Available Lists & Invented Objects**:",
                f"- OBJECTS_HERE: {available_objects}",
                f"- HOLDING: {available_holding}",
                f"- EXITS: {available_exits}",
                f"- **Invented**: {invented_list}",
                f"- **Reasons**: {ex.get('invented_reasons', {})}",
                f"- **Available Empty**: {'⚠️ Yes' if ex.get('available_lists_empty') else 'No'}",
                "",
                "**Guidance Card** (truncated):",
                "```",
                ex['guidance_cards'][0][:300] if ex['guidance_cards'] else "(none)",
                "```",
                "",
                "**Raw Output** (truncated):",
                "```",
                ex['raw_output'],
                "```",
                "",
                "**Raw Speech**: " + ex['raw_speech'],
                "",
                "**Final Speech**: " + ex['final_speech'],
                "",
                "---",
                "",
            ])

    report_lines.extend([
        "## Raw Data",
        "",
        "See `results.json` for detailed per-run data.",
        "",
        "See `examples_index.csv` for qualitative analysis index.",
        "",
        "See `CONVERSATION_REPORT.md` for turn-by-turn conversation analysis.",
    ])

    # Write report
    report_path = output_path / "REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    logger.info(f"Report written to {report_path}")


def generate_conversation_report(
    results: list[RunResult],
    output_path: Path,
    config: Optional["ExperimentConfig"] = None,
    scenarios_meta: Optional[dict[str, dict]] = None,
) -> None:
    """Generate CONVERSATION_REPORT.md with turn-by-turn conversation analysis.

    Shows:
    - raw_speech / final_speech
    - guidance_cards (if any)
    - total_generation_calls
    - silent_correction detection
    - format_break info
    """
    # Apology words for detection (JP)
    apology_words = ["すみません", "ごめん", "間違え", "失礼", "申し訳", "ごめんなさい", "すいません"]

    report_lines = [
        "# Conversation Report (Gate-3 Analysis)",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
    ]

    for r in results:
        session_id = f"{config.experiment_id if config else 'exp'}_{r.condition}_{r.scenario}_{r.seed}"
        report_lines.extend([
            f"## Session: {session_id}",
            "",
            f"- **Condition**: {r.condition}",
            f"- **Scenario**: {r.scenario}",
            f"- **Seed**: {r.seed}",
            "",
        ])

        # Scenario meta if available
        if scenarios_meta and r.scenario in scenarios_meta:
            meta = scenarios_meta[r.scenario]
            report_lines.append(f"- **scenario_hash**: `{meta.get('scenario_hash', '-')}`")
            report_lines.append(f"- **world_hash**: `{meta.get('world_hash', '-')}`")
            report_lines.append("")

        report_lines.extend([
            "| Turn | Speaker | raw_speech | final_speech | guidance | gen_calls | silent_corr | apology | format_break |",
            "|------|---------|------------|--------------|----------|-----------|-------------|---------|--------------|",
        ])

        for t in r.turns:
            # Truncate speeches for table
            raw_sp = (t.raw_speech or t.parsed_speech or "")[:40].replace("|", "\\|").replace("\n", " ")
            final_sp = (t.final_speech or t.parsed_speech or "")[:40].replace("|", "\\|").replace("\n", " ")

            # Guidance summary
            guidance = ", ".join(t.guidance_cards[:2]) if t.guidance_cards else "-"
            guidance = guidance[:30].replace("|", "\\|")

            # Apology detection
            has_apology = any(w in (t.final_speech or "") for w in apology_words)
            apology_str = "⚠️" if has_apology else "-"

            # Silent correction
            silent_str = "✅" if t.silent_correction else "-"

            # Format break
            fb_str = t.format_break_type if t.format_break_triggered else "-"

            report_lines.append(
                f"| {t.turn_number} | {t.speaker} | {raw_sp} | {final_sp} | {guidance} | {t.total_generation_calls} | {silent_str} | {apology_str} | {fb_str} |"
            )

        report_lines.append("")

        # Detailed examples for interesting turns
        interesting_turns = [t for t in r.turns if t.silent_correction or t.format_break_triggered or t.total_generation_calls > 1]
        if interesting_turns:
            report_lines.extend([
                "### Detailed Turn Analysis",
                "",
            ])
            for t in interesting_turns[:3]:  # Max 3 examples per session
                report_lines.extend([
                    f"#### Turn {t.turn_number}: {t.speaker}",
                    "",
                ])

                # Raw vs Final speech comparison
                if t.raw_speech and t.final_speech and t.raw_speech != t.final_speech:
                    report_lines.extend([
                        "**Speech Change (raw → final):**",
                        f"- RAW: {t.raw_speech[:100]}",
                        f"- FINAL: {t.final_speech[:100]}",
                        "",
                    ])

                # Action intents change
                if t.raw_action_intents != t.final_action_intents:
                    report_lines.extend([
                        "**Action Change:**",
                        f"- RAW intents: {t.raw_action_intents}",
                        f"- FINAL intents: {t.final_action_intents}",
                        "",
                    ])

                # Guidance cards
                if t.guidance_cards:
                    report_lines.extend([
                        "**Guidance Cards:**",
                    ])
                    for card in t.guidance_cards:
                        report_lines.append(f"- {card}")
                    report_lines.append("")

                # Format break details
                if t.format_break_triggered:
                    report_lines.extend([
                        "**Format Break:**",
                        f"- Type: {t.format_break_type}",
                        f"- Repair Method: {t.repair_method}",
                        f"- Repair Steps: {t.repair_steps}",
                        "",
                    ])

                # Silent correction analysis
                has_apology = any(w in (t.final_speech or "") for w in apology_words)
                report_lines.extend([
                    "**Silent Correction Analysis:**",
                    f"- silent_correction: {t.silent_correction}",
                    f"- total_generation_calls: {t.total_generation_calls}",
                    f"- apology_detected: {has_apology}",
                    "",
                    "---",
                    "",
                ])

        report_lines.append("")

    # Write report
    report_path = output_path / "CONVERSATION_REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    logger.info(f"Conversation report written to {report_path}")


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
                "format_break": t.format_break_triggered,  # GM-018: Alias for convenience
                "break_type": t.format_break_type or "",  # GM-018: Renamed for clarity
                "format_break_type": t.format_break_type or "",  # Keep for backward compat
                "repair_method": t.repair_method or "",
                "repaired": t.repaired,
                # GM-018: Extended format break tracking
                "format_break_triggered": t.format_break_triggered,
                "repair_steps": t.repair_steps,
                "parse_attempts": t.parse_attempts,  # GM-018: How many parse attempts
                "parser_error": (t.parser_error or "")[:50],
                "repair_notes": t.repair_notes or "",
                "raw_output_ref": t.raw_output_ref or "",
                "repaired_output_ref": t.repaired_output_ref or "",
                "parsed_json_ref": t.parsed_json_ref or "",
                # GM-015: Preflight guidance
                "suggest_retry": t.suggest_retry,
                "guidance_cards_count": len(t.guidance_cards),
                "guidance_preview": (t.guidance_cards[0][:40] if t.guidance_cards else ""),
                # GM-015: Preflight retry tracking
                "preflight_retry_suggested": t.preflight_retry_suggested,
                "preflight_retry_executed": t.preflight_retry_executed,
                # Taste-3: Extended retry tracking
                "preflight_triggered": t.preflight_triggered,
                "guidance_level": t.guidance_level,
                "retry_steps": t.retry_steps,
                "give_up": t.give_up,
                "silent_correction": t.silent_correction,
                "raw_speech": (t.raw_speech or "")[:50],
                "final_speech": (t.final_speech or "")[:50],
                "raw_action_intents": "|".join(t.raw_action_intents) if t.raw_action_intents else "",
                "final_action_intents": "|".join(t.final_action_intents) if t.final_action_intents else "",
                # GM-017: Generation call tracking
                "total_generation_calls": t.total_generation_calls,
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


def generate_turns_log(
    results: list[RunResult],
    output_path: Path,
    config: Optional["ExperimentConfig"] = None,
    scenarios_meta: Optional[dict[str, dict]] = None,
) -> None:
    """Generate detailed turns log JSON for conversation reports.

    Saves full Thought/Output without truncation.
    GM-018+1: Includes scenario_hash and world_hash per turn.
    """
    turns_data = []

    for r in results:
        session_id = f"{config.experiment_id if config else 'exp'}_{r.condition}_{r.scenario}_{r.seed}"
        # GM-018+1: Get scenario meta for this run
        scenario_meta = scenarios_meta.get(r.scenario, {}) if scenarios_meta else {}
        for t in r.turns:
            turns_data.append({
                "condition": r.condition,
                "scenario": r.scenario,
                "seed": r.seed,
                "session_id": session_id,
                # GM-018+1: run_meta fields
                "scenario_hash": scenario_meta.get("scenario_hash"),
                "world_hash": scenario_meta.get("world_hash"),
                "turn_number": t.turn_number,
                "speaker": t.speaker,
                # Full content (not truncated)
                "parsed_thought": t.parsed_thought,
                "parsed_speech": t.parsed_speech,
                "raw_output": t.raw_output,
                # Action tracking
                "action_intents": t.action_intents,
                "raw_action_intents": t.raw_action_intents,
                "final_action_intents": t.final_action_intents,
                # GM status
                "allowed": t.allowed,
                "denied_reason": t.denied_reason,
                "injection_trigger": t.injection_trigger,
                "fact_cards": t.fact_cards,
                "world_delta": t.world_delta,
                # Preflight
                "preflight_triggered": t.preflight_triggered,
                "guidance_level": t.guidance_level,
                "retry_steps": t.retry_steps,
                "give_up": t.give_up,
                "silent_correction": t.silent_correction,
                "guidance_cards": t.guidance_cards,
                "total_generation_calls": t.total_generation_calls,
                # Full speech before/after retry
                "raw_speech": t.raw_speech,
                "final_speech": t.final_speech,
                # Latency
                "latency_ms": t.latency_ms,
                "llm_latency_ms": t.llm_latency_ms,
                "gm_latency_ms": t.gm_latency_ms,
                # GM-018: Format break details (full, not truncated)
                "format_break_triggered": t.format_break_triggered,
                "format_break_type": t.format_break_type,
                "repair_method": t.repair_method,
                "repaired": t.repaired,
                "repair_steps": t.repair_steps,
                "repaired_output": t.repaired_output,  # Full repaired text
                "parser_error": t.parser_error,
                "repair_notes": t.repair_notes,
                "parse_attempts": t.parse_attempts,
                # GM-018: Resolution tracking
                "resolution_method": t.resolution_method,
                "resolved_target": t.resolved_target,
                "soft_correction": t.soft_correction,
                # GM-020: Detailed retry success metrics
                "marker_targets_before": t.marker_targets_before,
                "marker_targets_after": t.marker_targets_after,
                "retry_success_strict": t.retry_success_strict,
                "retry_success_action": t.retry_success_action,
                "blocked_target_before": t.blocked_target_before,
                "blocked_target_after": t.blocked_target_after,
                # P1a: Invented object analysis
                "available_objects_here": t.available_objects_here,
                "available_holding": t.available_holding,
                "available_exits": t.available_exits,
                "invented_objects": t.invented_objects,
                "invented_reasons": t.invented_reasons,
                "available_lists_empty": t.available_lists_empty,
                "retry_same_target": t.retry_same_target,
                "retry_new_missing": t.retry_new_missing,
            })

    log_path = output_path / "turns_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(turns_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Turns log written to {log_path} ({len(turns_data)} turns)")


def generate_turn_logs_files(
    results: list[RunResult],
    output_path: Path,
    config: Optional["ExperimentConfig"] = None,
    scenarios_meta: Optional[dict[str, dict]] = None,
) -> dict[str, dict]:
    """Generate artifacts/ directory with raw/repaired/parsed files (GM-018+1, GM-019).

    Creates per-turn files:
    - artifacts/turn_{turn:03d}_raw_output.txt   <- ALWAYS saved (complete original)
    - artifacts/turn_{turn:03d}_repaired_output.txt <- Only when repaired=True
    - artifacts/turn_{turn:03d}_parsed.json      <- Always saved (parse result)

    Creates per-session files (GM-019):
    - artifacts/{session_id}/world_canonical.json <- Canonical world state for reproducibility

    The directory structure is: artifacts/{session_id}/

    Returns:
        Dict mapping turn_key to file paths (for updating TurnResult refs)
    """
    artifacts_dir = output_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    file_refs: dict[str, dict] = {}  # turn_key -> {raw_ref, repaired_ref, parsed_ref}
    total_turns = 0
    format_break_count = 0
    saved_world_canonicals: set[str] = set()  # Track which scenarios already saved

    for r in results:
        session_id = f"{config.experiment_id if config else 'exp'}_{r.condition}_{r.scenario}_{r.seed}"
        session_dir = artifacts_dir / session_id
        session_dir.mkdir(exist_ok=True)

        # GM-019: Save world_canonical.json per session (once per scenario)
        if scenarios_meta and r.scenario not in saved_world_canonicals:
            scenario_meta = scenarios_meta.get(r.scenario, {})
            world_canonical = scenario_meta.get("world_canonical")
            if world_canonical:
                canonical_file = session_dir / "world_canonical.json"
                with open(canonical_file, "w", encoding="utf-8") as f:
                    # Write as formatted JSON for readability
                    canonical_dict = json.loads(world_canonical)
                    json.dump(canonical_dict, f, ensure_ascii=False, indent=2)
                saved_world_canonicals.add(r.scenario)

        for t in r.turns:
            total_turns += 1
            turn_key = f"{session_id}_turn_{t.turn_number:03d}"

            refs: dict[str, Optional[str]] = {}

            # 1. ALWAYS save raw output (complete, no truncation) - GM-018+1 requirement
            raw_file = session_dir / f"turn_{t.turn_number:03d}_raw_output.txt"
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(t.raw_output or "")
            refs["raw_output_ref"] = f"artifacts/{session_id}/turn_{t.turn_number:03d}_raw_output.txt"
            # Also update the TurnResult
            t.raw_output_ref = refs["raw_output_ref"]

            # 2. Save repaired output ONLY when repaired=True - GM-018+1 requirement
            if t.repaired and t.repaired_output:
                format_break_count += 1
                repaired_file = session_dir / f"turn_{t.turn_number:03d}_repaired_output.txt"
                with open(repaired_file, "w", encoding="utf-8") as f:
                    f.write(t.repaired_output)
                refs["repaired_output_ref"] = f"artifacts/{session_id}/turn_{t.turn_number:03d}_repaired_output.txt"
                t.repaired_output_ref = refs["repaired_output_ref"]
            else:
                refs["repaired_output_ref"] = None

            # 3. ALWAYS save parsed JSON (parse result metadata)
            parsed_data = {
                "turn_number": t.turn_number,
                "speaker": t.speaker,
                "thought": t.parsed_thought,
                "speech": t.parsed_speech,
                "action_intents": t.action_intents,
                "raw_action_intents": t.raw_action_intents,
                "final_action_intents": t.final_action_intents,
                # Format break metadata
                "format_break_triggered": t.format_break_triggered,
                "break_type": t.format_break_type,
                "repair_method": t.repair_method,
                "repair_steps": t.repair_steps,
                "parse_attempts": t.parse_attempts,
                "repaired": t.repaired,
                "parser_error": t.parser_error,
                "repair_notes": t.repair_notes,
            }
            parsed_file = session_dir / f"turn_{t.turn_number:03d}_parsed.json"
            with open(parsed_file, "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            refs["parsed_json_ref"] = f"artifacts/{session_id}/turn_{t.turn_number:03d}_parsed.json"
            t.parsed_json_ref = refs["parsed_json_ref"]

            file_refs[turn_key] = refs

    logger.info(f"Artifacts written to {artifacts_dir} ({total_turns} turns, {format_break_count} repaired)")
    return file_refs


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

    # Fetch GM version for reproducibility (fail-fast if GM not running)
    gm_version = await fetch_gm_version(config.gm_base_url)
    if gm_version is None:
        logger.warning("GM version unavailable - results may not be reproducible")
    else:
        logger.info(f"GM Service: {gm_version.get('git_sha', 'unknown')}"
                   f"{'-dirty' if gm_version.get('git_dirty') else ''}")

        # P1 Fix: Fail-fast if git_dirty for gate/full profiles (dev allows dirty)
        if gm_version.get("git_dirty") and config.profile in ("gate", "full"):
            error_msg = (
                f"FAIL: GM server has uncommitted changes (git_dirty=true). "
                f"For reproducibility, gate/full profiles require clean git state. "
                f"Commit changes or use 'dev' profile."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    # Run experiment with wall time tracking
    experiment_start = time.perf_counter()
    runner = ExperimentRunner(config)
    results = await runner.run_all()
    experiment_wall_time = time.perf_counter() - experiment_start

    # GM-018+1: Compute scenario metadata for all scenarios
    scenarios_meta: dict[str, dict] = {}
    for scenario_id in config.scenarios:
        _, scenario_meta = runner._load_scenario_with_meta(scenario_id)
        scenarios_meta[scenario_id] = scenario_meta

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
                    "profile": config.profile,
                    "scenarios": config.scenarios,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "max_retries": config.max_retries,
                    "gm_base_url": config.gm_base_url,
                    "llm_url": config.llm_url if config.mode == "real" else None,
                },
                # GM-018+1: run_meta for reproducibility
                "run_meta": {
                    "scenarios": scenarios_meta,
                    "gm_version": gm_version,
                },
                "conditions": conditions_stats,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"Results saved to {results_file}")

    # GM-018+1/GM-019: Generate artifacts FIRST (populates refs in TurnResult)
    generate_turn_logs_files(results, output_path, config, scenarios_meta)

    # Generate report, examples index, turns log, and conversation report (refs now populated)
    generate_report(results, output_path, config, scenarios_meta)
    generate_examples_index(results, output_path, config)
    generate_turns_log(results, output_path, config, scenarios_meta)
    generate_conversation_report(results, output_path, config, scenarios_meta)

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
