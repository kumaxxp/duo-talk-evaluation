"""Tests for hakoniwa CLI hash mismatch diagnostics."""

import json
import pytest
from pathlib import Path

from hakoniwa.cli import _diagnose_hash_mismatch, _validate_play_state
from hakoniwa.serializer.canonical import compute_hash


class TestDiagnoseHashMismatch:
    """Tests for _diagnose_hash_mismatch function."""

    def test_broken_json_returns_parse_error(self):
        """Broken JSON should return JSON parse failed message."""
        broken_json = '{"key": "value"'  # Missing closing brace

        result = _diagnose_hash_mismatch(broken_json)

        assert "JSON parse failed" in result

    def test_invalid_schema_version_returns_schema_error(self):
        """Invalid schema_version should return schema error message."""
        invalid_schema = json.dumps({
            "schema_version": "9.9.9",
            "scenario_name": "test",
            "current_location": "start",
            "holding": [],
        })

        result = _diagnose_hash_mismatch(invalid_schema)

        assert "schema_version" in result
        assert "9.9.9" in result
        assert "not supported" in result
        assert "1.0.0" in result  # Expected version

    def test_missing_schema_version_returns_missing_field(self):
        """Missing schema_version should return missing field message."""
        no_schema = json.dumps({
            "scenario_name": "test",
            "current_location": "start",
            "holding": [],
        })

        result = _diagnose_hash_mismatch(no_schema)

        assert "schema_version" in result
        assert "Missing" in result

    def test_missing_required_fields_returns_missing_fields(self):
        """Missing required fields should be reported."""
        missing_fields = json.dumps({
            "schema_version": "1.0.0",
            # Missing: scenario_name, current_location, holding
        })

        result = _diagnose_hash_mismatch(missing_fields)

        assert "Missing" in result
        assert "scenario_name" in result or "current_location" in result or "holding" in result

    def test_valid_structure_returns_file_modified(self):
        """Valid structure with hash mismatch should return file modified message."""
        valid_content = json.dumps({
            "schema_version": "1.0.0",
            "scenario_name": "test",
            "current_location": "start",
            "holding": ["item"],
        })

        result = _diagnose_hash_mismatch(valid_content)

        assert "modified" in result.lower() or "edited" in result.lower()


class TestValidatePlayStateHashMismatchDetail:
    """Tests for _validate_play_state hash mismatch detail output."""

    def test_broken_json_shows_detail(self, tmp_path):
        """Broken JSON should show detail in error list."""
        state_file = tmp_path / "broken.json"
        hash_file = tmp_path / "broken.json.sha256"

        # Write valid content first, then corrupt it
        valid_content = '{"schema_version": "1.0.0"}'
        state_file.write_text(valid_content, encoding="utf-8")
        hash_file.write_text(compute_hash(valid_content), encoding="utf-8")

        # Corrupt the JSON
        state_file.write_text('{"broken": ', encoding="utf-8")

        is_valid, errors, data = _validate_play_state(state_file)

        assert is_valid is False
        assert data is None
        assert any("Hash mismatch" in e for e in errors)
        assert any("Detail:" in e and "JSON parse failed" in e for e in errors)

    def test_invalid_schema_version_shows_detail(self, tmp_path):
        """Invalid schema_version should show detail in error list."""
        state_file = tmp_path / "bad_schema.json"
        hash_file = tmp_path / "bad_schema.json.sha256"

        # Write valid content first
        valid_content = json.dumps({
            "schema_version": "1.0.0",
            "scenario_name": "test",
            "current_location": "start",
            "holding": [],
        })
        state_file.write_text(valid_content, encoding="utf-8")
        hash_file.write_text(compute_hash(valid_content), encoding="utf-8")

        # Change schema_version
        invalid_content = json.dumps({
            "schema_version": "9.9.9",
            "scenario_name": "test",
            "current_location": "start",
            "holding": [],
        })
        state_file.write_text(invalid_content, encoding="utf-8")

        is_valid, errors, data = _validate_play_state(state_file)

        assert is_valid is False
        assert data is None
        assert any("Hash mismatch" in e for e in errors)
        assert any("Detail:" in e and "schema_version" in e and "9.9.9" in e for e in errors)

    def test_file_edited_shows_detail(self, tmp_path):
        """Valid structure with hash mismatch shows file modified detail."""
        state_file = tmp_path / "edited.json"
        hash_file = tmp_path / "edited.json.sha256"

        # Write valid content
        original_content = json.dumps({
            "schema_version": "1.0.0",
            "scenario_name": "test",
            "current_location": "start",
            "holding": [],
        })
        state_file.write_text(original_content, encoding="utf-8")
        hash_file.write_text(compute_hash(original_content), encoding="utf-8")

        # Edit content (valid structure, different values)
        edited_content = json.dumps({
            "schema_version": "1.0.0",
            "scenario_name": "test",
            "current_location": "different_location",
            "holding": ["iron_key"],
        })
        state_file.write_text(edited_content, encoding="utf-8")

        is_valid, errors, data = _validate_play_state(state_file)

        assert is_valid is False
        assert data is None
        assert any("Hash mismatch" in e for e in errors)
        assert any("Detail:" in e and ("modified" in e.lower() or "edited" in e.lower()) for e in errors)

    def test_valid_file_passes(self, tmp_path):
        """Valid file with matching hash should pass."""
        state_file = tmp_path / "valid.json"
        hash_file = tmp_path / "valid.json.sha256"

        content = json.dumps({
            "schema_version": "1.0.0",
            "scenario_name": "test",
            "current_location": "start",
            "holding": [],
        })
        state_file.write_text(content, encoding="utf-8")
        hash_file.write_text(compute_hash(content), encoding="utf-8")

        is_valid, errors, data = _validate_play_state(state_file)

        assert is_valid is True
        assert errors == []
        assert data is not None
        assert data["schema_version"] == "1.0.0"
