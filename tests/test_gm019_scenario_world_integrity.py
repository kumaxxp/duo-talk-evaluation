"""Tests for GM-019: Scenario/World Integrity & Registry.

TDD: Regression tests for:
- A. Registry resolution: scenario_id -> path
- B. Registry missing: unknown scenario_id -> REGISTRY_MISSING
- C. Scenario integrity validation (exits, locations)
- D. Canonical JSON determinism
- E. World hash excludes runtime fields
- F. World summary structure
- G. scenario_id mismatch in file -> SCENARIO_ID_MISMATCH
- H. Hash computation error handling
"""

import json
import tempfile
from pathlib import Path

import pytest

from experiments.scenario_registry import (
    ScenarioEntry,
    ScenarioRegistry,
    SchemaValidationError,
    ValidationErrorCode,
    ValidationResult,
    canonicalize_dict,
    compute_scenario_hash,
    compute_world_hash,
    generate_world_summary,
    validate_scenario_integrity,
    world_state_to_canonical,
)


class TestRegistryResolution:
    """Tests for scenario_id -> path resolution (GM-019 A)."""

    def test_resolve_default_returns_none_path(self):
        """'default' scenario should resolve to None path (built-in)."""
        registry = ScenarioRegistry()
        path, entry = registry.resolve("default")
        assert path is None
        assert entry.scenario_id == "default"
        assert "baseline" in entry.tags

    def test_resolve_unknown_raises_registry_missing(self):
        """Unknown scenario_id should raise REGISTRY_MISSING error."""
        registry = ScenarioRegistry()
        with pytest.raises(SchemaValidationError) as exc_info:
            registry.resolve("nonexistent_scenario_xyz")
        assert exc_info.value.code == ValidationErrorCode.REGISTRY_MISSING
        assert "nonexistent_scenario_xyz" in str(exc_info.value)

    def test_resolve_registered_scenario_returns_path(self):
        """Registered scenario should resolve to correct file path."""
        registry = ScenarioRegistry()
        # Check if coffee_trap exists in registry
        entries = registry.list_scenarios()
        coffee_entry = next((e for e in entries if e.scenario_id == "coffee_trap"), None)
        if coffee_entry:
            path, entry = registry.resolve("coffee_trap")
            assert path is not None or entry.path is None  # depends on file existence
            assert entry.scenario_id == "coffee_trap"


class TestRegistryMissing:
    """Tests for REGISTRY_MISSING error (GM-019 B)."""

    def test_error_contains_available_scenarios(self):
        """REGISTRY_MISSING error should list available scenarios."""
        registry = ScenarioRegistry()
        with pytest.raises(SchemaValidationError) as exc_info:
            registry.resolve("not_a_real_scenario")
        assert exc_info.value.code == ValidationErrorCode.REGISTRY_MISSING
        assert "available" in exc_info.value.details


class TestScenarioIntegrity:
    """Tests for scenario integrity validation (GM-019 C)."""

    def test_valid_scenario_passes(self):
        """Valid scenario should pass integrity checks."""
        scenario_data = {
            "locations": {
                "キッチン": {"exits": ["リビング"]},
                "リビング": {"exits": ["キッチン"]},
            },
            "characters": {
                "やな": {"location": "キッチン"},
                "あゆ": {"location": "リビング"},
            },
        }
        result = validate_scenario_integrity(scenario_data)
        assert result.passed is True
        assert len(result.errors) == 0

    def test_exit_target_missing_detected(self):
        """Missing exit target should trigger EXIT_TARGET_MISSING."""
        scenario_data = {
            "locations": {
                "キッチン": {"exits": ["存在しない部屋"]},
            },
            "characters": {},
        }
        result = validate_scenario_integrity(scenario_data)
        assert result.passed is False
        assert ValidationErrorCode.EXIT_TARGET_MISSING.value in result.error_codes

    def test_character_location_missing_detected(self):
        """Missing character location should trigger CHAR_LOCATION_MISSING."""
        scenario_data = {
            "locations": {
                "キッチン": {"exits": []},
            },
            "characters": {
                "やな": {"location": "存在しない場所"},
            },
        }
        result = validate_scenario_integrity(scenario_data)
        assert result.passed is False
        assert ValidationErrorCode.CHAR_LOCATION_MISSING.value in result.error_codes

    def test_none_scenario_passes(self):
        """None scenario (built-in default) should pass validation."""
        result = validate_scenario_integrity(None)
        assert result.passed is True


class TestCanonicalJSON:
    """Tests for canonical JSON determinism (GM-019 D)."""

    def test_canonicalize_sorts_keys(self):
        """Canonical JSON should sort keys."""
        data = {"z": 1, "a": 2, "m": 3}
        canonical = canonicalize_dict(data)
        assert canonical == '{"a":2,"m":3,"z":1}'

    def test_canonicalize_nested_dicts(self):
        """Canonical JSON should sort nested dict keys."""
        data = {"outer": {"z": 1, "a": 2}}
        canonical = canonicalize_dict(data)
        assert canonical == '{"outer":{"a":2,"z":1}}'

    def test_canonicalize_deterministic(self):
        """Same input should produce identical output."""
        data = {"name": "test", "values": [3, 1, 2]}
        hash1 = canonicalize_dict(data)
        hash2 = canonicalize_dict(data)
        assert hash1 == hash2


class TestWorldHashExcludesRuntime:
    """Tests for world_hash excluding runtime fields (GM-019 E)."""

    def test_world_canonical_excludes_events(self):
        """world_state_to_canonical should exclude 'events'."""
        world_state = {
            "locations": {"キッチン": {}},
            "events": [{"type": "move", "turn": 1}],  # Runtime field
        }
        canonical = world_state_to_canonical(world_state)
        assert "events" not in canonical

    def test_world_canonical_excludes_turn(self):
        """world_state_to_canonical should exclude 'time.turn'."""
        world_state = {
            "locations": {"キッチン": {}},
            "time": {"period": "morning", "turn": 5},  # turn is runtime
        }
        canonical = world_state_to_canonical(world_state)
        parsed = json.loads(canonical)
        assert "turn" not in parsed.get("time", {})
        assert parsed["time"]["period"] == "morning"

    def test_world_canonical_excludes_underscore_fields(self):
        """world_state_to_canonical should exclude fields starting with '_'."""
        world_state = {
            "locations": {"キッチン": {}},
            "_internal_counter": 42,  # Private field
        }
        canonical = world_state_to_canonical(world_state)
        assert "_internal_counter" not in canonical

    def test_world_hash_stable_across_turns(self):
        """World hash should be stable when only runtime fields change."""
        base_world = {
            "locations": {"キッチン": {}},
            "props": {"マグカップ": {"location": "キッチン"}},
        }
        world_turn1 = {**base_world, "time": {"period": "morning", "turn": 1}}
        world_turn5 = {**base_world, "time": {"period": "morning", "turn": 5}}

        hash1 = compute_world_hash(world_turn1)
        hash5 = compute_world_hash(world_turn5)
        assert hash1 == hash5, "Hash should be stable when only turn changes"


class TestWorldSummary:
    """Tests for world_summary structure (GM-019 F)."""

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
        assert "キッチン" in summary["locations"]

    def test_world_summary_top10_limit(self):
        """objects_top10 should be limited to 10 items."""
        world_state = {
            "locations": {},
            "characters": {},
            "props": {f"object_{i}": {} for i in range(20)},
        }
        summary = generate_world_summary(world_state)
        assert len(summary["objects_top10"]) == 10


class TestScenarioIdMismatch:
    """Tests for scenario_id mismatch detection (GM-019 G)."""

    def test_load_scenario_validates_name_field(self, tmp_path):
        """Loading scenario should validate name field matches scenario_id."""
        # Create a temporary registry with a test scenario
        registry_content = """
scenarios:
  - scenario_id: test_scenario
    path: test_scenario.json
    tags: [test]
"""
        registry_path = tmp_path / "registry.yaml"
        registry_path.write_text(registry_content)

        # Create scenario file with mismatched name
        scenario_path = tmp_path / "test_scenario.json"
        scenario_path.write_text(json.dumps({
            "name": "different_name",  # Mismatch!
            "locations": {},
        }))

        registry = ScenarioRegistry(registry_path)
        with pytest.raises(SchemaValidationError) as exc_info:
            registry.load_scenario("test_scenario")
        assert exc_info.value.code == ValidationErrorCode.SCENARIO_ID_MISMATCH


class TestHashComputation:
    """Tests for hash computation (GM-019 H)."""

    def test_scenario_hash_deterministic(self):
        """scenario_hash should be deterministic for same input."""
        scenario_data = {
            "name": "test",
            "locations": {"キッチン": {"props": ["マグカップ"]}},
        }
        hash1 = compute_scenario_hash(scenario_data)
        hash2 = compute_scenario_hash(scenario_data)
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_world_hash_deterministic(self):
        """world_hash should be deterministic for same input."""
        world_state = {
            "version": "0.1",
            "props": {"マグカップ": {"location": "キッチン"}},
        }
        hash1 = compute_world_hash(world_state)
        hash2 = compute_world_hash(world_state)
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_default_scenario_hash(self):
        """None scenario should return fixed hash."""
        hash_result = compute_scenario_hash(None)
        assert hash_result == "default_scenario"

    def test_scenario_hash_different_for_different_data(self):
        """Different scenarios should produce different hashes."""
        scenario1 = {"name": "test1", "locations": {}}
        scenario2 = {"name": "test2", "locations": {}}
        hash1 = compute_scenario_hash(scenario1)
        hash2 = compute_scenario_hash(scenario2)
        assert hash1 != hash2


class TestValidationResult:
    """Tests for ValidationResult structure."""

    def test_validation_result_error_codes(self):
        """ValidationResult should provide error codes list."""
        errors = [
            SchemaValidationError(
                "Test error",
                ValidationErrorCode.EXIT_TARGET_MISSING,
            ),
        ]
        result = ValidationResult(passed=False, errors=errors)
        assert result.error_codes == ["EXIT_TARGET_MISSING"]

    def test_validation_result_passed_no_errors(self):
        """Passed validation should have no errors."""
        result = ValidationResult(passed=True)
        assert result.passed is True
        assert len(result.errors) == 0
        assert result.error_codes == []
