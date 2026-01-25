"""Phase C: Log Viewer.

Features:
- Turn list (speaker, trigger, repaired, retry_steps, give_up)
- Click for turn details: raw_output / repaired_output / final
- Diff view for format_break (raw vs repaired vs final)
"""

import json
from pathlib import Path
from typing import Optional

from nicegui import ui


class LogViewerState:
    """State for log viewer."""

    def __init__(self):
        self.results_dir = Path("results")
        self.selected_result: Optional[Path] = None
        self.results_data: Optional[dict] = None
        self.selected_run_key: Optional[str] = None
        self.selected_turn: Optional[int] = None

    def get_result_dirs(self) -> list[str]:
        """Get list of result directories."""
        if not self.results_dir.exists():
            return []
        dirs = sorted(
            [d.name for d in self.results_dir.iterdir() if d.is_dir()],
            reverse=True,
        )
        return dirs[:20]  # Limit to recent 20

    def load_result(self, dir_name: str) -> tuple[bool, str]:
        """Load results.json from directory."""
        self.selected_result = self.results_dir / dir_name
        results_json = self.selected_result / "results.json"

        if not results_json.exists():
            return False, f"results.json not found in {dir_name}"

        try:
            with open(results_json, encoding="utf-8") as f:
                self.results_data = json.load(f)
            return True, f"Loaded {dir_name}"
        except Exception as e:
            return False, f"Error loading: {e}"

    def get_runs(self) -> list[str]:
        """Get list of run keys from results."""
        if not self.results_data:
            return []
        return list(self.results_data.get("runs", {}).keys())

    def get_turns(self, run_key: str) -> list[dict]:
        """Get turns for a run."""
        if not self.results_data:
            return []
        run_data = self.results_data.get("runs", {}).get(run_key, {})
        return run_data.get("turns", [])

    def get_turn_summary(self, turn: dict) -> dict:
        """Get summary info for turn display."""
        return {
            "turn_number": turn.get("turn_number", "?"),
            "speaker": turn.get("speaker", "?"),
            "trigger": turn.get("gm_trigger", "none"),
            "repaired": turn.get("format_repaired", False),
            "retry_steps": turn.get("retry_steps", 0),
            "give_up": turn.get("give_up", False),
            "repair_method": turn.get("repair_method"),
        }

    def get_artifacts(self, run_key: str, turn_number: int) -> dict:
        """Get artifact paths for a turn."""
        if not self.selected_result:
            return {}

        # Parse run_key: experiment_id_condition_scenario_seed
        # e.g., "gui_20260125_gate3_test_D_coffee_trap_1"
        artifacts_dir = self.selected_result / "artifacts"

        # Try to find matching artifact directory
        pattern = f"*_{turn_number:03d}_*"
        raw_files = list(artifacts_dir.glob(f"*/turn_{turn_number:03d}_raw_output.txt"))
        parsed_files = list(artifacts_dir.glob(f"*/turn_{turn_number:03d}_parsed.json"))

        artifacts = {}
        if raw_files:
            artifacts["raw_output"] = raw_files[0]
        if parsed_files:
            artifacts["parsed"] = parsed_files[0]

        return artifacts

    def load_artifact(self, path: Path) -> str:
        """Load artifact content."""
        if not path.exists():
            return f"File not found: {path}"
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading: {e}"


def create_log_viewer_page():
    """Create the log viewer page content."""
    state = LogViewerState()

    # UI containers
    runs_container = ui.column()
    turns_container = ui.column()
    detail_container = ui.column()

    def update_runs_display():
        """Update runs list display."""
        runs_container.clear()
        with runs_container:
            runs = state.get_runs()
            if not runs:
                ui.label("No runs found").classes("text-grey")
                return

            for run_key in runs:
                turns = state.get_turns(run_key)

                def select_run(key=run_key):
                    state.selected_run_key = key
                    update_turns_display()

                with ui.card().classes("w-full cursor-pointer hover:bg-gray-100").on("click", select_run):
                    with ui.row().classes("items-center"):
                        ui.label(run_key).classes("text-bold")
                        ui.badge(f"{len(turns)} turns", color="blue")

    def update_turns_display():
        """Update turns list display."""
        turns_container.clear()
        with turns_container:
            if not state.selected_run_key:
                ui.label("Select a run").classes("text-grey")
                return

            ui.label(f"Run: {state.selected_run_key}").classes("text-h6")
            ui.separator()

            turns = state.get_turns(state.selected_run_key)
            if not turns:
                ui.label("No turns found").classes("text-grey")
                return

            # Table header
            with ui.row().classes("w-full bg-gray-100 p-2"):
                ui.label("Turn").classes("w-12 text-bold")
                ui.label("Speaker").classes("w-16 text-bold")
                ui.label("Trigger").classes("w-24 text-bold")
                ui.label("Repaired").classes("w-20 text-bold")
                ui.label("Retry").classes("w-16 text-bold")
                ui.label("GiveUp").classes("w-16 text-bold")

            # Turn rows
            for turn in turns:
                summary = state.get_turn_summary(turn)

                def select_turn(t=turn):
                    state.selected_turn = t.get("turn_number")
                    update_detail_display(t)

                row_class = "w-full p-2 cursor-pointer hover:bg-blue-50"
                if summary["give_up"]:
                    row_class += " bg-red-50"
                elif summary["repaired"]:
                    row_class += " bg-yellow-50"

                with ui.row().classes(row_class).on("click", select_turn):
                    ui.label(str(summary["turn_number"])).classes("w-12")
                    ui.label(summary["speaker"]).classes("w-16")
                    ui.label(summary["trigger"] or "none").classes("w-24")

                    # Repaired indicator
                    if summary["repaired"]:
                        with ui.row().classes("w-20"):
                            ui.icon("build", color="orange")
                            ui.label(summary["repair_method"] or "").classes("text-caption")
                    else:
                        ui.label("-").classes("w-20")

                    ui.label(str(summary["retry_steps"])).classes("w-16")

                    if summary["give_up"]:
                        ui.icon("error", color="red").classes("w-16")
                    else:
                        ui.label("-").classes("w-16")

    def update_detail_display(turn: dict):
        """Update turn detail display."""
        detail_container.clear()
        with detail_container:
            ui.label(f"Turn {turn.get('turn_number', '?')} Details").classes("text-h6")
            ui.separator()

            # Basic info
            with ui.card().classes("w-full"):
                ui.label("Turn Info").classes("text-subtitle1 text-bold")
                with ui.row():
                    ui.label(f"Speaker: {turn.get('speaker', '?')}")
                    ui.label(f"Trigger: {turn.get('gm_trigger', 'none')}")
                    ui.label(f"Retry Steps: {turn.get('retry_steps', 0)}")

                if turn.get("give_up"):
                    ui.label("GIVE UP").classes("text-negative text-bold")

            # Speech content
            with ui.card().classes("w-full q-mt-md"):
                ui.label("Final Speech").classes("text-subtitle1 text-bold")
                speech = turn.get("final_speech") or turn.get("speech", "")
                ui.code(speech, language="text").classes("w-full")

            # Raw vs Repaired (if format_break)
            if turn.get("format_repaired"):
                with ui.card().classes("w-full q-mt-md"):
                    ui.label("Format Break Details").classes("text-subtitle1 text-bold")

                    with ui.row():
                        ui.badge(f"Type: {turn.get('format_break_type', '?')}", color="orange")
                        ui.badge(f"Method: {turn.get('repair_method', '?')}", color="blue")
                        ui.badge(f"Steps: {turn.get('repair_steps', 0)}", color="grey")

                    ui.label("Raw Output").classes("text-caption q-mt-md")
                    raw_output = turn.get("raw_output", "")
                    ui.code(raw_output[:500] + ("..." if len(raw_output) > 500 else ""), language="text").classes("w-full")

                    if turn.get("repaired_output"):
                        ui.label("Repaired Output").classes("text-caption q-mt-md")
                        repaired = turn.get("repaired_output", "")
                        ui.code(repaired[:500] + ("..." if len(repaired) > 500 else ""), language="text").classes("w-full")

            # GM Intervention details
            if turn.get("gm_injection") or turn.get("gm_intervention"):
                with ui.card().classes("w-full q-mt-md"):
                    ui.label("GM Intervention").classes("text-subtitle1 text-bold")

                    if turn.get("fact_cards"):
                        ui.label("Fact Cards:").classes("text-caption")
                        for card in turn.get("fact_cards", []):
                            ui.code(str(card), language="json").classes("w-full")

                    if turn.get("guidance_cards"):
                        ui.label("Guidance Cards:").classes("text-caption")
                        for card in turn.get("guidance_cards", []):
                            ui.code(card, language="text").classes("w-full")

            # Actions
            with ui.card().classes("w-full q-mt-md"):
                ui.label("Actions").classes("text-subtitle1 text-bold")
                actions = turn.get("actions", [])
                if actions:
                    for action in actions:
                        ui.label(f"  - {action}")
                else:
                    ui.label("No actions").classes("text-grey")

    def on_result_select(dir_name: str):
        """Handle result selection."""
        ok, msg = state.load_result(dir_name)
        if ok:
            update_runs_display()
            turns_container.clear()
            with turns_container:
                ui.label("Select a run to view turns").classes("text-grey")
            detail_container.clear()
            ui.notify(msg, type="positive")
        else:
            ui.notify(msg, type="negative")

    # Main layout
    with ui.row().classes("w-full"):
        # Left panel: Result selector + Runs
        with ui.column().classes("w-1/4"):
            ui.label("Log Viewer").classes("text-h5")

            # Result directory selector
            result_dirs = state.get_result_dirs()
            if result_dirs:
                ui.select(
                    options=result_dirs,
                    label="Select Result",
                    on_change=lambda e: on_result_select(e.value),
                ).classes("w-full")
            else:
                ui.label("No results found in results/").classes("text-grey")

            ui.separator()
            ui.label("Runs").classes("text-h6")
            with runs_container:
                ui.label("Select a result directory").classes("text-grey")

        # Middle panel: Turns list
        with ui.column().classes("w-1/4"):
            with turns_container:
                ui.label("Turns").classes("text-h6")
                ui.label("Select a result to view turns").classes("text-grey")

        # Right panel: Turn details
        with ui.column().classes("w-1/2"):
            with detail_container:
                ui.label("Turn Details").classes("text-h6")
                ui.label("Select a turn to view details").classes("text-grey")
