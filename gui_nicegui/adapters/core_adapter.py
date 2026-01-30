"""CoreAdapter - Thin wrapper for duo-talk-core generation API.

This module provides async functions to generate thoughts and utterances
for the HAKONIWA Console. Step5: Real integration with duo-talk-core.

API:
    generate_thought(session_id, speaker, topic) -> ThoughtResponse
    generate_utterance(session_id, speaker, thought) -> UtteranceResponse

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
DUO_TALK_CORE_ROOT = PROJECT_ROOT.parent / "duo-talk-core" / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DUO_TALK_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(DUO_TALK_CORE_ROOT))

logger = logging.getLogger(__name__)

# Try to import duo-talk-core components
CORE_AVAILABLE = False
_llm_client = None
_two_phase_engine = None
_characters: dict = {}

try:
    from duo_talk_core.llm_client import OllamaClient, GenerationConfig
    from duo_talk_core.two_phase_engine import TwoPhaseEngine
    from duo_talk_core.character import Character, CharacterConfig

    # Create simple character instances without YAML (for GUI purposes)
    _yana_config = CharacterConfig(
        name="やな",
        full_name="やな",
        role="姉 (ELDER sister)",
        callname_self="私",
        callname_other="あゆ",
        speech_register="casual",
        speech_patterns=["〜", "よ", "ね"],
        personality=["直感重視の楽天家", "妹を頼りにしている"],
        thought_pattern="面白そうなら乗る。妹に任せれば大丈夫。",
        speech_style="明るく柔らかい口調",
    )
    _ayu_config = CharacterConfig(
        name="あゆ",
        full_name="あゆ",
        role="妹 (YOUNGER sister)",
        callname_self="私",
        callname_other="姉様",
        speech_register="polite",
        speech_patterns=["です", "ます"],
        personality=["冷静沈着だが姉には辛辣", "姉を尊敬しつつも心配"],
        thought_pattern="姉様の無謀さを嘆く。でも最後は付き合う。",
        speech_style="丁寧語だが毒がある",
    )
    _characters = {
        "やな": Character(_yana_config),
        "あゆ": Character(_ayu_config),
    }

    # Initialize LLM client (Ollama)
    _llm_client = OllamaClient(model="gemma3:12b")
    _two_phase_engine = TwoPhaseEngine(max_thought_tokens=80)

    # Check if Ollama is available
    if _llm_client.is_available():
        CORE_AVAILABLE = True
        logger.info("duo-talk-core integration: ENABLED (Ollama available)")
    else:
        logger.warning("duo-talk-core import succeeded but Ollama is not available, using mock")
        CORE_AVAILABLE = False

except ImportError as e:
    logger.warning(f"duo-talk-core import failed: {e}, using mock implementation")
    CORE_AVAILABLE = False
except Exception as e:
    logger.warning(f"duo-talk-core initialization failed: {e}, using mock implementation")
    CORE_AVAILABLE = False


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


# Mock thought templates per speaker (fallback)
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

# Mock speech templates per speaker (fallback)
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


def _sync_generate_thought(speaker: str, topic: str, history: list[dict]) -> str:
    """Synchronous thought generation using duo-talk-core."""
    if not CORE_AVAILABLE or _two_phase_engine is None or _llm_client is None:
        raise RuntimeError("Core not available")

    character = _characters.get(speaker)
    if character is None:
        raise ValueError(f"Unknown speaker: {speaker}")

    # Build prompt using TwoPhaseEngine
    prompt = _two_phase_engine.build_phase1_prompt(character, topic, history)

    # Generate using LLM
    raw_response = _llm_client.generate(prompt, GenerationConfig(max_tokens=80))

    # Parse response
    thought = _two_phase_engine.parse_thought_response(raw_response)
    return thought


def _sync_generate_utterance(speaker: str, thought: str, topic: str, history: list[dict]) -> str:
    """Synchronous utterance generation using duo-talk-core."""
    if not CORE_AVAILABLE or _two_phase_engine is None or _llm_client is None:
        raise RuntimeError("Core not available")

    character = _characters.get(speaker)
    if character is None:
        raise ValueError(f"Unknown speaker: {speaker}")

    # Build prompt using TwoPhaseEngine
    prompt = _two_phase_engine.build_phase2_prompt(character, thought, topic, history)

    # Generate using LLM
    raw_response = _llm_client.generate(prompt, GenerationConfig(max_tokens=150))

    # Parse response
    speech = _two_phase_engine.parse_speech_response(raw_response)
    return speech


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
    history: list[dict] | None = None,
) -> ThoughtResponse:
    """Generate a thought for the given speaker.

    Args:
        session_id: Session identifier (for future context tracking)
        speaker: Speaker name ("やな" or "あゆ")
        topic: Topic or prompt for thought generation
        timeout: Timeout in seconds (default: 5s)
        history: Conversation history (optional)

    Returns:
        ThoughtResponse with thought text, token count, and latency

    Raises:
        asyncio.TimeoutError: If generation exceeds timeout
        Exception: For other generation errors
    """
    start_time = time.perf_counter()
    history = history or []

    try:
        if CORE_AVAILABLE:
            # Use real duo-talk-core via asyncio.to_thread
            thought = await asyncio.wait_for(
                asyncio.to_thread(_sync_generate_thought, speaker, topic, history),
                timeout=timeout,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return ThoughtResponse(
                thought=thought,
                tokens=len(thought),
                latency_ms=elapsed_ms,
            )
        else:
            # Fallback to mock
            result = await asyncio.wait_for(
                _mock_generate_thought(speaker, topic),
                timeout=timeout,
            )
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
    topic: str = "",
    history: list[dict] | None = None,
) -> UtteranceResponse:
    """Generate an utterance for the given speaker based on thought.

    Args:
        session_id: Session identifier (for future context tracking)
        speaker: Speaker name ("やな" or "あゆ")
        thought: Thought text to base utterance on
        timeout: Timeout in seconds (default: 5s)
        topic: Topic (optional, for context)
        history: Conversation history (optional)

    Returns:
        UtteranceResponse with speech text, token count, and latency

    Raises:
        asyncio.TimeoutError: If generation exceeds timeout
        Exception: For other generation errors
    """
    start_time = time.perf_counter()
    history = history or []

    try:
        if CORE_AVAILABLE:
            # Use real duo-talk-core via asyncio.to_thread
            speech = await asyncio.wait_for(
                asyncio.to_thread(_sync_generate_utterance, speaker, thought, topic, history),
                timeout=timeout,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return UtteranceResponse(
                speech=speech,
                tokens=len(speech),
                latency_ms=elapsed_ms,
            )
        else:
            # Fallback to mock
            result = await asyncio.wait_for(
                _mock_generate_utterance(speaker, thought),
                timeout=timeout,
            )
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


def is_core_available() -> bool:
    """Check if duo-talk-core is available."""
    return CORE_AVAILABLE
