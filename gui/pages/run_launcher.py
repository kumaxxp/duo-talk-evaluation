"""Phase B: Run Launcher.

Features:
- Select profile (dev/gate/full), condition, seeds, turns
- Execute experiment
- Show results path/link
- Jump to run_meta/artifacts/turns_log.json
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from nicegui import ui

from experiments.scenario_registry import ScenarioRegistry

# Profile configurations (from gm_2x2_runner.py)
PROFILE_CONFIG = {
    "dev": {
        "conditions": ["D"],
        "seeds": 1,
        "max_turns": 5,
        "max_tokens": 192,
        "description": "Quick iteration (fastest)",
    },
    "gate": {
        "conditions": ["B", "D"],
        "seeds": 5,
        "max_turns": 10,
        "max_tokens": 256,
        "description": "PR check (statistical)",
    },
    "full": {
        "conditions": ["A", "B", "C", "D"],
        "seeds": 20,
        "max_turns": 10,
        "max_tokens": 300,
        "description": "Production measurement",
    },
}


class RunLauncherState:
    """State for run launcher."""

    def __init__(self):
        self.profile: str = "dev"
        self.conditions: list[str] = ["D"]
        self.seeds: int = 1
        self.max_turns: int = 5
        self.scenario_id: str = "coffee_trap"
        self.mode: str = "real"
        self.llm_model: str = "gemma3:12b"

        self.is_running: bool = False
        self.last_result_path: Optional[Path] = None
        self.output_log: str = ""

    def get_scenarios(self) -> list[str]:
        """Get available scenarios."""
        try:
            registry = ScenarioRegistry()
            return [e.scenario_id for e in registry.list_scenarios()]
        except Exception:
            return ["default", "coffee_trap", "wrong_location", "locked_door"]

    def apply_profile(self, profile: str):
        """Apply profile preset."""
        self.profile = profile
        config = PROFILE_CONFIG.get(profile, PROFILE_CONFIG["dev"])
        self.conditions = config["conditions"]
        self.seeds = config["seeds"]
        self.max_turns = config["max_turns"]

    def build_command(self, experiment_id: str) -> list[str]:
        """Build experiment command."""
        cmd = [
            "python", "-m", "experiments.gm_2x2_runner",
            "--experiment_id", experiment_id,
            "--profile", self.profile,
            "--conditions", ",".join(self.conditions),
            "--scenarios", self.scenario_id,
            "--seeds", str(self.seeds),
            "--max_turns", str(self.max_turns),
            "--mode", self.mode,
            "--llm_model", self.llm_model,
        ]
        return cmd

    def get_expected_result_path(self, experiment_id: str) -> Path:
        """Get expected result path."""
        # Results are saved to results/gm_2x2_{experiment_id}_{timestamp}/
        results_dir = Path("results")
        # Find the most recent matching directory
        pattern = f"gm_2x2_{experiment_id}_*"
        matching = sorted(results_dir.glob(pattern), reverse=True)
        if matching:
            return matching[0]
        return results_dir / f"gm_2x2_{experiment_id}"


def create_run_launcher_page():
    """Create the run launcher page content."""
    state = RunLauncherState()

    # UI containers
    output_container = ui.column()
    result_container = ui.column()

    # Form elements
    profile_select = None
    conditions_select = None
    seeds_input = None
    turns_input = None

    def update_from_profile(profile: str):
        """Update form from profile."""
        state.apply_profile(profile)
        if conditions_select:
            conditions_select.value = state.conditions
        if seeds_input:
            seeds_input.value = state.seeds
        if turns_input:
            turns_input.value = state.max_turns

    def update_output(text: str):
        """Append to output log."""
        state.output_log += text + "\n"
        output_container.clear()
        with output_container:
            ui.code(state.output_log).classes("w-full").style("max-height: 300px; overflow-y: auto")

    def show_results(result_path: Path):
        """Show result links."""
        result_container.clear()
        with result_container:
            ui.label("Results").classes("text-h6 text-positive")
            ui.separator()

            if result_path.exists():
                ui.label(f"Path: {result_path}").classes("font-mono")

                # Links to key files
                report_md = result_path / "REPORT.md"
                results_json = result_path / "results.json"
                conv_report = result_path / "CONVERSATION_REPORT.md"
                artifacts_dir = result_path / "artifacts"

                with ui.column():
                    if report_md.exists():
                        ui.link(
                            "REPORT.md",
                            f"/logs?path={report_md}",
                        ).classes("text-primary")

                    if results_json.exists():
                        ui.link(
                            "results.json",
                            f"/logs?path={results_json}",
                        ).classes("text-primary")

                    if conv_report.exists():
                        ui.link(
                            "CONVERSATION_REPORT.md",
                            f"/logs?path={conv_report}",
                        ).classes("text-primary")

                    if artifacts_dir.exists():
                        ui.label(f"Artifacts: {artifacts_dir}").classes("font-mono text-caption")

                # Open in file manager button
                def open_folder():
                    import platform
                    import subprocess
                    if platform.system() == "Darwin":
                        subprocess.run(["open", str(result_path)])
                    elif platform.system() == "Linux":
                        subprocess.run(["xdg-open", str(result_path)])
                    else:
                        subprocess.run(["explorer", str(result_path)])

                ui.button("Open Folder", on_click=open_folder, color="secondary")
            else:
                ui.label("Result path not found").classes("text-negative")

    async def run_experiment():
        """Run the experiment."""
        if state.is_running:
            ui.notify("Experiment already running", type="warning")
            return

        # Generate experiment ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_id = f"gui_{timestamp}"

        state.is_running = True
        state.output_log = ""
        update_output(f"Starting experiment: {experiment_id}")
        update_output(f"Profile: {state.profile}, Conditions: {state.conditions}")
        update_output(f"Scenario: {state.scenario_id}, Seeds: {state.seeds}, Turns: {state.max_turns}")
        update_output("-" * 50)

        cmd = state.build_command(experiment_id)
        update_output(f"Command: {' '.join(cmd)}")
        update_output("-" * 50)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(Path.cwd()),
            )

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                update_output(line.decode().rstrip())

            await process.wait()

            if process.returncode == 0:
                update_output("-" * 50)
                update_output("Experiment completed successfully!")
                ui.notify("Experiment completed!", type="positive")

                # Find result path
                state.last_result_path = state.get_expected_result_path(experiment_id)
                show_results(state.last_result_path)
            else:
                update_output(f"Experiment failed with code: {process.returncode}")
                ui.notify("Experiment failed", type="negative")

        except Exception as e:
            update_output(f"Error: {e}")
            ui.notify(f"Error: {e}", type="negative")
        finally:
            state.is_running = False

    # Import asyncio for async subprocess
    import asyncio

    # Main layout
    with ui.column().classes("w-full"):
        ui.label("Run Launcher").classes("text-h5")
        ui.separator()

        # Configuration form
        with ui.card().classes("w-full"):
            ui.label("Configuration").classes("text-h6")

            with ui.row().classes("w-full items-center"):
                # Profile
                profile_select = ui.select(
                    options=list(PROFILE_CONFIG.keys()),
                    label="Profile",
                    value=state.profile,
                    on_change=lambda e: update_from_profile(e.value),
                ).classes("w-32")

                # Profile description
                ui.label(PROFILE_CONFIG[state.profile]["description"]).classes("text-caption text-grey")

            with ui.row().classes("w-full items-center"):
                # Conditions
                conditions_select = ui.select(
                    options=["A", "B", "C", "D"],
                    label="Conditions",
                    value=state.conditions,
                    multiple=True,
                    on_change=lambda e: setattr(state, "conditions", e.value),
                ).classes("w-48")

                # Scenario
                scenarios = state.get_scenarios()
                ui.select(
                    options=scenarios,
                    label="Scenario",
                    value=state.scenario_id,
                    on_change=lambda e: setattr(state, "scenario_id", e.value),
                ).classes("w-48")

            with ui.row().classes("w-full items-center"):
                # Seeds
                seeds_input = ui.number(
                    label="Seeds",
                    value=state.seeds,
                    min=1,
                    max=100,
                    on_change=lambda e: setattr(state, "seeds", int(e.value)),
                ).classes("w-24")

                # Max turns
                turns_input = ui.number(
                    label="Max Turns",
                    value=state.max_turns,
                    min=1,
                    max=50,
                    on_change=lambda e: setattr(state, "max_turns", int(e.value)),
                ).classes("w-24")

                # Mode
                ui.select(
                    options=["real", "sim"],
                    label="Mode",
                    value=state.mode,
                    on_change=lambda e: setattr(state, "mode", e.value),
                ).classes("w-24")

                # LLM Model
                ui.input(
                    label="LLM Model",
                    value=state.llm_model,
                    on_change=lambda e: setattr(state, "llm_model", e.value),
                ).classes("w-32")

            ui.separator()

            # Run button
            ui.button(
                "Run Experiment",
                on_click=run_experiment,
                color="primary",
            ).classes("w-full")

        # Output log
        with ui.card().classes("w-full q-mt-md"):
            ui.label("Output Log").classes("text-h6")
            with output_container:
                ui.label("No experiment run yet").classes("text-grey")

        # Results
        with ui.card().classes("w-full q-mt-md"):
            with result_container:
                ui.label("Results will appear here after run").classes("text-grey")
