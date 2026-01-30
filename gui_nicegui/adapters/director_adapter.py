"""DirectorAdapter - Thin wrapper for duo-talk-director quality check API.

This module provides async functions to check generated content quality
using the Director service. Currently implements mock responses for Step3;
will be connected to actual duo-talk-director in future steps.

API:
    check(stage, content, context) -> DirectorCheckResponse

Timeout: Default 5s using asyncio.wait_for
"""

import asyncio
import random
import time
from typing import TypedDict


class DirectorCheckResponse(TypedDict):
    """Response from Director check."""

    status: str  # "PASS" | "RETRY" | "GIVE_UP"
    reasons: list[str]
    repaired_output: str | None
    injected_facts: list[dict] | None
    latency_ms: int


# Mock repair patterns for RETRY cases
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
        # Use mock implementation for now
        # TODO: Replace with actual duo-talk-director call in future steps
        result = await asyncio.wait_for(
            _mock_check(stage, content, context),
            timeout=timeout,
        )

        # Update latency with actual elapsed time
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
