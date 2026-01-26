"""Tests for scenario tools (TDD - Phase C).

C1: Template generation
C2: Linter validation
C3: World summary
"""

import json
import tempfile
from pathlib import Path

import pytest


# =============================================================================
# C1: Template Generation Tests
# =============================================================================


class TestTemplateGeneration:
    """Tests for scenario template generation."""

    def test_generate_template_creates_valid_json(self):
        """Template generates valid JSON structure."""
        from scripts.scenario_tools import generate_template

        template = generate_template("scn_test")

        assert template["name"] == "scn_test"
        assert "description" in template
        assert "locations" in template
        assert "characters" in template
        assert "time_of_day" in template
        assert "notes" in template

    def test_generate_template_has_default_locations(self):
        """Template includes default kitchen/living locations."""
        from scripts.scenario_tools import generate_template

        template = generate_template("scn_001")

        assert "キッチン" in template["locations"]
        assert "リビング" in template["locations"]
        # Check exits are bidirectional
        assert "リビング" in template["locations"]["キッチン"]["exits"]
        assert "キッチン" in template["locations"]["リビング"]["exits"]

    def test_generate_template_has_both_characters(self):
        """Template includes both やな and あゆ."""
        from scripts.scenario_tools import generate_template

        template = generate_template("scn_002")

        assert "やな" in template["characters"]
        assert "あゆ" in template["characters"]
        assert template["characters"]["やな"]["location"] == "キッチン"
        assert template["characters"]["あゆ"]["location"] == "キッチン"

    def test_write_template_to_file(self):
        """Template can be written to file."""
        from scripts.scenario_tools import generate_template, write_template

        with tempfile.TemporaryDirectory() as tmpdir:
            template = generate_template("scn_write_test")
            output_path = Path(tmpdir) / "scn_write_test.json"

            write_template(template, output_path)

            assert output_path.exists()
            loaded = json.loads(output_path.read_text(encoding="utf-8"))
            assert loaded["name"] == "scn_write_test"


# =============================================================================
# C2: Linter Tests
# =============================================================================


class TestScenarioLinter:
    """Tests for scenario linter validation."""

    def test_valid_scenario_passes(self):
        """Valid scenario passes linter."""
        from scripts.scenario_tools import lint_scenario

        scenario = {
            "name": "test",
            "description": "Test scenario",
            "locations": {
                "キッチン": {"props": ["コーヒーメーカー"], "exits": ["リビング"]},
                "リビング": {"props": ["ソファ"], "exits": ["キッチン"]},
            },
            "characters": {
                "やな": {"location": "キッチン", "holding": []},
                "あゆ": {"location": "キッチン", "holding": []},
            },
            "time_of_day": "morning",
            "notes": "Test notes",
        }

        errors = lint_scenario(scenario)
        assert len(errors) == 0

    def test_missing_name_fails(self):
        """Missing name field is detected."""
        from scripts.scenario_tools import lint_scenario

        scenario = {
            "description": "Test",
            "locations": {},
            "characters": {},
        }

        errors = lint_scenario(scenario)
        assert any("name" in e.lower() for e in errors)

    def test_missing_locations_fails(self):
        """Missing locations field is detected."""
        from scripts.scenario_tools import lint_scenario

        scenario = {
            "name": "test",
            "description": "Test",
            "characters": {},
        }

        errors = lint_scenario(scenario)
        assert any("locations" in e.lower() for e in errors)

    def test_missing_characters_fails(self):
        """Missing characters field is detected."""
        from scripts.scenario_tools import lint_scenario

        scenario = {
            "name": "test",
            "description": "Test",
            "locations": {},
        }

        errors = lint_scenario(scenario)
        assert any("characters" in e.lower() for e in errors)

    def test_invalid_exit_reference_fails(self):
        """Exit pointing to non-existent location is detected."""
        from scripts.scenario_tools import lint_scenario

        scenario = {
            "name": "test",
            "description": "Test",
            "locations": {
                "キッチン": {"props": [], "exits": ["存在しない場所"]},
            },
            "characters": {
                "やな": {"location": "キッチン", "holding": []},
                "あゆ": {"location": "キッチン", "holding": []},
            },
        }

        errors = lint_scenario(scenario)
        assert any("exit" in e.lower() or "存在しない場所" in e for e in errors)

    def test_character_invalid_location_fails(self):
        """Character at non-existent location is detected."""
        from scripts.scenario_tools import lint_scenario

        scenario = {
            "name": "test",
            "description": "Test",
            "locations": {
                "キッチン": {"props": [], "exits": []},
            },
            "characters": {
                "やな": {"location": "存在しない場所", "holding": []},
                "あゆ": {"location": "キッチン", "holding": []},
            },
        }

        errors = lint_scenario(scenario)
        assert any("やな" in e or "location" in e.lower() for e in errors)

    def test_unidirectional_exit_warns(self):
        """Unidirectional exit (A->B but not B->A) generates warning."""
        from scripts.scenario_tools import lint_scenario, lint_scenario_detailed

        scenario = {
            "name": "test",
            "description": "Test",
            "locations": {
                "キッチン": {"props": [], "exits": ["リビング"]},
                "リビング": {"props": [], "exits": []},  # No exit back to kitchen
            },
            "characters": {
                "やな": {"location": "キッチン", "holding": []},
                "あゆ": {"location": "キッチン", "holding": []},
            },
        }

        # Check backward-compatible function
        errors = lint_scenario(scenario)
        # Should have warning (prefixed with [warning])
        assert any("unidirectional" in e.lower() or "一方向" in e for e in errors)
        assert any("[warning]" in e.lower() for e in errors)

        # Check detailed function
        result = lint_scenario_detailed(scenario)
        assert len(result["errors"]) == 0  # No errors
        assert len(result["warnings"]) > 0  # Has warnings
        assert any("unidirectional" in w.lower() or "一方向" in w for w in result["warnings"])

    def test_unidirectional_exit_allowlist_suppresses_warning(self):
        """lint_allow.unidirectional_exits suppresses warnings for listed locations."""
        from scripts.scenario_tools import lint_scenario_detailed

        scenario = {
            "name": "locked_door_test",
            "description": "Test locked door scenario",
            "lint_allow": {
                "unidirectional_exits": ["書斎"]
            },
            "locations": {
                "リビング": {"props": [], "exits": ["キッチン"]},
                "キッチン": {"props": [], "exits": ["リビング"]},
                "書斎": {"props": [], "exits": ["リビング"]},  # One-way intentional
            },
            "characters": {
                "やな": {"location": "リビング", "holding": []},
                "あゆ": {"location": "リビング", "holding": []},
            },
        }

        result = lint_scenario_detailed(scenario)

        # No errors
        assert len(result["errors"]) == 0
        # No warnings about 書斎 (allowlisted)
        assert len(result["warnings"]) == 0

    def test_unidirectional_exit_partial_allowlist(self):
        """Only listed locations are suppressed, others still warn."""
        from scripts.scenario_tools import lint_scenario_detailed

        scenario = {
            "name": "partial_test",
            "description": "Test partial allowlist",
            "lint_allow": {
                "unidirectional_exits": ["書斎"]  # Only 書斎 allowed
            },
            "locations": {
                "リビング": {"props": [], "exits": []},  # No exits
                "キッチン": {"props": [], "exits": ["リビング"]},  # One-way, not allowed
                "書斎": {"props": [], "exits": ["リビング"]},  # One-way, allowed
            },
            "characters": {
                "やな": {"location": "リビング", "holding": []},
            },
        }

        result = lint_scenario_detailed(scenario)

        # Should have warning for キッチン -> リビング (not in allowlist)
        assert len(result["warnings"]) == 1
        assert "キッチン" in result["warnings"][0]

    def test_container_not_in_props_warns(self):
        """Container parent object not in props generates warning."""
        from scripts.scenario_tools import lint_scenario_detailed

        scenario = {
            "name": "container_test",
            "description": "Test container validation",
            "locations": {
                "リビング": {
                    "props": ["ソファ"],  # 本棚 is NOT in props
                    "exits": [],
                    "containers": {"本棚": ["本", "アルバム"]},  # 本棚 is a container
                },
            },
            "characters": {
                "やな": {"location": "リビング", "holding": []},
            },
        }

        result = lint_scenario_detailed(scenario)

        # Should have warning about 本棚 not being in props
        assert len(result["warnings"]) == 1
        assert "本棚" in result["warnings"][0]
        assert "props" in result["warnings"][0]

    def test_container_in_props_no_warning(self):
        """Container parent object in props generates no warning."""
        from scripts.scenario_tools import lint_scenario_detailed

        scenario = {
            "name": "container_test",
            "description": "Test container validation",
            "locations": {
                "リビング": {
                    "props": ["ソファ", "本棚"],  # 本棚 IS in props
                    "exits": [],
                    "containers": {"本棚": ["本", "アルバム"]},
                },
            },
            "characters": {
                "やな": {"location": "リビング", "holding": []},
            },
        }

        result = lint_scenario_detailed(scenario)

        # No warnings
        assert len(result["warnings"]) == 0
        assert len(result["errors"]) == 0

    def test_hidden_object_in_props_warns(self):
        """Hidden object also in props generates warning."""
        from scripts.scenario_tools import lint_scenario_detailed

        scenario = {
            "name": "hidden_test",
            "description": "Test hidden object validation",
            "locations": {
                "リビング": {
                    "props": ["ソファ", "鍵"],  # 鍵 is visible
                    "exits": [],
                    "hidden_objects": ["鍵"],  # 鍵 is also hidden - conflict
                },
            },
            "characters": {
                "やな": {"location": "リビング", "holding": []},
            },
        }

        result = lint_scenario_detailed(scenario)

        # Should have warning about 鍵 being in both props and hidden_objects
        assert len(result["warnings"]) == 1
        assert "鍵" in result["warnings"][0]
        assert "hidden_objects" in result["warnings"][0]

    def test_hidden_object_not_in_props_no_warning(self):
        """Hidden object not in props generates no warning."""
        from scripts.scenario_tools import lint_scenario_detailed

        scenario = {
            "name": "hidden_test",
            "description": "Test hidden object validation",
            "locations": {
                "リビング": {
                    "props": ["ソファ"],  # 鍵 is NOT in props
                    "exits": [],
                    "hidden_objects": ["ソファの下の鍵"],  # Only hidden
                },
            },
            "characters": {
                "やな": {"location": "リビング", "holding": []},
            },
        }

        result = lint_scenario_detailed(scenario)

        # No warnings
        assert len(result["warnings"]) == 0
        assert len(result["errors"]) == 0


# =============================================================================
# C3: World Summary Tests
# =============================================================================


class TestWorldSummary:
    """Tests for world summary generation."""

    def test_summary_contains_location_count(self):
        """Summary includes location count."""
        from scripts.scenario_tools import generate_world_summary

        scenario = {
            "name": "test",
            "locations": {
                "キッチン": {"props": ["マグカップ"], "exits": ["リビング"]},
                "リビング": {"props": ["ソファ"], "exits": ["キッチン"]},
            },
            "characters": {
                "やな": {"location": "キッチン", "holding": []},
                "あゆ": {"location": "キッチン", "holding": []},
            },
        }

        summary = generate_world_summary(scenario)

        assert summary["location_count"] == 2

    def test_summary_contains_prop_count(self):
        """Summary includes total prop count."""
        from scripts.scenario_tools import generate_world_summary

        scenario = {
            "name": "test",
            "locations": {
                "キッチン": {"props": ["マグカップ", "コーヒーメーカー"], "exits": []},
                "リビング": {"props": ["ソファ"], "exits": []},
            },
            "characters": {},
        }

        summary = generate_world_summary(scenario)

        assert summary["prop_count"] == 3

    def test_summary_contains_character_positions(self):
        """Summary includes character positions."""
        from scripts.scenario_tools import generate_world_summary

        scenario = {
            "name": "test",
            "locations": {
                "キッチン": {"props": [], "exits": []},
                "リビング": {"props": [], "exits": []},
            },
            "characters": {
                "やな": {"location": "リビング", "holding": ["本"]},
                "あゆ": {"location": "キッチン", "holding": []},
            },
        }

        summary = generate_world_summary(scenario)

        assert summary["character_positions"]["やな"] == "リビング"
        assert summary["character_positions"]["あゆ"] == "キッチン"

    def test_summary_contains_exit_graph(self):
        """Summary includes exit connectivity graph."""
        from scripts.scenario_tools import generate_world_summary

        scenario = {
            "name": "test",
            "locations": {
                "キッチン": {"props": [], "exits": ["リビング", "玄関"]},
                "リビング": {"props": [], "exits": ["キッチン"]},
                "玄関": {"props": [], "exits": ["キッチン"]},
            },
            "characters": {},
        }

        summary = generate_world_summary(scenario)

        assert "キッチン" in summary["exit_graph"]
        assert "リビング" in summary["exit_graph"]["キッチン"]
        assert "玄関" in summary["exit_graph"]["キッチン"]

    def test_summary_text_format(self):
        """Summary can be formatted as text."""
        from scripts.scenario_tools import generate_world_summary, format_summary_text

        scenario = {
            "name": "coffee_trap",
            "description": "コーヒー豆がない状況",
            "locations": {
                "キッチン": {"props": ["コーヒーメーカー"], "exits": ["リビング"]},
                "リビング": {"props": ["ソファ"], "exits": ["キッチン"]},
            },
            "characters": {
                "やな": {"location": "キッチン", "holding": []},
                "あゆ": {"location": "キッチン", "holding": []},
            },
        }

        summary = generate_world_summary(scenario)
        text = format_summary_text(summary)

        assert "coffee_trap" in text or "2" in text  # Location count
        assert isinstance(text, str)
        assert len(text) > 0
