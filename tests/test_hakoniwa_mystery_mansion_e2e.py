"""E2E Tests for HAKONIWA Save/Load with mystery_mansion scenario.

Tests the 2-process save/load workflow using HAKONIWA official API:
1. Process 1: Create session with mystery_mansion → save using save_world_state()
2. Process 2: Load using hakoniwa load CLI → verify state
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from hakoniwa.dto.manifest import Manifest
from hakoniwa.dto.world_state import RuntimeState, TurnRecord, WorldStateDTO
from hakoniwa.persistence import load_world_state, save_world_state


class TestMysteryMansionSaveLoad:
    """E2E tests for save/load with mystery_mansion scenario."""

    @pytest.fixture
    def save_path(self, tmp_path):
        """Create a temporary save path following naming convention."""
        return tmp_path / "scn_mystery_mansion_v1_state.json"

    @pytest.fixture
    def sample_world_state(self) -> WorldStateDTO:
        """Create a sample WorldStateDTO for mystery_mansion."""
        return WorldStateDTO(
            manifest=Manifest(description="E2E test save"),
            scenario_id="mystery_mansion",
            history=[
                TurnRecord(
                    turn_index=0,
                    speaker="やな",
                    response="わあ、この洋館すごく雰囲気あるね！",
                    thought="(ドキドキする)",
                ),
                TurnRecord(
                    turn_index=1,
                    speaker="あゆ",
                    response="姉様、まずはこのホールを調べましょうか。",
                    thought="(冷静に分析する)",
                ),
            ],
            runtime=RuntimeState(
                turn_index=2,
                last_actor="あゆ",
            ),
        )

    def test_save_creates_valid_json(self, save_path, sample_world_state):
        """save_world_state should create valid JSON with hash file."""
        # Save state
        content_hash = save_world_state(sample_world_state, save_path)

        # Verify files exist
        assert save_path.exists()
        hash_path = Path(str(save_path) + ".sha256")
        assert hash_path.exists()

        # Verify hash matches
        assert hash_path.read_text().strip() == content_hash

        # Verify JSON is valid
        save_data = json.loads(save_path.read_text())
        assert save_data["scenario_id"] == "mystery_mansion"
        assert len(save_data["history"]) == 2

        # Verify schema_version is included
        assert "manifest" in save_data
        assert save_data["manifest"]["schema_version"] == "1.0.0"

    def test_load_restores_state_correctly(self, save_path, sample_world_state):
        """load_world_state should restore state correctly."""
        # Save state
        save_world_state(sample_world_state, save_path)

        # Load state
        loaded_state = load_world_state(save_path)

        # Verify restored state
        assert loaded_state.scenario_id == "mystery_mansion"
        assert len(loaded_state.history) == 2
        assert loaded_state.history[0].speaker == "やな"
        assert loaded_state.history[1].speaker == "あゆ"
        assert loaded_state.runtime.turn_index == 2
        assert loaded_state.runtime.last_actor == "あゆ"

        # Verify schema_version is restored
        assert loaded_state.manifest.schema_version == "1.0.0"

    def test_e2e_two_process_workflow(self, tmp_path, sample_world_state):
        """Full E2E test: Process 1 saves, Process 2 loads via CLI."""
        save_path = tmp_path / "scn_mystery_mansion_v1_state.json"

        # =====================================================================
        # Process 1: Save state using Python API
        # =====================================================================
        save_world_state(sample_world_state, save_path)
        assert save_path.exists()

        # =====================================================================
        # Process 2: Load state via hakoniwa CLI
        # =====================================================================
        env = {**dict(__import__("os").environ), "PYTHONPATH": str(Path.cwd())}

        # First, dry-run to validate
        result = subprocess.run(
            [sys.executable, "-m", "hakoniwa.cli", "load", str(save_path), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            env=env,
        )
        assert result.returncode == 0, f"Dry-run failed: {result.stderr}"
        assert "State OK" in result.stdout

        # Full load
        result = subprocess.run(
            [sys.executable, "-m", "hakoniwa.cli", "load", str(save_path)],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            env=env,
        )
        assert result.returncode == 0, f"Load failed: {result.stderr}"
        assert "mystery_mansion" in result.stdout
        assert "turn_count" in result.stdout
        assert "schema_version" in result.stdout

    def test_save_path_follows_naming_convention(self, tmp_path, sample_world_state):
        """Save path should follow scn_{scenario}_v{version}_state.json convention."""
        save_path = tmp_path / "artifacts" / "scn_mystery_mansion_v1_state.json"

        # Save state
        save_world_state(sample_world_state, save_path)

        # Verify path structure
        assert save_path.exists()
        assert save_path.name == "scn_mystery_mansion_v1_state.json"
        assert save_path.parent.name == "artifacts"

    def test_load_preserves_turn_history(self, save_path, sample_world_state):
        """Turn history should be immutable and fully preserved."""
        # Save state
        save_world_state(sample_world_state, save_path)

        # Load state
        loaded_state = load_world_state(save_path)

        # Verify turn details are preserved
        turn0 = loaded_state.history[0]
        assert turn0.turn_index == 0
        assert turn0.speaker == "やな"
        assert "洋館" in turn0.response
        assert "ドキドキ" in turn0.thought

        turn1 = loaded_state.history[1]
        assert turn1.turn_index == 1
        assert turn1.speaker == "あゆ"
        assert "ホール" in turn1.response
        assert "冷静" in turn1.thought


class TestMysteryMansionScenarioExists:
    """Verify mystery_mansion scenario file exists and is valid."""

    def test_scenario_file_exists(self):
        """Scenario file should exist at expected path."""
        scenario_path = Path("experiments/scenarios/scn_mystery_mansion_v1.json")
        assert scenario_path.exists(), f"Scenario file not found: {scenario_path}"

    def test_scenario_is_valid_json(self):
        """Scenario file should be valid JSON."""
        scenario_path = Path("experiments/scenarios/scn_mystery_mansion_v1.json")
        content = scenario_path.read_text()
        scenario = json.loads(content)

        assert scenario["name"] == "mystery_mansion"
        assert "start_hall" in scenario["locations"]
        assert "locked_study" in scenario["locations"]
        assert "goal_attic" in scenario["locations"]

    def test_scenario_registered_in_registry(self):
        """Scenario should be registered in registry.yaml."""
        import yaml

        registry_path = Path("experiments/scenarios/registry.yaml")
        content = yaml.safe_load(registry_path.read_text())

        scenario_ids = [s["scenario_id"] for s in content["scenarios"]]
        assert "mystery_mansion" in scenario_ids

        # Find the entry and verify path
        entry = next(s for s in content["scenarios"] if s["scenario_id"] == "mystery_mansion")
        assert entry["path"] == "scn_mystery_mansion_v1.json"
