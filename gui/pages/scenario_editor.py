"""Phase A: Scenario Editor.

Features:
- Load scenarios from registry.yaml
- Edit scenario JSON (locations/exits/objects/characters)
- Show validation results
- Show world_summary/hash in right pane
"""

import json
from pathlib import Path
from typing import Optional

from nicegui import ui

from experiments.scenario_registry import (
    ScenarioRegistry,
    SchemaValidationError,
    ValidationResult,
    compute_scenario_hash,
    compute_world_hash,
    generate_world_summary,
    validate_scenario_integrity,
)


class ScenarioEditorState:
    """State for scenario editor."""

    def __init__(self):
        self.registry: Optional[ScenarioRegistry] = None
        self.selected_scenario_id: Optional[str] = None
        self.scenario_data: Optional[dict] = None
        self.scenario_meta: Optional[dict] = None
        self.validation_result: Optional[ValidationResult] = None
        self.editor_content: str = ""
        self.is_dirty: bool = False

    def load_registry(self) -> list[str]:
        """Load registry and return scenario IDs."""
        try:
            self.registry = ScenarioRegistry()
            entries = self.registry.list_scenarios()
            return [e.scenario_id for e in entries]
        except Exception as e:
            return [f"Error: {e}"]

    def load_scenario(self, scenario_id: str) -> tuple[bool, str]:
        """Load scenario by ID."""
        if not self.registry:
            return False, "Registry not loaded"

        try:
            self.scenario_data, self.scenario_meta = self.registry.load_scenario(scenario_id)
            self.selected_scenario_id = scenario_id

            if self.scenario_data:
                self.editor_content = json.dumps(self.scenario_data, indent=2, ensure_ascii=False)
                self.validate()
            else:
                self.editor_content = "# Built-in default scenario (no file)"
                self.validation_result = ValidationResult(passed=True)

            self.is_dirty = False
            return True, "Loaded successfully"
        except SchemaValidationError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error: {e}"

    def validate(self) -> ValidationResult:
        """Validate current scenario data."""
        if self.scenario_data:
            self.validation_result = validate_scenario_integrity(self.scenario_data)
        else:
            self.validation_result = ValidationResult(passed=True)
        return self.validation_result

    def parse_and_validate(self, content: str) -> tuple[bool, str]:
        """Parse JSON content and validate."""
        try:
            self.scenario_data = json.loads(content)
            self.editor_content = content
            self.validate()
            self.is_dirty = True
            return True, "Valid JSON"
        except json.JSONDecodeError as e:
            return False, f"JSON Error: {e}"

    def save_scenario(self) -> tuple[bool, str]:
        """Save scenario to file."""
        if not self.registry or not self.selected_scenario_id:
            return False, "No scenario selected"

        if self.selected_scenario_id == "default":
            return False, "Cannot save built-in default"

        try:
            resolved_path, _ = self.registry.resolve(self.selected_scenario_id)
            if resolved_path:
                with open(resolved_path, "w", encoding="utf-8") as f:
                    json.dump(self.scenario_data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                self.is_dirty = False
                return True, f"Saved to {resolved_path}"
            return False, "No file path"
        except Exception as e:
            return False, f"Save error: {e}"

    def get_world_summary(self) -> dict:
        """Get world summary from scenario data."""
        if not self.scenario_data:
            return {"counts": {}, "objects_top10": [], "locations": []}

        # Convert scenario_data to world_state format
        locations = self.scenario_data.get("locations", {})
        characters = self.scenario_data.get("characters", {})

        # Collect all props
        props = {}
        for loc_name, loc_data in locations.items():
            for prop in loc_data.get("props", []):
                props[prop] = {"location": loc_name}

        world_state = {
            "locations": locations,
            "characters": characters,
            "props": props,
        }

        return generate_world_summary(world_state)

    def get_hashes(self) -> tuple[str, str]:
        """Get scenario_hash and world_hash."""
        scenario_hash = compute_scenario_hash(self.scenario_data) if self.scenario_data else "N/A"

        # Build world_state for hash
        if self.scenario_data:
            locations = self.scenario_data.get("locations", {})
            characters = self.scenario_data.get("characters", {})
            props = {}
            for loc_name, loc_data in locations.items():
                for prop in loc_data.get("props", []):
                    props[prop] = {"location": loc_name}
            world_state = {"locations": locations, "characters": characters, "props": props}
            world_hash = compute_world_hash(world_state)
        else:
            world_hash = "N/A"

        return scenario_hash, world_hash


def create_scenario_editor_page():
    """Create the scenario editor page content."""
    state = ScenarioEditorState()

    # UI containers for dynamic updates
    validation_container = ui.column()
    summary_container = ui.column()
    editor_container = ui.column()

    def update_validation_display():
        """Update validation result display."""
        validation_container.clear()
        with validation_container:
            if state.validation_result is None:
                ui.label("No validation yet").classes("text-grey")
            elif state.validation_result.passed:
                ui.label("Validation: PASSED").classes("text-positive text-bold")
            else:
                ui.label("Validation: FAILED").classes("text-negative text-bold")
                for err in state.validation_result.errors:
                    with ui.row().classes("items-center"):
                        ui.badge(err.code.value, color="negative")
                        ui.label(err.message).classes("text-caption")

    def update_summary_display():
        """Update world summary display."""
        summary_container.clear()
        with summary_container:
            summary = state.get_world_summary()
            scenario_hash, world_hash = state.get_hashes()

            ui.label("World Summary").classes("text-h6")
            ui.separator()

            # Hashes
            with ui.row():
                ui.label("scenario_hash:").classes("text-bold")
                ui.label(scenario_hash[:8] if scenario_hash != "N/A" else "N/A").classes("font-mono")
            with ui.row():
                ui.label("world_hash:").classes("text-bold")
                ui.label(world_hash[:8] if world_hash != "N/A" else "N/A").classes("font-mono")

            ui.separator()

            # Counts
            counts = summary.get("counts", {})
            ui.label("Counts").classes("text-subtitle1")
            with ui.row():
                ui.badge(f"Locations: {counts.get('locations', 0)}", color="blue")
                ui.badge(f"Objects: {counts.get('objects', 0)}", color="green")
                ui.badge(f"Characters: {counts.get('characters', 0)}", color="orange")

            # Locations
            ui.label("Locations").classes("text-subtitle1 q-mt-md")
            for loc in summary.get("locations", []):
                ui.label(f"  - {loc}")

            # Objects (top 10)
            ui.label("Objects (top 10)").classes("text-subtitle1 q-mt-md")
            for obj in summary.get("objects_top10", []):
                ui.label(f"  - {obj}")

    def update_editor_display():
        """Update editor display."""
        editor_container.clear()
        with editor_container:
            if state.selected_scenario_id == "default":
                ui.label("Built-in default scenario (read-only)").classes("text-grey")
                return

            editor = ui.textarea(
                label="Scenario JSON",
                value=state.editor_content,
            ).classes("w-full font-mono").style("min-height: 400px")

            def on_change(e):
                ok, msg = state.parse_and_validate(e.value)
                if ok:
                    update_validation_display()
                    update_summary_display()

            editor.on("blur", on_change)

            with ui.row():
                def save_click():
                    ok, msg = state.save_scenario()
                    if ok:
                        ui.notify(msg, type="positive")
                    else:
                        ui.notify(msg, type="negative")

                ui.button("Save", on_click=save_click, color="primary")
                ui.button("Validate", on_click=lambda: (state.validate(), update_validation_display()))

    def on_scenario_select(scenario_id: str):
        """Handle scenario selection."""
        ok, msg = state.load_scenario(scenario_id)
        if ok:
            update_editor_display()
            update_validation_display()
            update_summary_display()
            ui.notify(f"Loaded: {scenario_id}", type="positive")
        else:
            ui.notify(msg, type="negative")

    # Main layout
    with ui.row().classes("w-full"):
        # Left panel: Scenario list + Editor
        with ui.column().classes("w-2/3"):
            ui.label("Scenario Editor").classes("text-h5")

            # Scenario selector
            scenario_ids = state.load_registry()
            with ui.row().classes("items-center"):
                ui.label("Select Scenario:")
                scenario_select = ui.select(
                    options=scenario_ids,
                    label="Scenario",
                    on_change=lambda e: on_scenario_select(e.value),
                ).classes("w-64")

            ui.separator()

            # Validation display
            with validation_container:
                ui.label("Select a scenario to begin").classes("text-grey")

            ui.separator()

            # Editor
            with editor_container:
                ui.label("Select a scenario to edit").classes("text-grey")

        # Right panel: World summary
        with ui.column().classes("w-1/3 q-pl-md"):
            with summary_container:
                ui.label("World Summary").classes("text-h6")
                ui.label("Select a scenario to view summary").classes("text-grey")
