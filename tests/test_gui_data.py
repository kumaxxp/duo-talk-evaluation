"""Tests for GUI data layer.

TDD tests for:
1. Scenario loading from experiments/scenarios/*.json
2. Results directory analysis (find latest runs)
3. Turn log parsing
4. Text diff generation for format repair comparison
"""

import json
import pytest
from pathlib import Path
from datetime import datetime


class TestScenarioLoader:
    """Tests for scenario loading from experiments/scenarios/."""

    def test_list_scenarios_returns_json_files(self, tmp_path):
        """Should list all .json files in scenarios directory."""
        from gui_nicegui.data.scenarios import list_scenarios

        # Create test scenarios
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()

        (scenarios_dir / "coffee_trap.json").write_text('{"name": "coffee_trap"}')
        (scenarios_dir / "locked_door.json").write_text('{"name": "locked_door"}')
        (scenarios_dir / "README.md").write_text("Not a scenario")

        scenarios = list_scenarios(scenarios_dir)

        assert len(scenarios) == 2
        assert "coffee_trap" in [s["name"] for s in scenarios]
        assert "locked_door" in [s["name"] for s in scenarios]

    def test_load_scenario_returns_dict(self, tmp_path):
        """Should load and parse a scenario JSON file."""
        from gui_nicegui.data.scenarios import load_scenario

        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()

        scenario_data = {
            "name": "coffee_trap",
            "description": "Test scenario",
            "locations": {"キッチン": {"props": ["コーヒーメーカー"]}},
        }
        (scenarios_dir / "coffee_trap.json").write_text(json.dumps(scenario_data))

        scenario = load_scenario(scenarios_dir / "coffee_trap.json")

        assert scenario["name"] == "coffee_trap"
        assert "locations" in scenario

    def test_get_scenario_summary(self, tmp_path):
        """Should extract summary info from scenario."""
        from gui_nicegui.data.scenarios import get_scenario_summary

        scenario = {
            "name": "coffee_trap",
            "description": "MISSING_OBJECTを誘発",
            "locations": {
                "キッチン": {"props": ["コーヒーメーカー", "マグカップ"], "exits": ["リビング"]},
                "リビング": {"props": ["ソファ"], "exits": ["キッチン"]},
            },
            "characters": {"やな": {}, "あゆ": {}},
        }

        summary = get_scenario_summary(scenario)

        assert summary["name"] == "coffee_trap"
        assert summary["location_count"] == 2
        assert summary["character_count"] == 2
        assert "コーヒーメーカー" in summary["top_props"]


class TestResultsLoader:
    """Tests for results directory analysis."""

    def test_list_runs_returns_sorted_by_date(self, tmp_path):
        """Should list runs sorted by timestamp (newest first)."""
        from gui_nicegui.data.results import list_runs

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create run directories with different timestamps
        (results_dir / "gm_2x2_coffee_trap_20260125_100000").mkdir()
        (results_dir / "gm_2x2_coffee_trap_20260125_120000").mkdir()
        (results_dir / "gm_2x2_coffee_trap_20260125_110000").mkdir()

        runs = list_runs(results_dir)

        assert len(runs) == 3
        # Newest first
        assert "120000" in runs[0]["dir_name"]
        assert "110000" in runs[1]["dir_name"]
        assert "100000" in runs[2]["dir_name"]

    def test_get_run_info_extracts_metadata(self, tmp_path):
        """Should extract run metadata from result.json."""
        from gui_nicegui.data.results import get_run_info

        results_dir = tmp_path / "results"
        run_dir = results_dir / "gm_2x2_coffee_trap_20260125_120000"
        run_dir.mkdir(parents=True)

        result_data = {
            "profile": "dev",
            "scenarios": ["coffee_trap"],
            "total_turns": 10,
            "invented_objects_rate": 0.05,
        }
        (run_dir / "result.json").write_text(json.dumps(result_data))

        info = get_run_info(run_dir)

        assert info["profile"] == "dev"
        assert info["scenarios"] == ["coffee_trap"]
        assert info["total_turns"] == 10

    def test_load_turns_log_parses_entries(self, tmp_path):
        """Should load and parse turns_log.json."""
        from gui_nicegui.data.results import load_turns_log

        run_dir = tmp_path / "run1"
        run_dir.mkdir()

        turns = [
            {
                "turn": 0,
                "speaker": "やな",
                "thought": "(楽しそう)",
                "speech": "おはよう！",
                "raw_output": "Thought: (楽しそう)\nOutput: おはよう！",
            },
            {
                "turn": 1,
                "speaker": "あゆ",
                "thought": "(眠い)",
                "speech": "おはよう...",
                "raw_output": "Thought: (眠い)\nOutput: おはよう...",
            },
        ]
        (run_dir / "turns_log.json").write_text(json.dumps(turns))

        loaded = load_turns_log(run_dir)

        assert len(loaded) == 2
        assert loaded[0]["speaker"] == "やな"
        assert loaded[1]["speaker"] == "あゆ"


class TestDiffGenerator:
    """Tests for text diff generation."""

    def test_generate_diff_for_repair(self):
        """Should generate diff showing before/after repair."""
        from gui_nicegui.data.diff import generate_repair_diff

        raw = "Thought: (考え中)\nOutput: おはよう\n\n余計なテキスト"
        repaired = "Thought: (考え中)\nOutput: おはよう"

        diff = generate_repair_diff(raw, repaired)

        assert "余計なテキスト" in diff["removed"]
        assert diff["has_changes"] is True

    def test_no_diff_when_same(self):
        """Should indicate no changes when raw equals repaired."""
        from gui_nicegui.data.diff import generate_repair_diff

        text = "Thought: (考え中)\nOutput: おはよう"

        diff = generate_repair_diff(text, text)

        assert diff["has_changes"] is False

    def test_diff_handles_none(self):
        """Should handle None repaired gracefully."""
        from gui_nicegui.data.diff import generate_repair_diff

        diff = generate_repair_diff("some text", None)

        assert diff["has_changes"] is False


class TestAvailableExtractor:
    """Tests for extracting available lists from guidance cards."""

    def test_extract_from_guidance_card(self):
        """Should extract OBJECTS_HERE, HOLDING, EXITS from guidance card."""
        from gui_nicegui.data.guidance import extract_available_from_card

        card = """<<<SYSTEM_SIGNAL>>>
[ALTERNATIVES]
OBJECTS_HERE: コーヒーメーカー, マグカップ
HOLDING: (none)
EXITS: リビング
<<<END_SIGNAL>>>"""

        available = extract_available_from_card(card)

        assert "コーヒーメーカー" in available["objects_here"]
        assert "マグカップ" in available["objects_here"]
        assert available["holding"] == []
        assert "リビング" in available["exits"]

    def test_handles_missing_sections(self):
        """Should return empty lists for missing sections."""
        from gui_nicegui.data.guidance import extract_available_from_card

        card = "[ERROR] Something went wrong"

        available = extract_available_from_card(card)

        assert available["objects_here"] == []
        assert available["holding"] == []
        assert available["exits"] == []


# =============================================================================
# MVP+ Tests: Registry, TurnViewModel, Enhanced Diff
# =============================================================================


class TestRegistryLoader:
    """Tests for scenario registry loading."""

    def test_load_registry_returns_scenarios(self, tmp_path):
        """Should load scenarios from registry.yaml."""
        from gui_nicegui.data.registry import load_registry

        registry_content = """
scenarios:
  - scenario_id: coffee_trap
    path: coffee_trap.json
    tags: [retry, missing_object]
    recommended_profile: dev
    description: "Coffee maker test"
  - scenario_id: locked_door
    path: locked_door.json
    tags: [navigation]
    recommended_profile: gate
    description: "Locked door test"
"""
        registry_path = tmp_path / "registry.yaml"
        registry_path.write_text(registry_content)

        scenarios = load_registry(registry_path)

        assert len(scenarios) == 2
        assert scenarios[0]["scenario_id"] == "coffee_trap"
        assert scenarios[1]["scenario_id"] == "locked_door"

    def test_registry_includes_tags(self, tmp_path):
        """Should include tags for filtering."""
        from gui_nicegui.data.registry import load_registry

        registry_content = """
scenarios:
  - scenario_id: test
    path: test.json
    tags: [gate_taste3, retry]
    recommended_profile: dev
    description: "Test"
"""
        registry_path = tmp_path / "registry.yaml"
        registry_path.write_text(registry_content)

        scenarios = load_registry(registry_path)

        assert "gate_taste3" in scenarios[0]["tags"]
        assert "retry" in scenarios[0]["tags"]

    def test_get_scenario_hash(self):
        """Should generate consistent hash for scenario."""
        from gui_nicegui.data.registry import get_scenario_hash

        scenario = {
            "name": "coffee_trap",
            "locations": {"キッチン": {"props": ["コーヒーメーカー"]}},
        }

        hash1 = get_scenario_hash(scenario)
        hash2 = get_scenario_hash(scenario)

        assert hash1 == hash2
        assert len(hash1) == 16  # Short hash


class TestTurnViewModel:
    """Tests for turn view model conversion."""

    def test_convert_turn_to_view_model(self):
        """Should convert raw turn to view model."""
        from gui_nicegui.data.turns import TurnViewModel, to_view_model

        raw_turn = {
            "turn_number": 0,
            "speaker": "やな",
            "parsed_thought": "考え中",
            "parsed_speech": "おはよう",
            "raw_output": "Thought: 考え中\nOutput: おはよう",
            "raw_speech": "おはよう！",
            "final_speech": "おはよう",
            "retry_steps": 1,
            "give_up": False,
            "guidance_cards": ["[ERROR] MISSING_OBJECT"],
            "format_break_triggered": True,
            "format_break_type": "EMPTY_THOUGHT",
            "repair_method": "REGENERATE",
            "repaired": True,
            "repaired_output": "Thought: (修正後)\nOutput: おはよう",
        }

        vm = to_view_model(raw_turn)

        assert vm["turn"] == 0
        assert vm["speaker"] == "やな"
        assert vm["has_retry"] is True
        assert vm["has_format_break"] is True
        assert vm["format_break_type"] == "EMPTY_THOUGHT"

    def test_view_model_includes_diff_data(self):
        """Should include data needed for diff display."""
        from gui_nicegui.data.turns import to_view_model

        raw_turn = {
            "turn_number": 1,
            "speaker": "あゆ",
            "raw_output": "Thought: 元\nOutput: 元テキスト",
            "repaired_output": "Thought: 修正\nOutput: 修正テキスト",
            "raw_speech": "元テキスト",
            "final_speech": "修正テキスト",
            "repaired": True,
        }

        vm = to_view_model(raw_turn)

        assert vm["raw_output"] == "Thought: 元\nOutput: 元テキスト"
        assert vm["repaired_output"] == "Thought: 修正\nOutput: 修正テキスト"
        assert vm["raw_speech"] == "元テキスト"
        assert vm["final_speech"] == "修正テキスト"

    def test_view_model_extracts_format_break_fields(self):
        """Should extract format_break fields for display."""
        from gui_nicegui.data.turns import to_view_model

        raw_turn = {
            "turn_number": 2,
            "speaker": "やな",
            "format_break_triggered": True,
            "format_break_type": "MISSING_OUTPUT",
            "repair_method": "FALLBACK",
            "repair_steps": 2,
            "parser_error": "Output section not found",
        }

        vm = to_view_model(raw_turn)

        assert vm["format_break"]["triggered"] is True
        assert vm["format_break"]["type"] == "MISSING_OUTPUT"
        assert vm["format_break"]["method"] == "FALLBACK"
        assert vm["format_break"]["steps"] == 2
        assert vm["format_break"]["error"] == "Output section not found"


class TestIssueSummary:
    """Tests for issue summary extraction (fast triage badges)."""

    def test_extract_issue_from_give_up_with_guidance(self):
        """Should extract MISSING_OBJECT and blocked_target from give_up turn."""
        from gui_nicegui.data.turns import extract_issue_summary

        raw_turn = {
            "give_up": True,
            "guidance_cards": [
                """<<<SYSTEM_SIGNAL>>>
[ERROR_CODE] MISSING_OBJECT
[BLOCKED_TARGET] 段ボール箱の中から、少し色褪せた古いオルゴール
[REASON] Object does not exist
<<<END_SIGNAL>>>"""
            ],
        }

        summary = extract_issue_summary(raw_turn)

        assert summary is not None
        assert summary["error_code"] == "MISSING_OBJECT"
        # Truncated at 17 chars + "..."
        assert summary["blocked_target"].startswith("段ボール箱の中から")
        assert summary["blocked_target"].endswith("...")
        assert len(summary["blocked_target"]) == 20
        assert "MISSING_OBJECT" in summary["badge_text"]

    def test_extract_issue_from_format_break(self):
        """Should extract format_break_type when no give_up."""
        from gui_nicegui.data.turns import extract_issue_summary

        raw_turn = {
            "give_up": False,
            "format_break_triggered": True,
            "format_break_type": "EMPTY_THOUGHT",
        }

        summary = extract_issue_summary(raw_turn)

        assert summary is not None
        assert summary["error_code"] == "EMPTY_THOUGHT"
        assert summary["badge_text"] == "EMPTY_THOUGHT"

    def test_extract_issue_from_retry_with_guidance(self):
        """Should extract RETRY with error_code from retry turn."""
        from gui_nicegui.data.turns import extract_issue_summary

        raw_turn = {
            "give_up": False,
            "retry_steps": 1,
            "guidance_cards": [
                "[ERROR_CODE] MISSING_OBJECT\n[BLOCKED_TARGET] test_obj"
            ],
        }

        summary = extract_issue_summary(raw_turn)

        assert summary is not None
        assert "RETRY" in summary["badge_text"]
        assert summary["error_code"] == "MISSING_OBJECT"

    def test_no_issue_summary_for_normal_turn(self):
        """Should return None for turns without issues."""
        from gui_nicegui.data.turns import extract_issue_summary

        raw_turn = {
            "give_up": False,
            "retry_steps": 0,
            "format_break_triggered": False,
        }

        summary = extract_issue_summary(raw_turn)

        assert summary is None

    def test_view_model_includes_issue_summary(self):
        """Should include issue_summary in view model."""
        from gui_nicegui.data.turns import to_view_model

        raw_turn = {
            "turn_number": 5,
            "speaker": "やな",
            "give_up": True,
            "guidance_cards": ["[ERROR_CODE] MISSING_OBJECT"],
        }

        vm = to_view_model(raw_turn)

        assert vm["issue_summary"] is not None
        assert vm["issue_summary"]["error_code"] == "MISSING_OBJECT"


class TestEnhancedDiff:
    """Tests for enhanced diff generation."""

    def test_generate_speech_diff(self):
        """Should generate diff between raw_speech and final_speech."""
        from gui_nicegui.data.diff import generate_speech_diff

        raw = "*コーヒーを淹れる* おはよう、今日もいい天気だね！"
        final = "おはよう、今日もいい天気だね！"

        diff = generate_speech_diff(raw, final)

        assert diff["has_changes"] is True
        assert "*コーヒーを淹れる*" in diff["removed"]

    def test_no_speech_diff_when_same(self):
        """Should indicate no changes when speeches are same."""
        from gui_nicegui.data.diff import generate_speech_diff

        text = "おはよう"

        diff = generate_speech_diff(text, text)

        assert diff["has_changes"] is False

    def test_diff_with_inline_markers(self):
        """Should provide inline diff markers."""
        from gui_nicegui.data.diff import generate_inline_diff

        old = "私は元気です"
        new = "私は疲れています"

        diff = generate_inline_diff(old, new)

        assert "removed" in diff
        assert "added" in diff


class TestResultsAnalysis:
    """Tests for results directory analysis."""

    def test_get_run_statistics(self, tmp_path):
        """Should calculate run statistics from turns_log."""
        from gui_nicegui.data.results import get_run_statistics

        run_dir = tmp_path / "run1"
        run_dir.mkdir()

        turns = [
            {"retry_steps": 0, "give_up": False, "format_break_triggered": False},
            {"retry_steps": 1, "give_up": False, "format_break_triggered": True},
            {"retry_steps": 2, "give_up": True, "format_break_triggered": False},
        ]
        (run_dir / "turns_log.json").write_text(json.dumps(turns))

        stats = get_run_statistics(run_dir)

        assert stats["total_turns"] == 3
        assert stats["retry_count"] == 2  # turns with retry_steps > 0
        assert stats["give_up_count"] == 1
        assert stats["format_break_count"] == 1

    def test_filter_turns_by_issue(self, tmp_path):
        """Should filter turns that have issues for quick triage."""
        from gui_nicegui.data.results import filter_issue_turns

        turns = [
            {"turn_number": 0, "retry_steps": 0, "format_break_triggered": False},
            {"turn_number": 1, "retry_steps": 1, "format_break_triggered": False},
            {"turn_number": 2, "retry_steps": 0, "format_break_triggered": True},
            {"turn_number": 3, "retry_steps": 0, "format_break_triggered": False},
        ]

        issue_turns = filter_issue_turns(turns)

        assert len(issue_turns) == 2
        assert issue_turns[0]["turn_number"] == 1
        assert issue_turns[1]["turn_number"] == 2


# =============================================================================
# Demo Pack Tests: Pack Run, Latest Pointer, Compare
# =============================================================================


class TestDemoPackRunner:
    """Tests for demo pack scenario management."""

    def test_get_demo_scenarios_from_registry(self, tmp_path):
        """Should filter scenarios with 'demo' tag."""
        from gui_nicegui.data.pack import get_demo_scenarios

        registry = [
            {"scenario_id": "coffee_trap", "tags": ["demo", "missing_object"]},
            {"scenario_id": "locked_door", "tags": ["navigation"]},
            {"scenario_id": "hidden_object", "tags": ["demo", "container"]},
        ]

        demo_scenarios = get_demo_scenarios(registry)

        assert len(demo_scenarios) == 2
        assert demo_scenarios[0]["scenario_id"] == "coffee_trap"
        assert demo_scenarios[1]["scenario_id"] == "hidden_object"

    def test_create_pack_run_id(self):
        """Should create unique pack run ID."""
        from gui_nicegui.data.pack import create_pack_run_id

        pack_id = create_pack_run_id()

        assert pack_id.startswith("demo_pack_")
        assert len(pack_id) > 15  # Includes timestamp

    def test_get_pack_run_dir(self, tmp_path):
        """Should return pack run directory path."""
        from gui_nicegui.data.pack import get_pack_run_dir

        results_dir = tmp_path / "results"
        pack_id = "demo_pack_20260125_120000"

        pack_dir = get_pack_run_dir(results_dir, pack_id)

        assert pack_dir == results_dir / pack_id


class TestLatestPointer:
    """Tests for tracking latest results per scenario."""

    def test_save_latest_pointer(self, tmp_path):
        """Should save latest run pointer."""
        from gui_nicegui.data.latest import save_latest_pointer, load_latest_pointer

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        pointer_data = {
            "scenario_id": "coffee_trap",
            "run_dir": "gm_2x2_coffee_trap_20260125_120000",
            "scenario_hash": "abc123",
            "world_hash": "def456",
            "timestamp": "20260125_120000",
        }

        save_latest_pointer(results_dir, "coffee_trap", pointer_data)
        loaded = load_latest_pointer(results_dir, "coffee_trap")

        assert loaded["scenario_id"] == "coffee_trap"
        assert loaded["run_dir"] == "gm_2x2_coffee_trap_20260125_120000"

    def test_load_missing_pointer_returns_none(self, tmp_path):
        """Should return None for missing pointer."""
        from gui_nicegui.data.latest import load_latest_pointer

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        loaded = load_latest_pointer(results_dir, "nonexistent")

        assert loaded is None


class TestCompareModel:
    """Tests for comparing run results."""

    def test_compare_run_meta(self):
        """Should compare run metadata and detect changes."""
        from gui_nicegui.data.compare import compare_run_meta

        current = {
            "scenario_hash": "abc123",
            "world_hash": "def456",
            "gm_version": "v1.0",
            "prompt_version": "p1.0",
        }
        previous = {
            "scenario_hash": "abc123",
            "world_hash": "xyz789",  # Changed
            "gm_version": "v1.0",
            "prompt_version": "p0.9",  # Changed
        }

        diff = compare_run_meta(current, previous)

        assert diff["scenario_hash_changed"] is False
        assert diff["world_hash_changed"] is True
        assert diff["gm_version_changed"] is False
        assert diff["prompt_version_changed"] is True

    def test_compare_metrics(self):
        """Should compare key metrics."""
        from gui_nicegui.data.compare import compare_metrics

        current = {
            "give_up_count": 2,
            "retry_count": 5,
            "format_break_count": 1,
            "total_turns": 20,
        }
        previous = {
            "give_up_count": 3,
            "retry_count": 8,
            "format_break_count": 2,
            "total_turns": 20,
        }

        diff = compare_metrics(current, previous)

        assert diff["give_up_delta"] == -1  # Improved
        assert diff["retry_delta"] == -3  # Improved
        assert diff["format_break_delta"] == -1  # Improved

    def test_compare_with_no_previous(self):
        """Should handle no previous run gracefully."""
        from gui_nicegui.data.compare import compare_run_meta

        current = {"scenario_hash": "abc123"}

        diff = compare_run_meta(current, None)

        assert diff["is_first_run"] is True


class TestExportPack:
    """Tests for exporting demo pack results."""

    def test_collect_export_files(self, tmp_path):
        """Should collect files for export."""
        from gui_nicegui.data.export import collect_export_files

        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        (run_dir / "REPORT.md").write_text("# Report")
        (run_dir / "turns_log.json").write_text("[]")
        (run_dir / "CONVERSATION_REPORT.md").write_text("# Conversation")

        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "turn_0.json").write_text("{}")

        files = collect_export_files(run_dir)

        assert len(files) >= 3
        assert any("REPORT.md" in str(f) for f in files)
        assert any("turns_log.json" in str(f) for f in files)

    def test_create_export_zip(self, tmp_path):
        """Should create zip file with collected files."""
        from gui_nicegui.data.export import create_export_zip

        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        (run_dir / "REPORT.md").write_text("# Report")
        (run_dir / "turns_log.json").write_text("[]")

        output_path = tmp_path / "export.zip"
        create_export_zip(run_dir, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0


# =============================================================================
# Runner Command Tests
# =============================================================================


class TestRunnerCommand:
    """Tests for runner command generation."""

    def test_generate_experiment_id(self):
        """Should generate unique experiment ID with timestamp."""
        from gui_nicegui.data.runner import generate_experiment_id

        exp_id = generate_experiment_id("coffee_trap", "dev")

        assert exp_id.startswith("gui_coffee_trap_dev_")
        assert len(exp_id) > 20  # Has timestamp

    def test_build_runner_command_includes_experiment_id(self, tmp_path):
        """Should include --experiment_id in command."""
        from gui_nicegui.data.runner import build_runner_command

        result = build_runner_command("coffee_trap", "dev", tmp_path)

        assert "--experiment_id" in result["cmd"]
        exp_id_idx = result["cmd"].index("--experiment_id")
        assert result["cmd"][exp_id_idx + 1].startswith("gui_coffee_trap_dev_")

    def test_build_runner_command_sets_pythonpath(self, tmp_path):
        """Should set PYTHONPATH in environment."""
        from gui_nicegui.data.runner import build_runner_command

        result = build_runner_command("coffee_trap", "dev", tmp_path)

        assert "PYTHONPATH" in result["env"]
        assert str(tmp_path) in result["env"]["PYTHONPATH"]

    def test_build_runner_command_includes_profile(self, tmp_path):
        """Should include --profile in command."""
        from gui_nicegui.data.runner import build_runner_command

        result = build_runner_command("coffee_trap", "gate", tmp_path)

        assert "--profile" in result["cmd"]
        profile_idx = result["cmd"].index("--profile")
        assert result["cmd"][profile_idx + 1] == "gate"

    def test_build_runner_command_with_max_turns(self, tmp_path):
        """Should include --max_turns when specified."""
        from gui_nicegui.data.runner import build_runner_command

        result = build_runner_command("coffee_trap", "dev", tmp_path, max_turns=5)

        assert "--max_turns" in result["cmd"]
        turns_idx = result["cmd"].index("--max_turns")
        assert result["cmd"][turns_idx + 1] == "5"

    def test_build_runner_command_defaults_to_real_mode(self, tmp_path):
        """Should default to real mode for LLM execution."""
        from gui_nicegui.data.runner import build_runner_command

        result = build_runner_command("coffee_trap", "dev", tmp_path)

        assert "--mode" in result["cmd"]
        mode_idx = result["cmd"].index("--mode")
        assert result["cmd"][mode_idx + 1] == "real"

    def test_build_runner_command_with_sim_mode(self, tmp_path):
        """Should allow sim mode for testing."""
        from gui_nicegui.data.runner import build_runner_command

        result = build_runner_command("coffee_trap", "dev", tmp_path, mode="sim")

        mode_idx = result["cmd"].index("--mode")
        assert result["cmd"][mode_idx + 1] == "sim"

    def test_build_runner_command_with_llm_model(self, tmp_path):
        """Should include --llm_model when specified."""
        from gui_nicegui.data.runner import build_runner_command

        result = build_runner_command(
            "coffee_trap", "dev", tmp_path, llm_model="gemma3:12b"
        )

        assert "--llm_model" in result["cmd"]
        model_idx = result["cmd"].index("--llm_model")
        assert result["cmd"][model_idx + 1] == "gemma3:12b"


# =============================================================================
# Phase F: Issue Priority + Play Mode Integration
# =============================================================================


class TestIssuePriority:
    """Tests for issue priority sorting (Crash > Schema > FormatBreak > GiveUp > Retry)."""

    def test_get_issue_priority(self):
        """Should return priority level for different issue types."""
        from gui_nicegui.data.turns import get_issue_priority

        # Crash is highest priority
        crash_turn = {"error_type": "CRASH", "give_up": False, "retry_steps": 0}
        assert get_issue_priority(crash_turn) == 0

        # Schema break
        schema_turn = {"error_type": "SCHEMA_BREAK", "give_up": False, "retry_steps": 0}
        assert get_issue_priority(schema_turn) == 1

        # FormatBreak
        format_turn = {"format_break_triggered": True, "give_up": False, "retry_steps": 0}
        assert get_issue_priority(format_turn) == 2

        # GiveUp
        giveup_turn = {"give_up": True, "retry_steps": 1}
        assert get_issue_priority(giveup_turn) == 3

        # Retry only
        retry_turn = {"give_up": False, "retry_steps": 2, "format_break_triggered": False}
        assert get_issue_priority(retry_turn) == 4

        # Normal turn (no issue)
        normal_turn = {"give_up": False, "retry_steps": 0, "format_break_triggered": False}
        assert get_issue_priority(normal_turn) == 99

    def test_sort_turns_by_priority(self):
        """Should sort turns by issue priority (most severe first)."""
        from gui_nicegui.data.turns import sort_by_issue_priority

        turns = [
            {"turn_number": 0, "give_up": False, "retry_steps": 1},  # Retry only
            {"turn_number": 1, "give_up": True, "retry_steps": 1},  # GiveUp
            {"turn_number": 2, "format_break_triggered": True, "give_up": False},  # FormatBreak
            {"turn_number": 3, "give_up": False, "retry_steps": 0},  # Normal
        ]

        sorted_turns = sort_by_issue_priority(turns)

        # FormatBreak (priority 2) should come first, then GiveUp (3), then Retry (4)
        assert sorted_turns[0]["turn_number"] == 2  # FormatBreak
        assert sorted_turns[1]["turn_number"] == 1  # GiveUp
        assert sorted_turns[2]["turn_number"] == 0  # Retry


class TestPlayModeIntegration:
    """Tests for GUI -> Play Mode integration."""

    def test_generate_play_command(self):
        """Should generate CLI command for play mode."""
        from gui_nicegui.data.pack import generate_play_command

        cmd = generate_play_command("coffee_trap")

        assert cmd == "make play s=coffee_trap"

    def test_generate_play_command_with_path(self):
        """Should support full path if needed."""
        from gui_nicegui.data.pack import generate_play_command

        cmd = generate_play_command("coffee_trap", include_path=True)

        assert "python scripts/play_mode.py" in cmd
        assert "coffee_trap" in cmd


class TestExportWithReadme:
    """Tests for export ZIP with README."""

    def test_generate_export_readme(self, tmp_path):
        """Should generate README for export."""
        from gui_nicegui.data.export import generate_export_readme

        run_info = {
            "scenario_id": "coffee_trap",
            "profile": "dev",
            "total_turns": 10,
            "give_up_count": 1,
            "retry_count": 2,
            "timestamp": "20260126_120000",
        }

        readme = generate_export_readme(run_info)

        assert "coffee_trap" in readme
        assert "dev" in readme
        assert "10" in readme  # total_turns
        assert "使い方" in readme or "Usage" in readme

    def test_export_zip_includes_readme(self, tmp_path):
        """Should include README.md in export zip."""
        import zipfile
        from gui_nicegui.data.export import create_export_zip

        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        (run_dir / "REPORT.md").write_text("# Report")
        (run_dir / "turns_log.json").write_text("[]")
        (run_dir / "result.json").write_text('{"scenario_id": "test", "profile": "dev"}')

        output_path = tmp_path / "export.zip"
        create_export_zip(run_dir, output_path, include_readme=True)

        with zipfile.ZipFile(output_path, "r") as zf:
            names = zf.namelist()
            assert any("README" in name for name in names)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
