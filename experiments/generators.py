"""LLM Output Generators for GM 2×2 Experiment (GM-013).

Provides abstraction for LLM output generation:
- SimGenerator: Deterministic simulation for testing
- RealLLMGenerator: Real LLM via Ollama API

Usage:
    # Simulation mode
    gen = SimGenerator()
    output = await gen.generate_turn(prompt, speaker, turn, seed)

    # Real LLM mode (Ollama)
    gen = RealLLMGenerator(model="gemma3:12b")
    output = await gen.generate_turn(prompt, speaker, turn, seed)
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of LLM generation with timing breakdown."""

    raw_output: str
    latency_ms: float
    # Timing breakdown (GM-013: Real latency tracking)
    latency_breakdown: dict[str, float] = field(default_factory=dict)
    # Metadata
    model: str = "unknown"
    tokens_generated: int = 0
    finish_reason: str = "unknown"


class Generator(ABC):
    """Abstract base for LLM output generators."""

    @abstractmethod
    async def generate_turn(
        self,
        prompt: str,
        speaker: str,
        turn_number: int,
        seed: int,
        temperature: float = 0.7,
        max_tokens: int = 300,
    ) -> GenerationResult:
        """Generate a single turn output.

        Args:
            prompt: System prompt including conversation history
            speaker: Current speaker ("やな" or "あゆ")
            turn_number: Current turn number
            seed: Random seed for reproducibility
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate

        Returns:
            GenerationResult with output and timing info
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the generator is available."""
        pass

    def get_model_name(self) -> str:
        """Return model name for reporting."""
        return "unknown"


class SimGenerator(Generator):
    """Deterministic simulation generator for testing.

    Reproduces existing _simulate_output behavior for backward compatibility.
    """

    def __init__(self):
        self._outputs = [
            "Thought: (朝のキッチン)\nOutput: おはよう、{other}！",
            "Thought: (コーヒー飲みたい)\nOutput: *マグカップを取る* コーヒー淹れようか",
            "Thought: (何食べよう)\nOutput: 今日の朝ごはん何にする？",
            "Thought: (リビング行こうかな)\nOutput: *リビングに移動* ちょっとテレビ見てくるね",
            "Thought: (同意)\nOutput: うん、そうだね",
        ]

    async def generate_turn(
        self,
        prompt: str,
        speaker: str,
        turn_number: int,
        seed: int,
        temperature: float = 0.7,
        max_tokens: int = 300,
    ) -> GenerationResult:
        """Generate simulated output (deterministic)."""
        start = time.perf_counter()

        other = "あゆ" if speaker == "やな" else "姉様"
        output = self._outputs[(turn_number + seed) % len(self._outputs)].format(other=other)

        latency_ms = (time.perf_counter() - start) * 1000

        return GenerationResult(
            raw_output=output,
            latency_ms=latency_ms,
            latency_breakdown={"llm": latency_ms},
            model="simulation",
            tokens_generated=len(output),
            finish_reason="simulated",
        )

    async def health_check(self) -> bool:
        """Simulation is always available."""
        return True

    def get_model_name(self) -> str:
        return "simulation"


class RealLLMGenerator(Generator):
    """Real LLM generator via Ollama API.

    GM-013: Implements Real Gemma 3 integration with:
    - Latency breakdown (llm time)
    - Consistent temperature/max_tokens for A/B fairness
    - Output format enforcement via system prompt
    """

    # System prompt for character dialogue (Two-pass compatible)
    CHARACTER_SYSTEM_PROMPT = """あなたは以下のキャラクターとして対話します。

## キャラクター
やな（姉）: 一人称「私」、直感的、行動派、明るく柔らかい口調
あゆ（妹）: 一人称「私」、分析的、慎重、姉を「姉様」と呼ぶ

## 出力形式
必ず以下の形式で出力してください:
Thought: (内心の考え)
Output: (実際のセリフ/行動)

行動は *アスタリスク* で囲みます。例:
Output: *マグカップを手に取る* コーヒー淹れようか

## 現在の状況
{context}

## 会話履歴
{history}

{speaker}として応答してください。"""

    def __init__(
        self,
        model: str = "gemma3:12b",
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
    ):
        self.model = model
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=timeout)

    async def generate_turn(
        self,
        prompt: str,
        speaker: str,
        turn_number: int,
        seed: int,
        temperature: float = 0.7,
        max_tokens: int = 300,
    ) -> GenerationResult:
        """Generate output from real LLM via Ollama."""
        start_total = time.perf_counter()

        # Build full prompt
        full_prompt = self.CHARACTER_SYSTEM_PROMPT.format(
            context=prompt,
            history="",  # Will be filled by caller if needed
            speaker=speaker,
        )

        # Call Ollama API
        start_llm = time.perf_counter()
        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        "seed": seed,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            # Return fallback output on error
            return GenerationResult(
                raw_output=f"Thought: (エラー)\nOutput: すみません、ちょっと考え中です...",
                latency_ms=(time.perf_counter() - start_total) * 1000,
                latency_breakdown={"llm": 0, "error": True},
                model=self.model,
                tokens_generated=0,
                finish_reason="error",
            )

        llm_latency = (time.perf_counter() - start_llm) * 1000
        total_latency = (time.perf_counter() - start_total) * 1000

        raw_output = data.get("response", "")
        tokens = data.get("eval_count", len(raw_output))
        finish_reason = "stop" if data.get("done", False) else "length"

        return GenerationResult(
            raw_output=raw_output,
            latency_ms=total_latency,
            latency_breakdown={
                "llm": llm_latency,
                "overhead": total_latency - llm_latency,
            },
            model=self.model,
            tokens_generated=tokens,
            finish_reason=finish_reason,
        )

    async def health_check(self) -> bool:
        """Check if Ollama is available with the specified model."""
        try:
            # Check if model is available
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                return False

            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]

            # Check if our model is available (handle tag variations)
            model_base = self.model.split(":")[0]
            return any(model_base in m for m in models)
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def get_model_name(self) -> str:
        return self.model

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class OpenAICompatibleGenerator(Generator):
    """OpenAI-compatible API generator (vLLM, llama.cpp server, etc.).

    GM-013: Alternative to Ollama for flexibility.
    """

    CHARACTER_SYSTEM_PROMPT = """あなたは以下のキャラクターとして対話します。

## キャラクター
やな（姉）: 一人称「私」、直感的、行動派、明るく柔らかい口調
あゆ（妹）: 一人称「私」、分析的、慎重、姉を「姉様」と呼ぶ

## 出力形式
必ず以下の形式で出力してください:
Thought: (内心の考え)
Output: (実際のセリフ/行動)

行動は *アスタリスク* で囲みます。"""

    def __init__(
        self,
        model: str = "gemma-3-12b",
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "EMPTY",
        timeout: float = 60.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=timeout)

    async def generate_turn(
        self,
        prompt: str,
        speaker: str,
        turn_number: int,
        seed: int,
        temperature: float = 0.7,
        max_tokens: int = 300,
    ) -> GenerationResult:
        """Generate output via OpenAI-compatible API."""
        start_total = time.perf_counter()

        messages = [
            {"role": "system", "content": self.CHARACTER_SYSTEM_PROMPT},
            {"role": "user", "content": f"状況: {prompt}\n\n{speaker}として応答してください。"},
        ]

        start_llm = time.perf_counter()
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "seed": seed,
                },
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return GenerationResult(
                raw_output=f"Thought: (エラー)\nOutput: すみません、ちょっと考え中です...",
                latency_ms=(time.perf_counter() - start_total) * 1000,
                latency_breakdown={"llm": 0, "error": True},
                model=self.model,
                tokens_generated=0,
                finish_reason="error",
            )

        llm_latency = (time.perf_counter() - start_llm) * 1000
        total_latency = (time.perf_counter() - start_total) * 1000

        choice = data.get("choices", [{}])[0]
        raw_output = choice.get("message", {}).get("content", "")
        finish_reason = choice.get("finish_reason", "unknown")
        usage = data.get("usage", {})
        tokens = usage.get("completion_tokens", len(raw_output))

        return GenerationResult(
            raw_output=raw_output,
            latency_ms=total_latency,
            latency_breakdown={
                "llm": llm_latency,
                "overhead": total_latency - llm_latency,
            },
            model=self.model,
            tokens_generated=tokens,
            finish_reason=finish_reason,
        )

    async def health_check(self) -> bool:
        """Check if OpenAI-compatible server is available."""
        try:
            response = await self.client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI API health check failed: {e}")
            return False

    def get_model_name(self) -> str:
        return self.model

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


def create_generator(
    mode: str = "sim",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_type: str = "ollama",
) -> Generator:
    """Factory function to create appropriate generator.

    Args:
        mode: "sim" for simulation, "real" for real LLM
        model: Model name (for real mode)
        base_url: API base URL (for real mode)
        api_type: "ollama" or "openai" (for real mode)

    Returns:
        Generator instance
    """
    if mode == "sim":
        return SimGenerator()

    if api_type == "ollama":
        return RealLLMGenerator(
            model=model or "gemma3:12b",
            base_url=base_url or "http://localhost:11434",
        )
    elif api_type == "openai":
        return OpenAICompatibleGenerator(
            model=model or "gemma-3-12b",
            base_url=base_url or "http://localhost:8000/v1",
        )
    else:
        raise ValueError(f"Unknown api_type: {api_type}")
