"""GMClient - HTTP client for Game Master (GM) service.

This module provides async functions to interact with the GM service
for world state management and action processing.
Step5: Real HTTP integration with duo-talk-gm.

API:
    post_step(payload) -> GMResponse
    get_health() -> HealthResponse

Timeout: Default 3s using httpx
"""

import asyncio
import logging
import random
import time
from typing import TypedDict

logger = logging.getLogger(__name__)

# Try to import httpx for actual HTTP calls
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    logger.warning("httpx not available, GM client will use mock only")
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

# Track GM availability
_gm_available: bool | None = None  # None = not checked yet


async def _check_gm_availability() -> bool:
    """Check if GM service is available."""
    global _gm_available
    if not HTTPX_AVAILABLE:
        _gm_available = False
        return False

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{GM_BASE_URL}/health")
            _gm_available = response.status_code == 200
            if _gm_available:
                logger.info("GM service: CONNECTED")
            return _gm_available
    except Exception as e:
        logger.warning(f"GM service not available: {e}")
        _gm_available = False
        return False


# Mock world patches (fallback)
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


def _map_gm_response_to_gui(data: dict, speaker: str) -> GMResponse:
    """Map GM service response to GUI-friendly format."""
    # Extract world_delta and convert to world_patch
    world_delta = data.get("world_delta", [])
    changes = []

    # Extract changes from world_delta (JSON Patch operations)
    for delta in world_delta:
        if delta.get("op") == "replace" or delta.get("op") == "add":
            path = delta.get("path", "")
            value = delta.get("value", "")
            if "location" in path:
                changes.append(f"{speaker}が{value}に移動した")
            elif "holding" in path:
                if value:
                    changes.append(f"{speaker}が{value}を手に取った")

    # Build world_patch from various sources
    world_patch: dict = {"changes": changes}

    # Extract normalized_action for action info
    norm_action = data.get("normalized_action", {})
    actions = []
    if norm_action.get("normalized"):
        actions.append({
            "action": norm_action.get("verb", "UNKNOWN").upper(),
            "actor": speaker,
            "target": norm_action.get("target", ""),
            "result": "SUCCESS" if norm_action.get("apply_success", True) else "FAILED",
        })
    elif data.get("allowed", True):
        # Default SPEAK action if no normalized action
        actions.append({
            "action": "SPEAK",
            "actor": speaker,
            "target": "",
            "result": "SUCCESS",
        })

    # Extract logs from fact_cards
    logs = data.get("fact_cards", [])

    return GMResponse(
        actions=actions,
        world_patch=world_patch,
        logs=logs,
        latency_ms=0,  # Will be updated by caller
    )


async def post_step(
    payload: dict,
    timeout: float = DEFAULT_TIMEOUT,
    use_mock: bool | None = None,
) -> GMResponse:
    """Post a step to the GM service.

    Args:
        payload: Step payload containing utterance, speaker, world_state
        timeout: Timeout in seconds (default: 3s)
        use_mock: If True, use mock. If None, auto-detect GM availability.

    Returns:
        GMResponse with actions, world_patch, and logs

    Raises:
        asyncio.TimeoutError: If request exceeds timeout
        httpx.HTTPError: For HTTP errors (when not using mock)
        Exception: For other errors
    """
    global _gm_available
    start_time = time.perf_counter()

    # Auto-detect GM availability if not specified
    if use_mock is None:
        if _gm_available is None:
            await _check_gm_availability()
        use_mock = not _gm_available

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
            # Build GMStepRequest-compatible payload
            speaker = payload.get("speaker", "やな")
            utterance = payload.get("utterance", "")
            world_state = payload.get("world_state", {})

            gm_request = {
                "session_id": payload.get("session_id", "gui_session"),
                "turn_number": payload.get("turn_number", 0),
                "speaker": speaker,
                "raw_output": f"Thought: (thinking)\nOutput: {utterance}",
                "world_state": {
                    "current_location": world_state.get("current_location", "寝室"),
                    "characters": world_state.get("characters", {}),
                    "locations": {},
                    "time": world_state.get("time", "朝 7:00"),
                    "props": {},
                },
            }

            response = await client.post(
                f"{GM_BASE_URL}/v1/gm/step",
                json=gm_request,
            )
            response.raise_for_status()
            data = response.json()

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            result = _map_gm_response_to_gui(data, speaker)
            return GMResponse(
                actions=result["actions"],
                world_patch=result["world_patch"],
                logs=result["logs"],
                latency_ms=elapsed_ms,
            )
        except httpx.TimeoutException:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            raise asyncio.TimeoutError(
                f"GM post_step timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"GM HTTP error: {e}")
            # Fallback to mock on error
            _gm_available = False
            result = await _mock_post_step(payload)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return GMResponse(
                actions=result["actions"],
                world_patch=result["world_patch"],
                logs=[f"GM error: {e.response.status_code}"] + result["logs"],
                latency_ms=elapsed_ms,
            )
        except Exception as e:
            logger.error(f"GM error: {e}")
            # Fallback to mock on error
            _gm_available = False
            result = await _mock_post_step(payload)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return GMResponse(
                actions=result["actions"],
                world_patch=result["world_patch"],
                logs=[f"GM error: {str(e)[:50]}"] + result["logs"],
                latency_ms=elapsed_ms,
            )


async def get_health(
    timeout: float = DEFAULT_TIMEOUT,
    use_mock: bool | None = None,
) -> HealthResponse:
    """Check GM service health.

    Args:
        timeout: Timeout in seconds (default: 3s)
        use_mock: If True, use mock. If None, try real first.

    Returns:
        HealthResponse with status

    Raises:
        asyncio.TimeoutError: If request exceeds timeout
        httpx.HTTPError: For HTTP errors (when not using mock)
        Exception: For other errors
    """
    global _gm_available
    start_time = time.perf_counter()

    # If use_mock is explicitly True, use mock
    if use_mock is True or not HTTPX_AVAILABLE:
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

    # Try real HTTP first
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(f"{GM_BASE_URL}/health")
            response.raise_for_status()
            data = response.json()

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            _gm_available = True
            return HealthResponse(
                status=data.get("status", "unknown"),
                latency_ms=elapsed_ms,
            )
        except httpx.TimeoutException:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            _gm_available = False
            raise asyncio.TimeoutError(
                f"GM health check timed out after {elapsed_ms}ms (limit: {int(timeout * 1000)}ms)"
            )
        except Exception as e:
            # Return error status for non-timeout errors
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            _gm_available = False
            logger.warning(f"GM health check failed: {e}")
            return HealthResponse(
                status="unavailable",
                latency_ms=elapsed_ms,
            )


def is_gm_available() -> bool:
    """Check if GM service is available (cached value)."""
    return _gm_available is True
