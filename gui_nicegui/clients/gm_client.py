"""GMClient - HTTP client for Game Master (GM) service.

This module provides async functions to interact with the GM service
for world state management and action processing.
Currently implements mock responses for Step3; will connect to actual
GM FastAPI service in future steps.

API:
    post_step(payload) -> GMResponse
    get_health() -> HealthResponse

Timeout: Default 3s using httpx
"""

import asyncio
import random
import time
from typing import TypedDict

# Try to import httpx for actual HTTP calls
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class GMResponse(TypedDict):
    """Response from GM /step endpoint."""

    actions: list[dict]
    world_patch: dict
    logs: list[str]
    latency_ms: int


class HealthResponse(TypedDict):
    """Response from GM /health endpoint."""

    status: str
    latency_ms: int


# GM server configuration
GM_BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 3.0

# Mock world patches
_MOCK_PATCHES: list[dict] = [
    {
        "current_location": "リビング",
        "time": "朝 7:30",
        "changes": ["やなとあゆがリビングに移動した"],
    },
    {
        "current_location": "キッチン",
        "time": "朝 8:00",
        "changes": ["あゆが朝食の準備を始めた"],
    },
    {
        "characters": {
            "やな": {"holding": ["コーヒーカップ"]},
        },
        "changes": ["やながコーヒーカップを手に取った"],
    },
    {
        "characters": {
            "あゆ": {"holding": ["本"]},
        },
        "changes": ["あゆが本を手に取った"],
    },
]

# Mock actions
_MOCK_ACTIONS: list[dict] = [
    {"action": "MOVE", "actor": "やな", "target": "リビング", "result": "SUCCESS"},
    {"action": "TAKE", "actor": "やな", "target": "コーヒーカップ", "result": "SUCCESS"},
    {"action": "SPEAK", "actor": "やな", "target": "あゆ", "result": "SUCCESS"},
    {"action": "MOVE", "actor": "あゆ", "target": "キッチン", "result": "SUCCESS"},
    {"action": "TAKE", "actor": "あゆ", "target": "本", "result": "SUCCESS"},
]

# Mock logs
_MOCK_LOGS: list[str] = [
    "ActionJudge: MOVE action validated",
    "WorldState: Location updated",
    "ActionJudge: TAKE action validated",
    "WorldState: Inventory updated",
]


async def _mock_post_step(payload: dict) -> GMResponse:
    """Mock implementation of GM /step."""
    # Simulate processing delay (50-200ms)
    delay = random.uniform(0.05, 0.2)
    await asyncio.sleep(delay)

    # Select random patch and actions
    patch = random.choice(_MOCK_PATCHES)
    actions = random.sample(_MOCK_ACTIONS, k=random.randint(1, 2))
    logs = random.sample(_MOCK_LOGS, k=random.randint(1, 2))

    return GMResponse(
        actions=actions,
        world_patch=patch,
        logs=logs,
        latency_ms=int(delay * 1000),
    )


async def _mock_get_health() -> HealthResponse:
    """Mock implementation of GM /health."""
    # Simulate latency
    delay = random.uniform(0.01, 0.05)
    await asyncio.sleep(delay)

    return HealthResponse(
        status="ok",
        latency_ms=int(delay * 1000),
    )


async def post_step(
    payload: dict,
    timeout: float = DEFAULT_TIMEOUT,
    use_mock: bool = True,
) -> GMResponse:
    """Post a step to the GM service.

    Args:
        payload: Step payload containing utterance, speaker, world_state
        timeout: Timeout in seconds (default: 3s)
        use_mock: If True, use mock implementation (default: True for Step3)

    Returns:
        GMResponse with actions, world_patch, and logs

    Raises:
        asyncio.TimeoutError: If request exceeds timeout
        httpx.HTTPError: For HTTP errors (when not using mock)
        Exception: For other errors
    """
    start_time = time.perf_counter()

    if use_mock or not HTTPX_AVAILABLE:
        # Use mock implementation
        try:
            result = await asyncio.wait_for(
                _mock_post_step(payload),
                timeout=timeout,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return GMResponse(
                actions=result["actions"],
                world_patch=result["world_patch"],
                logs=result["logs"],
                latency_ms=elapsed_ms,
            )
        except asyncio.TimeoutError:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            raise asyncio.TimeoutError(
                f"GM post_step timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
            )

    # Real HTTP implementation
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                f"{GM_BASE_URL}/step",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return GMResponse(
                actions=data.get("actions", []),
                world_patch=data.get("world_patch", {}),
                logs=data.get("logs", []),
                latency_ms=elapsed_ms,
            )
        except httpx.TimeoutException:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            raise asyncio.TimeoutError(
                f"GM post_step timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
            )


async def get_health(
    timeout: float = DEFAULT_TIMEOUT,
    use_mock: bool = True,
) -> HealthResponse:
    """Check GM service health.

    Args:
        timeout: Timeout in seconds (default: 3s)
        use_mock: If True, use mock implementation (default: True for Step3)

    Returns:
        HealthResponse with status

    Raises:
        asyncio.TimeoutError: If request exceeds timeout
        httpx.HTTPError: For HTTP errors (when not using mock)
        Exception: For other errors
    """
    start_time = time.perf_counter()

    if use_mock or not HTTPX_AVAILABLE:
        # Use mock implementation
        try:
            result = await asyncio.wait_for(
                _mock_get_health(),
                timeout=timeout,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return HealthResponse(
                status=result["status"],
                latency_ms=elapsed_ms,
            )
        except asyncio.TimeoutError:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            raise asyncio.TimeoutError(
                f"GM health check timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
            )

    # Real HTTP implementation
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(f"{GM_BASE_URL}/health")
            response.raise_for_status()
            data = response.json()

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return HealthResponse(
                status=data.get("status", "unknown"),
                latency_ms=elapsed_ms,
            )
        except httpx.TimeoutException:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            raise asyncio.TimeoutError(
                f"GM health check timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
            )
        except Exception:
            # Return error status for non-timeout errors
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return HealthResponse(
                status="error",
                latency_ms=elapsed_ms,
            )
