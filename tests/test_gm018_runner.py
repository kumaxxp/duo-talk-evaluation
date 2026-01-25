"""Tests for GM-018+1 functionality in gm_2x2_runner.

TDD: Regression tests for:
- A. Artifact file generation (raw/repaired/parsed.json)
- B. Format break examples extraction (max 3)
- D. run_meta (scenario_hash/world_hash)
- D2. scenario_id mismatch detection
"""

import json
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pytest

from experiments.gm_2x2_runner import (
    TurnResult,
    RunResult,
    generate_turn_logs_files,
    _collect_format_break_examples,
)
from experiments.scenario_registry import (
    SchemaValidationError,
    ValidationErrorCode,
    compute_scenario_hash,
    compute_world_hash,
    generate_world_summary,
)


class TestArtifactGeneration:
    """Tests for artifact file generation (GM-018+1 A)."""

    def test_artifacts_always_save_raw_output(self, tmp_path):
        """raw_output.txt should always be saved for every turn."""
        # Create mock results
        turn = TurnResult(
            turn_number=0,
            speaker="やな",
            raw_output="Thought: (テスト)\nOutput: こんにちは",
            parsed_thought="(テスト)",
            parsed_speech="こんにちは",
            allowed=True,
            denied_reason=None,
            world_delta=[],
            stall_score=0.0,
            fact_cards=[],
            retry_count=0,
            latency_ms=100.0,
            gm_latency_ms=1.0,
            format_break_triggered=False,  # No format break
        )

        run_result = RunResult(
            condition="D",
            scenario="default",
            seed=0,
            inject_enabled=True,
            gm_enabled=True,
            turns=[turn],
            total_retries=0,
            success_rate=1.0,
            gm_injected_count=0,
            gm_denied_count=0,
            mean_stall_score=0.0,
            latency_p50_ms=100.0,
            latency_p95_ms=100.0,
            timestamp="2026-01-25",
        )

        # Mock config
        @dataclass
        class MockConfig:
            experiment_id: str = "test"

        config = MockConfig()

        # Generate artifacts
        generate_turn_logs_files([run_result], tmp_path, config)

        # Check raw_output.txt was created
        session_dir = tmp_path / "artifacts" / "test_D_default_0"
        raw_file = session_dir / "turn_000_raw_output.txt"
        assert raw_file.exists(), "raw_output.txt should always be saved"
        assert raw_file.read_text(encoding="utf-8") == "Thought: (テスト)\nOutput: こんにちは"

        # Check parsed.json was created
        parsed_file = session_dir / "turn_000_parsed.json"
        assert parsed_file.exists(), "parsed.json should always be saved"
        parsed_data = json.loads(parsed_file.read_text(encoding="utf-8"))
        assert parsed_data["thought"] == "(テスト)"
        assert parsed_data["speech"] == "こんにちは"

    def test_artifacts_save_repaired_only_when_repaired(self, tmp_path):
        """repaired_output.txt should only be saved when repaired=True."""
        # Turn WITHOUT repair
        turn_no_repair = TurnResult(
            turn_number=0,
            speaker="やな",
            raw_output="Thought: (テスト)\nOutput: こんにちは",
            parsed_thought="(テスト)",
            parsed_speech="こんにちは",
            allowed=True,
            denied_reason=None,
            world_delta=[],
            stall_score=0.0,
            fact_cards=[],
            retry_count=0,
            latency_ms=100.0,
            gm_latency_ms=1.0,
            format_break_triggered=False,
            repaired=False,
        )

        # Turn WITH repair
        turn_with_repair = TurnResult(
            turn_number=1,
            speaker="あゆ",
            raw_output="```\nThought: (テスト)\nOutput: さようなら\n```",
            parsed_thought="(テスト)",
            parsed_speech="さようなら",
            allowed=True,
            denied_reason=None,
            world_delta=[],
            stall_score=0.0,
            fact_cards=[],
            retry_count=0,
            latency_ms=100.0,
            gm_latency_ms=1.0,
            format_break_triggered=True,
            repaired=True,
            repaired_output="Thought: (テスト)\nOutput: さようなら",
            repair_method="STRIP",
            repair_steps=1,
        )

        run_result = RunResult(
            condition="D",
            scenario="default",
            seed=0,
            inject_enabled=True,
            gm_enabled=True,
            turns=[turn_no_repair, turn_with_repair],
            total_retries=0,
            success_rate=1.0,
            gm_injected_count=0,
            gm_denied_count=0,
            mean_stall_score=0.0,
            latency_p50_ms=100.0,
            latency_p95_ms=100.0,
            timestamp="2026-01-25",
        )

        @dataclass
        class MockConfig:
            experiment_id: str = "test"

        generate_turn_logs_files([run_result], tmp_path, MockConfig())

        session_dir = tmp_path / "artifacts" / "test_D_default_0"

        # Turn 0: no repaired file
        repaired_file_0 = session_dir / "turn_000_repaired_output.txt"
        assert not repaired_file_0.exists(), "repaired_output.txt should NOT be saved when repaired=False"

        # Turn 1: has repaired file
        repaired_file_1 = session_dir / "turn_001_repaired_output.txt"
        assert repaired_file_1.exists(), "repaired_output.txt should be saved when repaired=True"
        assert "```" not in repaired_file_1.read_text(encoding="utf-8"), "repaired output should not contain code fences"


class TestFormatBreakExamples:
    """Tests for format break examples extraction (GM-018+1 B)."""

    def test_examples_max_3(self):
        """Should return at most 3 examples."""
        turns = []
        for i in range(5):
            turn = TurnResult(
                turn_number=i,
                speaker="やな" if i % 2 == 0 else "あゆ",
                raw_output=f"broken output {i}",
                parsed_thought=None,
                parsed_speech=f"speech {i}",
                allowed=True,
                denied_reason=None,
                world_delta=[],
                stall_score=0.0,
                fact_cards=[],
                retry_count=0,
                latency_ms=100.0,
                gm_latency_ms=1.0,
                format_break_triggered=True,
                format_break_type="MISSING_OUTPUT_TAGS",
                repair_method="FALLBACK_SPEECH",
                repair_steps=i,
                repaired=True,
            )
            turns.append(turn)

        run_result = RunResult(
            condition="D",
            scenario="default",
            seed=0,
            inject_enabled=True,
            gm_enabled=True,
            turns=turns,
            total_retries=0,
            success_rate=1.0,
            gm_injected_count=0,
            gm_denied_count=0,
            mean_stall_score=0.0,
            latency_p50_ms=100.0,
            latency_p95_ms=100.0,
            timestamp="2026-01-25",
        )

        examples = _collect_format_break_examples([run_result], max_examples=3)
        assert len(examples) == 3, "Should return at most 3 examples"

    def test_examples_priority_by_repair_steps(self):
        """Should prioritize by repair_steps descending."""
        turns = []
        repair_steps_values = [1, 3, 2, 0]  # Out of order
        for i, steps in enumerate(repair_steps_values):
            turn = TurnResult(
                turn_number=i,
                speaker="やな",
                raw_output=f"broken output {i}",
                parsed_thought=None,
                parsed_speech=f"speech {i}",
                allowed=True,
                denied_reason=None,
                world_delta=[],
                stall_score=0.0,
                fact_cards=[],
                retry_count=0,
                latency_ms=100.0,
                gm_latency_ms=1.0,
                format_break_triggered=True,
                format_break_type="MISSING_OUTPUT_TAGS",
                repair_steps=steps,
                repaired=True,
            )
            turns.append(turn)

        run_result = RunResult(
            condition="D",
            scenario="default",
            seed=0,
            inject_enabled=True,
            gm_enabled=True,
            turns=turns,
            total_retries=0,
            success_rate=1.0,
            gm_injected_count=0,
            gm_denied_count=0,
            mean_stall_score=0.0,
            latency_p50_ms=100.0,
            latency_p95_ms=100.0,
            timestamp="2026-01-25",
        )

        examples = _collect_format_break_examples([run_result], max_examples=4)
        steps_order = [ex["repair_steps"] for ex in examples]
        assert steps_order == [3, 2, 1, 0], f"Should be sorted by repair_steps desc, got {steps_order}"


class TestRunMetaHashes:
    """Tests for run_meta hash computation (GM-018+1 D)."""

    def test_scenario_hash_deterministic(self):
        """scenario_hash should be deterministic for same input."""
        scenario_data = {
            "name": "test",
            "locations": {"キッチン": {"props": ["マグカップ"]}},
        }
        hash1 = compute_scenario_hash(scenario_data)
        hash2 = compute_scenario_hash(scenario_data)
        assert hash1 == hash2, "Hash should be deterministic"
        assert len(hash1) == 16, "Hash should be 16 chars"

    def test_world_hash_deterministic(self):
        """world_hash should be deterministic for same input."""
        world_state = {
            "version": "0.1",
            "props": {"マグカップ": {"location": "キッチン"}},
        }
        hash1 = compute_world_hash(world_state)
        hash2 = compute_world_hash(world_state)
        assert hash1 == hash2, "Hash should be deterministic"
        assert len(hash1) == 16, "Hash should be 16 chars"

    def test_world_summary_structure(self):
        """world_summary should have correct structure."""
        world_state = {
            "locations": {"キッチン": {}, "リビング": {}},
            "characters": {"やな": {}, "あゆ": {}},
            "props": {"マグカップ": {}, "コーヒーメーカー": {}},
        }
        summary = generate_world_summary(world_state)

        assert "counts" in summary
        assert summary["counts"]["locations"] == 2
        assert summary["counts"]["characters"] == 2
        assert summary["counts"]["objects"] == 2
        assert "objects_top10" in summary
        assert "locations" in summary


class TestScenarioMismatchValidation:
    """Tests for scenario_id mismatch detection (GM-018+1 D2)."""

    def test_schema_validation_error_exists(self):
        """SchemaValidationError should be importable."""
        assert SchemaValidationError is not None
        assert issubclass(SchemaValidationError, Exception)

    def test_schema_validation_error_message(self):
        """SchemaValidationError should contain helpful message."""
        error = SchemaValidationError(
            "test scenario mismatch",
            ValidationErrorCode.SCENARIO_ID_MISMATCH,
        )
        assert "mismatch" in str(error)
        assert error.code == ValidationErrorCode.SCENARIO_ID_MISMATCH
