"""Integration tests for One-Step E2E flow.

Tests the complete One-Step flow:
Core (Thought) → Director (Check) → Core (Utterance) → Director (Check) → GM (Step)

These tests use mocks by default but can be configured to use real services
via environment variables:
- USE_REAL_CORE=1: Use real duo-talk-core (requires Ollama)
- USE_REAL_DIRECTOR=1: Use real duo-talk-director
- USE_REAL_GM=1: Use real duo-talk-gm (requires server at localhost:8001)
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import adapters
from gui_nicegui.adapters import core_adapter, director_adapter
from gui_nicegui.clients import gm_client


class TestOneStepE2EWithMocks:
    """Test One-Step flow using mocks."""

    @pytest.fixture
    def mock_core_responses(self):
        """Mock responses for Core adapter."""
        return {
            "thought": core_adapter.ThoughtResponse(
                thought="今日も妹と過ごせて幸せだな。何か楽しいことしたいな。",
                tokens=25,
                latency_ms=150,
            ),
            "utterance": core_adapter.UtteranceResponse(
                speech="おはよう、あゆ〜。今日は何しようか？",
                tokens=18,
                latency_ms=200,
            ),
        }

    @pytest.fixture
    def mock_director_pass(self):
        """Mock PASS response for Director."""
        return director_adapter.DirectorCheckResponse(
            status="PASS",
            reasons=["OK"],
            repaired_output=None,
            injected_facts=None,
            latency_ms=5,
        )

    @pytest.fixture
    def mock_director_retry(self):
        """Mock RETRY response for Director."""
        return director_adapter.DirectorCheckResponse(
            status="RETRY",
            reasons=["キャラクター口調が不適切"],
            repaired_output="今日も妹と一緒だね。楽しいな〜。",
            injected_facts=None,
            latency_ms=10,
        )

    @pytest.fixture
    def mock_gm_response(self):
        """Mock response for GM."""
        return gm_client.GMResponse(
            actions=[{"action": "SPEAK", "actor": "やな", "target": "あゆ", "result": "SUCCESS"}],
            world_patch={"changes": ["やながあゆに話しかけた"]},
            logs=["ActionJudge: SPEAK validated"],
            latency_ms=50,
        )

    @pytest.mark.asyncio
    async def test_one_step_complete_flow_all_pass(
        self, mock_core_responses, mock_director_pass, mock_gm_response
    ):
        """Test complete One-Step flow with all PASS results."""
        with (
            patch.object(
                core_adapter, "generate_thought", new_callable=AsyncMock
            ) as mock_thought,
            patch.object(
                core_adapter, "generate_utterance", new_callable=AsyncMock
            ) as mock_utterance,
            patch.object(
                director_adapter, "check", new_callable=AsyncMock
            ) as mock_check,
            patch.object(gm_client, "post_step", new_callable=AsyncMock) as mock_gm,
        ):
            # Setup mocks
            mock_thought.return_value = mock_core_responses["thought"]
            mock_utterance.return_value = mock_core_responses["utterance"]
            mock_check.return_value = mock_director_pass
            mock_gm.return_value = mock_gm_response

            # Execute One-Step flow
            start_time = time.perf_counter()

            # Phase 1: Generate Thought
            thought_result = await core_adapter.generate_thought(
                session_id="test_session",
                speaker="やな",
                topic="朝の挨拶",
                timeout=5.0,
                history=[],
            )
            assert thought_result["thought"] is not None
            assert len(thought_result["thought"]) > 0

            # Phase 2: Director Check (Thought)
            thought_check = await director_adapter.check(
                stage="thought",
                content=thought_result["thought"],
                context={"speaker": "やな", "topic": "朝の挨拶", "turn_number": 1, "history": []},
                timeout=5.0,
            )
            assert thought_check["status"] in ["PASS", "RETRY"]

            # Phase 3: Generate Utterance
            utterance_result = await core_adapter.generate_utterance(
                session_id="test_session",
                speaker="やな",
                thought=thought_result["thought"],
                timeout=5.0,
                history=[],
            )
            assert utterance_result["speech"] is not None
            assert len(utterance_result["speech"]) > 0

            # Phase 4: Director Check (Speech)
            speech_check = await director_adapter.check(
                stage="speech",
                content=utterance_result["speech"],
                context={"speaker": "やな", "topic": "朝の挨拶", "turn_number": 1, "history": []},
                timeout=5.0,
            )
            assert speech_check["status"] in ["PASS", "RETRY"]

            # Phase 5: GM Step
            gm_result = await gm_client.post_step(
                payload={
                    "session_id": "test_session",
                    "turn_number": 1,
                    "speaker": "やな",
                    "utterance": utterance_result["speech"],
                    "world_state": {},
                },
                timeout=3.0,
            )
            assert gm_result is not None
            assert "actions" in gm_result
            assert "world_patch" in gm_result

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            print(f"\nOne-Step completed in {elapsed_ms}ms")
            print(f"  Thought: {thought_result['thought'][:50]}...")
            print(f"  Thought Check: {thought_check['status']}")
            print(f"  Utterance: {utterance_result['speech'][:50]}...")
            print(f"  Speech Check: {speech_check['status']}")
            print(f"  GM Actions: {gm_result['actions']}")

    @pytest.mark.asyncio
    async def test_one_step_with_director_retry(
        self, mock_core_responses, mock_director_pass, mock_director_retry, mock_gm_response
    ):
        """Test One-Step flow with Director RETRY on first thought."""
        retry_count = 0
        max_retries = 2

        with (
            patch.object(
                core_adapter, "generate_thought", new_callable=AsyncMock
            ) as mock_thought,
            patch.object(
                core_adapter, "generate_utterance", new_callable=AsyncMock
            ) as mock_utterance,
            patch.object(
                director_adapter, "check", new_callable=AsyncMock
            ) as mock_check,
            patch.object(gm_client, "post_step", new_callable=AsyncMock) as mock_gm,
        ):
            # Setup mocks - first check returns RETRY, subsequent returns PASS
            mock_thought.return_value = mock_core_responses["thought"]
            mock_utterance.return_value = mock_core_responses["utterance"]

            check_call_count = [0]

            async def check_side_effect(*args, **kwargs):
                check_call_count[0] += 1
                if check_call_count[0] == 1:
                    return mock_director_retry
                return mock_director_pass

            mock_check.side_effect = check_side_effect
            mock_gm.return_value = mock_gm_response

            # Phase 1: Generate Thought
            thought_result = await core_adapter.generate_thought(
                session_id="test_session",
                speaker="やな",
                topic="朝の挨拶",
                timeout=5.0,
                history=[],
            )

            # Phase 2: Director Check with retry
            current_thought = thought_result["thought"]
            for attempt in range(max_retries + 1):
                thought_check = await director_adapter.check(
                    stage="thought",
                    content=current_thought,
                    context={"speaker": "やな", "topic": "朝の挨拶", "turn_number": 1, "history": []},
                    timeout=5.0,
                )

                if thought_check["status"] == "PASS":
                    break
                elif thought_check["status"] == "RETRY":
                    retry_count += 1
                    if thought_check.get("repaired_output"):
                        current_thought = thought_check["repaired_output"]
                    else:
                        # Regenerate thought
                        thought_result = await core_adapter.generate_thought(
                            session_id="test_session",
                            speaker="やな",
                            topic="朝の挨拶",
                            timeout=5.0,
                            history=[],
                        )
                        current_thought = thought_result["thought"]

            assert retry_count >= 1, "Expected at least one retry"
            assert thought_check["status"] == "PASS", "Expected PASS after retry"
            print(f"\nRetry test: {retry_count} retries before PASS")

    @pytest.mark.asyncio
    async def test_one_step_timeout_handling(self, mock_core_responses, mock_director_pass):
        """Test timeout handling in One-Step flow."""
        with patch.object(
            core_adapter, "generate_thought", new_callable=AsyncMock
        ) as mock_thought:
            # Setup mock to timeout
            async def slow_thought(*args, **kwargs):
                await asyncio.sleep(10)  # Longer than timeout
                return mock_core_responses["thought"]

            mock_thought.side_effect = slow_thought

            # Should timeout
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    core_adapter.generate_thought(
                        session_id="test_session",
                        speaker="やな",
                        topic="朝の挨拶",
                        timeout=0.1,  # Very short timeout
                        history=[],
                    ),
                    timeout=0.2,
                )


class TestOneStepE2EWithRealServices:
    """Test One-Step flow using real services (when available).

    These tests are skipped unless the corresponding environment variable is set:
    - USE_REAL_CORE=1
    - USE_REAL_DIRECTOR=1
    - USE_REAL_GM=1
    """

    @pytest.fixture
    def use_real_core(self):
        return os.environ.get("USE_REAL_CORE", "0") == "1"

    @pytest.fixture
    def use_real_director(self):
        return os.environ.get("USE_REAL_DIRECTOR", "0") == "1"

    @pytest.fixture
    def use_real_gm(self):
        return os.environ.get("USE_REAL_GM", "0") == "1"

    @pytest.mark.asyncio
    async def test_real_core_thought_generation(self, use_real_core):
        """Test real Core thought generation."""
        if not use_real_core:
            pytest.skip("USE_REAL_CORE not set")

        if not core_adapter.CORE_AVAILABLE:
            pytest.skip("Core service not available")

        result = await core_adapter.generate_thought(
            session_id="test_session",
            speaker="やな",
            topic="朝の挨拶",
            timeout=30.0,  # Longer timeout for real LLM
            history=[],
        )

        assert result["thought"] is not None
        assert len(result["thought"]) > 0
        print(f"\nReal Core result: {result['thought']}")
        print(f"Latency: {result['latency_ms']}ms")

    @pytest.mark.asyncio
    async def test_real_director_check(self, use_real_director):
        """Test real Director check."""
        if not use_real_director:
            pytest.skip("USE_REAL_DIRECTOR not set")

        if not director_adapter.DIRECTOR_AVAILABLE:
            pytest.skip("Director service not available")

        result = await director_adapter.check(
            stage="thought",
            content="今日も妹と過ごせて幸せだな。",
            context={"speaker": "やな", "topic": "朝の挨拶", "turn_number": 1, "history": []},
            timeout=10.0,
        )

        assert result["status"] in ["PASS", "RETRY"]
        print(f"\nReal Director result: {result['status']}")
        print(f"Reasons: {result.get('reasons', [])}")
        print(f"Latency: {result['latency_ms']}ms")

    @pytest.mark.asyncio
    async def test_real_gm_step(self, use_real_gm):
        """Test real GM step."""
        if not use_real_gm:
            pytest.skip("USE_REAL_GM not set")

        # Check GM availability
        if not gm_client.is_gm_available():
            # Try to check availability
            await gm_client._check_gm_availability()
            if not gm_client.is_gm_available():
                pytest.skip("GM service not available at localhost:8001")

        result = await gm_client.post_step(
            payload={
                "session_id": "test_session",
                "turn_number": 1,
                "speaker": "やな",
                "utterance": "おはよう、あゆ〜",
                "world_state": {"current_location": "寝室", "time": "朝 7:00"},
            },
            timeout=5.0,
            use_mock=False,
        )

        assert result is not None
        assert "actions" in result
        print(f"\nReal GM result: {result}")


class TestServiceAvailability:
    """Tests for service availability checking."""

    def test_core_availability_flag(self):
        """Test that CORE_AVAILABLE flag is set correctly."""
        # This just verifies the flag exists and is boolean
        assert isinstance(core_adapter.CORE_AVAILABLE, bool)
        print(f"\nCORE_AVAILABLE: {core_adapter.CORE_AVAILABLE}")

    def test_director_availability_flag(self):
        """Test that DIRECTOR_AVAILABLE flag is set correctly."""
        assert isinstance(director_adapter.DIRECTOR_AVAILABLE, bool)
        print(f"\nDIRECTOR_AVAILABLE: {director_adapter.DIRECTOR_AVAILABLE}")

    @pytest.mark.asyncio
    async def test_gm_health_check(self):
        """Test GM health check endpoint."""
        result = await gm_client.get_health(timeout=2.0)
        assert result is not None
        assert "status" in result
        assert "latency_ms" in result
        print(f"\nGM Health: {result}")


class TestLatencyMetrics:
    """Tests for latency tracking."""

    @pytest.mark.asyncio
    async def test_core_latency_tracking(self):
        """Test that Core adapter tracks latency."""
        # Use mock to ensure consistent timing
        result = await core_adapter._mock_generate_thought("やな", "test")
        assert "latency_ms" in result
        assert result["latency_ms"] > 0
        print(f"\nMock Core latency: {result['latency_ms']}ms")

    @pytest.mark.asyncio
    async def test_director_latency_tracking(self):
        """Test that Director adapter tracks latency."""
        result = await director_adapter._mock_check("thought", "test", {})
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0
        print(f"\nMock Director latency: {result['latency_ms']}ms")

    @pytest.mark.asyncio
    async def test_gm_latency_tracking(self):
        """Test that GM client tracks latency."""
        result = await gm_client._mock_post_step({})
        assert "latency_ms" in result
        assert result["latency_ms"] > 0
        print(f"\nMock GM latency: {result['latency_ms']}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
