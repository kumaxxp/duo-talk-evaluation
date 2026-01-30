"""CoreAdapter - Thin wrapper for duo-talk-core generation API.

This module provides async functions to generate thoughts and utterances
for the HAKONIWA Console. Currently implements mock responses for Step2;
will be connected to actual duo-talk-core in future steps.

API:
    generate_thought(session_id, speaker, topic) -> ThoughtResponse
    generate_utterance(session_id, speaker, thought) -> UtteranceResponse

Timeout: Default 5s using asyncio.wait_for
"""

import asyncio
import random
import time
from typing import TypedDict


class ThoughtResponse(TypedDict):
    """Response from generate_thought."""

    thought: str
    tokens: int
    latency_ms: int


class UtteranceResponse(TypedDict):
    """Response from generate_utterance."""

    speech: str
    tokens: int
    latency_ms: int


# Mock thought templates per speaker
_MOCK_THOUGHTS: dict[str, list[str]] = {
    "やな": [
        "今日も一日頑張ろう！あゆと一緒なら何でも楽しいね。",
        "あゆったら、また難しい顔してる。私がなんとかしてあげなきゃ。",
        "わぁ、これ面白そう！あゆにも教えてあげたいな。",
        "ふふ、あゆの反応が可愛い。もっとからかっちゃおうかな。",
        "お腹空いたなぁ。あゆと一緒に何か食べに行こうかな。",
    ],
    "あゆ": [
        "姉様はまた無謀なことを考えていますね。仕方ありません、私がフォローしましょう。",
        "...この状況、論理的に考えれば解決策は明らかです。",
        "姉様のペースに巻き込まれるのは不本意ですが、悪くありません。",
        "なぜ姉様はいつもこうなのでしょう。でも、それが姉様らしいのかもしれません。",
        "静かに本を読みたいのですが...姉様がいると難しいですね。",
    ],
}

# Mock speech templates per speaker
_MOCK_SPEECHES: dict[str, list[str]] = {
    "やな": [
        "ねえねえ、あゆ〜！これ見て見て！",
        "えへへ、私って天才かも？",
        "あゆ、一緒に遊ぼうよ〜！",
        "わぁ、すごいすごい！あゆも見てよ！",
        "あゆのこと、大好きだよ〜♪",
    ],
    "あゆ": [
        "...姉様、少し落ち着いてください。",
        "その発想は...まあ、悪くないですね。",
        "はぁ...仕方ありませんね。付き合ってあげます。",
        "姉様、それは論理的に考えて無理があります。",
        "...別に、姉様のためじゃありませんから。",
    ],
}

# Default timeout in seconds
DEFAULT_TIMEOUT = 5.0


async def _mock_generate_thought(speaker: str, topic: str) -> ThoughtResponse:
    """Mock implementation of thought generation."""
    # Simulate processing delay (100-500ms)
    delay = random.uniform(0.1, 0.5)
    await asyncio.sleep(delay)

    # Select random thought for speaker
    thoughts = _MOCK_THOUGHTS.get(speaker, _MOCK_THOUGHTS["やな"])
    thought = random.choice(thoughts)

    # If topic is provided, incorporate it slightly
    if topic:
        thought = f"{topic}について...\n{thought}"

    return ThoughtResponse(
        thought=thought,
        tokens=len(thought),
        latency_ms=int(delay * 1000),
    )


async def _mock_generate_utterance(speaker: str, thought: str) -> UtteranceResponse:
    """Mock implementation of utterance generation."""
    # Simulate processing delay (100-500ms)
    delay = random.uniform(0.1, 0.5)
    await asyncio.sleep(delay)

    # Select random speech for speaker
    speeches = _MOCK_SPEECHES.get(speaker, _MOCK_SPEECHES["やな"])
    speech = random.choice(speeches)

    return UtteranceResponse(
        speech=speech,
        tokens=len(speech),
        latency_ms=int(delay * 1000),
    )


async def generate_thought(
    session_id: str,
    speaker: str,
    topic: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> ThoughtResponse:
    """Generate a thought for the given speaker.

    Args:
        session_id: Session identifier (for future context tracking)
        speaker: Speaker name ("やな" or "あゆ")
        topic: Topic or prompt for thought generation
        timeout: Timeout in seconds (default: 5s)

    Returns:
        ThoughtResponse with thought text, token count, and latency

    Raises:
        asyncio.TimeoutError: If generation exceeds timeout
        Exception: For other generation errors
    """
    start_time = time.perf_counter()

    try:
        # Use mock implementation for now
        # TODO: Replace with actual duo-talk-core call in future steps
        result = await asyncio.wait_for(
            _mock_generate_thought(speaker, topic),
            timeout=timeout,
        )

        # Update latency with actual elapsed time
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return ThoughtResponse(
            thought=result["thought"],
            tokens=result["tokens"],
            latency_ms=elapsed_ms,
        )

    except asyncio.TimeoutError:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        raise asyncio.TimeoutError(
            f"Thought generation timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
        )


async def generate_utterance(
    session_id: str,
    speaker: str,
    thought: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> UtteranceResponse:
    """Generate an utterance for the given speaker based on thought.

    Args:
        session_id: Session identifier (for future context tracking)
        speaker: Speaker name ("やな" or "あゆ")
        thought: Thought text to base utterance on
        timeout: Timeout in seconds (default: 5s)

    Returns:
        UtteranceResponse with speech text, token count, and latency

    Raises:
        asyncio.TimeoutError: If generation exceeds timeout
        Exception: For other generation errors
    """
    start_time = time.perf_counter()

    try:
        # Use mock implementation for now
        # TODO: Replace with actual duo-talk-core call in future steps
        result = await asyncio.wait_for(
            _mock_generate_utterance(speaker, thought),
            timeout=timeout,
        )

        # Update latency with actual elapsed time
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return UtteranceResponse(
            speech=result["speech"],
            tokens=result["tokens"],
            latency_ms=elapsed_ms,
        )

    except asyncio.TimeoutError:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        raise asyncio.TimeoutError(
            f"Utterance generation timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
        )
