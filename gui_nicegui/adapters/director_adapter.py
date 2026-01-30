"""DirectorAdapter - Thin wrapper for duo-talk-director quality check API.

This module provides async functions to check generated content quality
using the Director service. Step5: Real integration with duo-talk-director.

API:
    check(stage, content, context) -> DirectorCheckResponse

Timeout: Default 5s using asyncio.wait_for
"""

import asyncio
import logging
import random
import sys
import time
from pathlib import Path
from typing import TypedDict

# Add project roots to sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DUO_TALK_DIRECTOR_ROOT = PROJECT_ROOT.parent / "duo-talk-director" / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DUO_TALK_DIRECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(DUO_TALK_DIRECTOR_ROOT))

logger = logging.getLogger(__name__)

# Try to import duo-talk-director components
DIRECTOR_AVAILABLE = False
_director = None

try:
    from duo_talk_director.director_minimal import DirectorMinimal
    from duo_talk_director.interfaces import DirectorStatus

    # Initialize DirectorMinimal (static checks only, no LLM required)
    _director = DirectorMinimal(strict_thought_check=True)
    DIRECTOR_AVAILABLE = True
    logger.info("duo-talk-director integration: ENABLED (DirectorMinimal)")

except ImportError as e:
    logger.warning(f"duo-talk-director import failed: {e}, using mock implementation")
    DIRECTOR_AVAILABLE = False
except Exception as e:
    logger.warning(f"duo-talk-director initialization failed: {e}, using mock implementation")
    DIRECTOR_AVAILABLE = False


class DirectorCheckResponse(TypedDict):
    """Response from Director check."""

    status: str  # "PASS" | "RETRY" | "GIVE_UP"
    reasons: list[str]
    repaired_output: str | None
    injected_facts: list[dict] | None
    latency_ms: int


# Mock repair patterns for RETRY cases (fallback)
_MOCK_REPAIRS: dict[str, list[tuple[str, str]]] = {
    "やな": [
        ("寝癖可愛い", "あゆの寝癖、可愛いよ？"),
        ("お腹すいた", "お腹空いたなぁ。何か食べに行こうかな？"),
        ("面白そう", "わぁ、これ面白そう！一緒にやろうよ！"),
    ],
    "あゆ": [
        ("うるさい", "...姉様、少し声を抑えていただけますか。"),
        ("無理", "それは論理的に考えて難しいと思います。"),
        ("仕方ない", "はぁ...仕方ありませんね。付き合ってあげます。"),
    ],
}

# Mock reasons for RETRY
_MOCK_RETRY_REASONS: list[str] = [
    "キャラクター口調の逸脱を検出",
    "発話が短すぎます（最小長未達）",
    "フォーマット不正（Thought/Outputタグ欠落）",
    "世界状態との矛盾を検出",
]

# Mock facts for injection
_MOCK_FACTS: list[dict] = [
    {"type": "location", "content": "現在地は寝室です"},
    {"type": "time", "content": "現在時刻は朝7時です"},
    {"type": "relationship", "content": "やなとあゆは姉妹です"},
]

# Default timeout in seconds
DEFAULT_TIMEOUT = 5.0


def _sync_director_check(stage: str, content: str, context: dict) -> DirectorCheckResponse:
    """Synchronous Director check using duo-talk-director."""
    if not DIRECTOR_AVAILABLE or _director is None:
        raise RuntimeError("Director not available")

    speaker = context.get("speaker", "やな")
    topic = context.get("topic", "")
    history = context.get("dialogue_log", [])
    turn_number = len(history)

    # Format content for Director (Thought: ... Output: ...)
    # For GUI, we receive either thought or speech separately
    if stage == "thought":
        formatted_content = f"Thought: {content}\nOutput: "
    else:
        formatted_content = f"Thought: (thinking)\nOutput: {content}"

    # Call Director
    evaluation = _director.evaluate_response(
        speaker=speaker,
        response=formatted_content,
        topic=topic,
        history=[{"speaker": h.get("speaker", "?"), "content": h.get("speech", "")} for h in history],
        turn_number=turn_number,
    )

    # Map DirectorStatus to our response format
    status_map = {
        "PASS": "PASS",
        "WARN": "PASS",  # WARN is acceptable
        "RETRY": "RETRY",
        "MODIFY": "RETRY",  # MODIFY also means retry
    }
    status = status_map.get(evaluation.status.value, "PASS")

    # Build reasons list
    reasons = []
    if evaluation.reason:
        reasons.append(evaluation.reason)
    reasons.extend(evaluation.checks_failed)

    # Build repaired output (from suggestion if available)
    repaired_output = None
    if status == "RETRY" and evaluation.suggestion:
        repaired_output = evaluation.suggestion

    return DirectorCheckResponse(
        status=status,
        reasons=reasons,
        repaired_output=repaired_output,
        injected_facts=None,  # DirectorMinimal doesn't inject facts
        latency_ms=0,  # Will be updated by caller
    )


async def _mock_check(stage: str, content: str, context: dict) -> DirectorCheckResponse:
    """Mock implementation of Director check."""
    # Simulate processing delay (50-300ms)
    delay = random.uniform(0.05, 0.3)
    await asyncio.sleep(delay)

    # Determine PASS/RETRY based on content characteristics
    # For demo purposes: short content or specific patterns trigger RETRY
    should_retry = len(content) < 15 or random.random() < 0.2

    if should_retry:
        # Generate repair
        speaker = context.get("speaker", "やな")
        repairs = _MOCK_REPAIRS.get(speaker, _MOCK_REPAIRS["やな"])

        # Find matching pattern or use random
        repaired = None
        for pattern, repair in repairs:
            if pattern in content:
                repaired = repair
                break

        if not repaired:
            # Use random repair
            repaired = random.choice(repairs)[1]

        # Select reasons
        reasons = random.sample(_MOCK_RETRY_REASONS, k=random.randint(1, 2))

        # Maybe inject facts
        facts = random.sample(_MOCK_FACTS, k=random.randint(0, 2)) if random.random() < 0.3 else None

        return DirectorCheckResponse(
            status="RETRY",
            reasons=reasons,
            repaired_output=repaired,
            injected_facts=facts,
            latency_ms=int(delay * 1000),
        )
    else:
        return DirectorCheckResponse(
            status="PASS",
            reasons=[],
            repaired_output=None,
            injected_facts=None,
            latency_ms=int(delay * 1000),
        )


async def check(
    stage: str,
    content: str,
    context: dict,
    timeout: float = DEFAULT_TIMEOUT,
) -> DirectorCheckResponse:
    """Check content quality using Director service.

    Args:
        stage: Check stage ("thought" or "speech")
        content: Content to check
        context: Context dictionary (session_id, speaker, dialogue_log, etc.)
        timeout: Timeout in seconds (default: 5s)

    Returns:
        DirectorCheckResponse with status, reasons, optional repaired_output

    Raises:
        asyncio.TimeoutError: If check exceeds timeout
        Exception: For other check errors
    """
    start_time = time.perf_counter()

    try:
        if DIRECTOR_AVAILABLE:
            # Use real duo-talk-director via asyncio.to_thread
            result = await asyncio.wait_for(
                asyncio.to_thread(_sync_director_check, stage, content, context),
                timeout=timeout,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return DirectorCheckResponse(
                status=result["status"],
                reasons=result["reasons"],
                repaired_output=result["repaired_output"],
                injected_facts=result["injected_facts"],
                latency_ms=elapsed_ms,
            )
        else:
            # Fallback to mock
            result = await asyncio.wait_for(
                _mock_check(stage, content, context),
                timeout=timeout,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return DirectorCheckResponse(
                status=result["status"],
                reasons=result["reasons"],
                repaired_output=result["repaired_output"],
                injected_facts=result["injected_facts"],
                latency_ms=elapsed_ms,
            )

    except asyncio.TimeoutError:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        raise asyncio.TimeoutError(
            f"Director check timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
        )


def is_director_available() -> bool:
    """Check if duo-talk-director is available."""
    return DIRECTOR_AVAILABLE
