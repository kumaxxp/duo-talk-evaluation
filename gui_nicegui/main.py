"""NiceGUI main application for duo-talk evaluation.

MVP+ Features:
- Scenario selection from registry.yaml with hash display
- Run execution panel (profile selection, status)
- Fast triage viewer (issue turns, diffs)
- Demo Pack runner with comparison and export
"""

import asyncio
import sys
from pathlib import Path

from nicegui import ui

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = PROJECT_ROOT / "experiments" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results"
REGISTRY_PATH = SCENARIOS_DIR / "registry.yaml"

# Import data layer
from gui_nicegui.data.scenarios import list_scenarios, load_scenario, get_scenario_summary
from gui_nicegui.data.registry import load_registry, get_scenario_hash
from gui_nicegui.data.results import (
    list_runs, load_turns_log, get_run_info,
    get_run_statistics, filter_issue_turns
)
from gui_nicegui.data.turns import to_view_model
from gui_nicegui.data.diff import generate_repair_diff, generate_speech_diff
from gui_nicegui.components.timeline import (
    create_timeline, create_mini_timeline, turns_to_timeline_items, TimelineItem
)
from gui_nicegui.components.diff_viewer import (
    create_diff_viewer, create_inline_diff, create_change_summary, create_change_badge
)
from gui_nicegui.data.guidance import extract_available_from_card
from gui_nicegui.data.pack import get_demo_scenarios, create_pack_run_id, get_pack_run_dir
from gui_nicegui.data.latest import save_latest_pointer, load_latest_pointer
from gui_nicegui.data.compare import compare_run_meta, compare_metrics
from gui_nicegui.data.export import create_export_zip, create_pack_export_zip, collect_export_files
from gui_nicegui.data.runner import build_runner_command


class AppState:
    """Application state."""

    def __init__(self):
        self.selected_scenario: str | None = None
        self.selected_run: str | None = None
        self.profile: str = "dev"
        self.running: bool = False
        self.log_output: str = ""
        self.last_result_dir: str = ""
        # Demo Pack state
        self.pack_running: bool = False
        self.pack_log: str = ""
        self.pack_completed: list[str] = []
        self.show_compare: bool = True
        self.auto_open_issues: bool = True  # Auto-open Issues Only after pack completion
        self.last_pack_result_dirs: list[Path] = []  # Track result dirs from last pack run


state = AppState()


def create_scenario_panel():
    """Create scenario selection panel with registry support."""
    with ui.card().classes("w-full"):
        ui.label("Scenario Selection").classes("text-lg font-bold")

        # Load from registry
        registry = load_registry(REGISTRY_PATH) if REGISTRY_PATH.exists() else []
        scenarios = list_scenarios(SCENARIOS_DIR) if SCENARIOS_DIR.exists() else []

        if not registry and not scenarios:
            ui.label("No scenarios found").classes("text-gray-500")
            return

        # Use registry entries for selection
        if registry:
            scenario_ids = [s.get("scenario_id", "unknown") for s in registry]
            options = scenario_ids
        else:
            options = [s.get("name", "unknown") for s in scenarios]

        select = ui.select(
            options=options,
            label="Select Scenario",
            on_change=lambda e: setattr(state, "selected_scenario", e.value),
        ).classes("w-full")

        # Summary container
        summary_container = ui.column().classes("w-full mt-2")

        def update_summary(scenario_id):
            summary_container.clear()

            # Find registry entry
            reg_entry = next(
                (r for r in registry if r.get("scenario_id") == scenario_id), None
            )

            # Find scenario data
            scenario_path = SCENARIOS_DIR / f"{scenario_id}.json"
            if reg_entry and reg_entry.get("path"):
                scenario_path = SCENARIOS_DIR / reg_entry["path"]

            scenario = None
            if scenario_path.exists():
                scenario = load_scenario(scenario_path)

            with summary_container:
                if reg_entry:
                    ui.label(reg_entry.get("description", "")).classes(
                        "text-sm text-gray-600"
                    )
                    with ui.row().classes("gap-2"):
                        ui.badge(reg_entry.get("recommended_profile", "dev")).props(
                            "color=blue"
                        )
                        for tag in reg_entry.get("tags", [])[:3]:
                            ui.badge(tag).props("color=grey outline")

                if scenario:
                    summary = get_scenario_summary(scenario)
                    scenario_hash = get_scenario_hash(scenario)

                    ui.label(
                        f"Locations: {summary['location_count']} | "
                        f"Characters: {summary['character_count']}"
                    ).classes("text-sm")

                    ui.label(f"Hash: {scenario_hash}").classes(
                        "text-xs font-mono text-gray-400"
                    )

        select.on_value_change(lambda e: update_summary(e.value))


def create_execution_panel():
    """Create execution control panel."""
    with ui.card().classes("w-full"):
        ui.label("Execution").classes("text-lg font-bold")

        with ui.row().classes("w-full gap-4 items-center"):
            ui.select(
                options=["dev", "gate", "full"],
                value="dev",
                label="Profile",
                on_change=lambda e: setattr(state, "profile", e.value),
            ).classes("w-32")

            ui.button("Run", on_click=run_experiment, icon="play_arrow").props(
                "color=primary"
            )

        # Status display
        status_label = ui.label("").classes("text-sm text-gray-500")
        status_label.bind_text_from(state, "log_output", lambda x: x.split("\n")[-1] if x else "Ready")

        # Result dir display
        result_label = ui.label("").classes("text-xs font-mono text-green-600")
        result_label.bind_text_from(state, "last_result_dir")


async def run_experiment():
    """Run the experiment with selected parameters."""
    if not state.selected_scenario:
        ui.notify("Please select a scenario first", type="warning")
        return

    if state.running:
        ui.notify("Experiment already running", type="warning")
        return

    state.running = True
    state.log_output = f"Starting {state.selected_scenario} ({state.profile})..."
    state.last_result_dir = ""

    try:
        # Build command with correct environment (PYTHONPATH, experiment_id)
        runner = build_runner_command(
            scenario_id=state.selected_scenario,
            profile=state.profile,
            project_root=PROJECT_ROOT,
        )

        process = await asyncio.create_subprocess_exec(
            *runner["cmd"],
            cwd=runner["cwd"],
            env=runner["env"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded = line.decode()
            state.log_output = decoded.strip()
            # Capture result dir
            if "results/" in decoded:
                import re
                match = re.search(r"results/[\w_]+", decoded)
                if match:
                    state.last_result_dir = match.group(0)

        await process.wait()

        if process.returncode == 0:
            state.log_output = f"Done (exit {process.returncode})"
            ui.notify("Experiment completed!", type="positive")
        else:
            state.log_output = f"Failed (exit {process.returncode})"
            ui.notify(f"Experiment failed with exit code {process.returncode}", type="negative")

        refresh_results()

    except Exception as e:
        state.log_output = f"Error: {e}"
        ui.notify(f"Error: {e}", type="negative")

    finally:
        state.running = False


# Global reference for refresh
results_container = None


def create_results_panel():
    """Create results viewer panel with fast triage."""
    global results_container

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Results").classes("text-lg font-bold")
            ui.button("Refresh", on_click=refresh_results, icon="refresh").props(
                "flat dense"
            )

        results_container = ui.column().classes("w-full")
        refresh_results()


def refresh_results():
    """Refresh the results list."""
    if results_container is None:
        return

    results_container.clear()

    if not RESULTS_DIR.exists():
        with results_container:
            ui.label("No results directory").classes("text-gray-500")
        return

    runs = list_runs(RESULTS_DIR)

    if not runs:
        with results_container:
            ui.label("No runs found").classes("text-gray-500")
        return

    with results_container:
        for run in runs[:10]:
            run_path = Path(run["path"])
            info = get_run_info(run_path)
            stats = get_run_statistics(run_path)

            # Color based on issues
            has_issues = stats["retry_count"] > 0 or stats["format_break_count"] > 0

            with ui.expansion(
                run["dir_name"],
                icon="folder" if not has_issues else "warning",
            ).classes("w-full"):
                # Stats row
                with ui.row().classes("gap-2 flex-wrap"):
                    ui.badge(f"Turns: {stats['total_turns']}").props("color=primary")
                    if stats["retry_count"]:
                        ui.badge(f"Retry: {stats['retry_count']}").props("color=orange")
                    if stats["format_break_count"]:
                        ui.badge(f"Format: {stats['format_break_count']}").props(
                            "color=red"
                        )
                    if stats["give_up_count"]:
                        ui.badge(f"GiveUp: {stats['give_up_count']}").props(
                            "color=deep-orange"
                        )

                # Mini timeline preview
                turns = load_turns_log(run_path)
                if turns:
                    timeline_items = turns_to_timeline_items(turns)
                    create_mini_timeline(timeline_items, max_display=25)

                ui.label(f"Profile: {info.get('profile', 'N/A')}").classes(
                    "text-xs text-gray-500"
                )

                with ui.row().classes("gap-2 mt-2"):
                    ui.button(
                        "View All",
                        on_click=lambda p=run_path: show_turns_dialog(p, filter_issues=False),
                        icon="list",
                    ).props("flat dense")

                    if has_issues:
                        ui.button(
                            "Issues Only",
                            on_click=lambda p=run_path: show_turns_dialog(
                                p, filter_issues=True, auto_focus_first=True
                            ),
                            icon="error_outline",
                        ).props("flat dense color=orange")


def show_turns_dialog(run_path: Path, filter_issues: bool = False, auto_focus_first: bool = False):
    """Show turns in a dialog with fast triage features.

    Args:
        run_path: Path to run directory
        filter_issues: If True, show only issue turns
        auto_focus_first: If True, auto-expand first issue turn details
    """
    all_turns = load_turns_log(run_path)
    raw_turns = filter_issue_turns(all_turns) if filter_issues else all_turns

    # State for timeline selection
    selected_turn_idx = {"value": -1}
    turn_cards_container = None

    def on_timeline_select(idx: int):
        """Handle timeline item selection."""
        selected_turn_idx["value"] = idx
        if turn_cards_container:
            turn_cards_container.clear()
            with turn_cards_container:
                # Show only selected turn expanded, or all turns
                for i, raw_turn in enumerate(raw_turns):
                    vm = to_view_model(raw_turn)
                    is_selected = i == idx
                    create_turn_card(vm, raw_turn, auto_expand=is_selected)

    with ui.dialog() as dialog, ui.card().classes("w-11/12 max-w-6xl"):
        with ui.row().classes("w-full items-center justify-between"):
            title = f"{'Issues' if filter_issues else 'Turns'} - {run_path.name}"
            ui.label(title).classes("text-lg font-bold")
            ui.label(f"({len(raw_turns)} turns)").classes("text-sm text-gray-500")

        if not raw_turns:
            ui.label("No turns found").classes("text-gray-500")
        else:
            # Timeline at the top (using all turns for context)
            timeline_items = turns_to_timeline_items(all_turns)
            create_timeline(
                timeline_items,
                on_select=on_timeline_select,
                selected_index=selected_turn_idx["value"],
            )

            # Turn cards below
            turn_cards_container = ui.scroll_area().classes("h-[60vh]")
            with turn_cards_container:
                for i, raw_turn in enumerate(raw_turns):
                    vm = to_view_model(raw_turn)
                    # Auto-expand first issue turn when requested
                    is_first = i == 0 and auto_focus_first and filter_issues
                    create_turn_card(vm, raw_turn, auto_expand=is_first)

        ui.button("Close", on_click=dialog.close).props("flat")

    dialog.open()


def create_turn_card(vm: dict, raw_turn: dict, auto_expand: bool = False):
    """Create a turn card with expandable details.

    Args:
        vm: Turn view model
        raw_turn: Raw turn data
        auto_expand: If True, auto-expand details section (for first issue)
    """
    # Determine card style based on issues
    card_class = "w-full mb-2"
    if vm.get("has_retry") or vm.get("has_format_break"):
        card_class += " border-l-4 border-orange-400"
    if vm.get("has_give_up"):
        card_class += " border-l-4 border-red-400"

    with ui.card().classes(card_class):
        # Header row
        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.badge(f"T{vm['turn']}").props("color=primary")
            ui.badge(vm["speaker"]).props(
                f"color={'pink' if vm['speaker'] == 'やな' else 'purple'}"
            )

            # Issue summary badge (fast triage feature)
            issue_summary = vm.get("issue_summary")
            if issue_summary:
                badge_text = issue_summary.get("badge_text", "ISSUE")
                # Color based on error code
                error_code = issue_summary.get("error_code", "")
                if "MISSING" in error_code:
                    badge_color = "deep-orange"
                elif "GIVE_UP" in error_code or error_code == "GIVE_UP":
                    badge_color = "red"
                elif "RETRY" in badge_text:
                    badge_color = "orange"
                else:
                    badge_color = "amber"
                ui.badge(badge_text).props(f"color={badge_color}").classes("text-xs")

            # Legacy issue badges (for backward compat)
            elif vm.get("has_retry"):
                ui.badge("Retry").props("color=orange outline")
            elif vm.get("has_format_break"):
                ui.badge(vm.get("format_break_type", "FORMAT")).props("color=red outline")
            elif vm.get("has_give_up"):
                ui.badge("GiveUp").props("color=deep-orange")

        # Thought (collapsed by default)
        if vm.get("thought"):
            ui.label(f"💭 {vm['thought']}").classes("text-sm text-gray-500 italic")

        # Speech
        if vm.get("speech"):
            ui.label(vm["speech"]).classes("text-base")

        # Expandable details (auto-expand for first issue turn)
        expansion = ui.expansion("Details", icon="info").classes("text-sm").props("dense")
        if auto_expand:
            expansion.value = True
        with expansion:
            create_turn_details(vm, raw_turn)


def create_turn_details(vm: dict, raw_turn: dict):
    """Create expandable details section for a turn."""
    with ui.tabs().classes("w-full") as tabs:
        raw_tab = ui.tab("Raw")
        diff_tab = ui.tab("Diff")
        meta_tab = ui.tab("Meta")

    with ui.tab_panels(tabs, value=raw_tab).classes("w-full"):
        # Raw output panel
        with ui.tab_panel(raw_tab):
            ui.label("raw_output:").classes("text-xs font-bold")
            ui.code(vm.get("raw_output", "")[:500]).classes("text-xs")

            if vm.get("repaired_output"):
                ui.label("repaired_output:").classes("text-xs font-bold mt-2")
                ui.code(vm.get("repaired_output", "")[:500]).classes("text-xs")

        # Diff panel (improved with visual diff viewer)
        with ui.tab_panel(diff_tab):
            has_any_diff = False

            # raw_output vs repaired_output diff
            if vm.get("repaired_output"):
                raw_output = vm.get("raw_output", "")
                repaired_output = vm.get("repaired_output", "")
                if raw_output != repaired_output:
                    has_any_diff = True
                    create_diff_viewer(
                        raw_output,
                        repaired_output,
                        title="🔧 Output Repair",
                        max_length=400,
                    )

            # raw_speech vs final_speech diff
            raw_speech = vm.get("raw_speech", "")
            final_speech = vm.get("final_speech", "")
            if raw_speech and final_speech and raw_speech != final_speech:
                has_any_diff = True
                ui.separator().classes("my-2")
                ui.label("💬 Speech Correction").classes("text-sm font-bold")
                create_inline_diff(raw_speech, final_speech)

            if not has_any_diff:
                ui.label("No differences detected").classes("text-gray-500 text-sm")

        # Meta panel
        with ui.tab_panel(meta_tab):
            # Format break info
            fb = vm.get("format_break", {})
            if fb.get("triggered"):
                with ui.card().classes("w-full bg-orange-50"):
                    ui.label("Format Break").classes("text-xs font-bold")
                    with ui.row().classes("gap-2 flex-wrap"):
                        ui.label(f"Type: {fb.get('type', 'N/A')}").classes("text-xs")
                        ui.label(f"Method: {fb.get('method', 'N/A')}").classes("text-xs")
                        ui.label(f"Steps: {fb.get('steps', 0)}").classes("text-xs")
                    if fb.get("error"):
                        ui.label(f"Error: {fb['error']}").classes("text-xs text-red-600")

            # Guidance cards
            guidance = vm.get("guidance_cards", [])
            if guidance:
                ui.label(f"Guidance Cards ({len(guidance)}):").classes("text-xs font-bold mt-2")
                for card in guidance[:2]:  # Show first 2
                    available = extract_available_from_card(card)
                    with ui.card().classes("w-full bg-blue-50 text-xs"):
                        ui.label(f"Objects: {', '.join(available['objects_here']) or '(none)'}")
                        ui.label(f"Holding: {', '.join(available['holding']) or '(none)'}")
                        ui.label(f"Exits: {', '.join(available['exits']) or '(none)'}")


# Demo Pack UI
demo_pack_container = None


def create_demo_pack_panel():
    """Create Demo Pack runner panel."""
    global demo_pack_container

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Demo Pack").classes("text-lg font-bold")
            with ui.row().classes("gap-2"):
                ui.switch(
                    "Compare",
                    value=True,
                    on_change=lambda e: setattr(state, "show_compare", e.value),
                ).props("dense")
                ui.switch(
                    "Auto-Open Issues",
                    value=True,
                    on_change=lambda e: setattr(state, "auto_open_issues", e.value),
                ).props("dense")

        # Get demo scenarios from registry
        registry = load_registry(REGISTRY_PATH) if REGISTRY_PATH.exists() else []
        demo_scenarios = get_demo_scenarios(registry)

        if not demo_scenarios:
            ui.label("No demo scenarios found (add 'demo' tag in registry.yaml)").classes(
                "text-gray-500 text-sm"
            )
            return

        # Show demo scenario list
        ui.label(f"{len(demo_scenarios)} scenarios:").classes("text-sm text-gray-600")
        with ui.row().classes("gap-1 flex-wrap"):
            for scenario in demo_scenarios:
                ui.badge(scenario.get("scenario_id", "?")).props("color=blue outline")

        # Run button
        with ui.row().classes("gap-2 mt-2"):
            ui.button(
                "Run Demo Pack",
                on_click=lambda: run_demo_pack(demo_scenarios),
                icon="play_circle",
            ).props("color=green")

            ui.button(
                "Export Zip",
                on_click=export_demo_pack,
                icon="download",
            ).props("flat")

        # Progress / status
        status_label = ui.label("").classes("text-sm text-gray-500 mt-2")
        status_label.bind_text_from(state, "pack_log")

        # Results container
        demo_pack_container = ui.column().classes("w-full mt-2")


async def run_demo_pack(demo_scenarios: list):
    """Run all demo pack scenarios sequentially."""
    if state.pack_running:
        ui.notify("Demo Pack already running", type="warning")
        return

    state.pack_running = True
    state.pack_completed = []
    state.pack_log = "Starting Demo Pack..."
    state.last_pack_result_dirs = []

    pack_id = create_pack_run_id()
    pack_dir = get_pack_run_dir(RESULTS_DIR, pack_id)

    try:
        for i, scenario in enumerate(demo_scenarios):
            scenario_id = scenario.get("scenario_id", "unknown")
            state.pack_log = f"[{i+1}/{len(demo_scenarios)}] Running {scenario_id}..."

            # Load previous run data for comparison
            previous = load_latest_pointer(RESULTS_DIR, scenario_id)

            # Build command with correct environment (PYTHONPATH, experiment_id)
            runner = build_runner_command(
                scenario_id=scenario_id,
                profile="dev",
                project_root=PROJECT_ROOT,
            )

            process = await asyncio.create_subprocess_exec(
                *runner["cmd"],
                cwd=runner["cwd"],
                env=runner["env"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            result_dir = None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode().strip()
                if "results/" in decoded:
                    import re
                    match = re.search(r"results/([\w_]+)", decoded)
                    if match:
                        result_dir = RESULTS_DIR / match.group(1)

            await process.wait()

            if result_dir and result_dir.exists():
                state.pack_completed.append(scenario_id)
                state.last_pack_result_dirs.append(result_dir)

                # Get current run statistics
                stats = get_run_statistics(result_dir)

                # Save latest pointer
                pointer_data = {
                    "scenario_id": scenario_id,
                    "run_dir": str(result_dir),
                    "timestamp": result_dir.name,
                    "give_up_count": stats.get("give_up_count", 0),
                    "retry_count": stats.get("retry_count", 0),
                    "format_break_count": stats.get("format_break_count", 0),
                    "total_turns": stats.get("total_turns", 0),
                }
                save_latest_pointer(RESULTS_DIR, scenario_id, pointer_data)

                # Update UI with comparison if enabled
                if state.show_compare and demo_pack_container:
                    update_pack_result(scenario_id, pointer_data, previous)

        state.pack_log = f"Done: {len(state.pack_completed)}/{len(demo_scenarios)} completed"
        ui.notify("Demo Pack completed!", type="positive")
        refresh_results()

        # Auto-open Issues Only view for first scenario with issues
        if state.auto_open_issues and state.last_pack_result_dirs:
            for result_dir in state.last_pack_result_dirs:
                stats = get_run_statistics(result_dir)
                has_issues = (
                    stats["retry_count"] > 0 or
                    stats["give_up_count"] > 0 or
                    stats["format_break_count"] > 0
                )
                if has_issues:
                    ui.notify(f"Opening Issues view for {result_dir.name}", type="info")
                    show_turns_dialog(result_dir, filter_issues=True, auto_focus_first=True)
                    break

    except Exception as e:
        state.pack_log = f"Error: {e}"
        ui.notify(f"Error: {e}", type="negative")

    finally:
        state.pack_running = False


def update_pack_result(scenario_id: str, current: dict, previous: dict | None):
    """Update pack result card with comparison."""
    if demo_pack_container is None:
        return

    with demo_pack_container:
        with ui.card().classes("w-full mb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.badge(scenario_id).props("color=primary")

                # Compare meta
                meta_diff = compare_run_meta(current, previous)

                if meta_diff["is_first_run"]:
                    ui.badge("NEW").props("color=green outline")
                else:
                    # Check for changes
                    if meta_diff.get("world_hash_changed"):
                        ui.badge("World Changed").props("color=orange")
                    if meta_diff.get("scenario_hash_changed"):
                        ui.badge("Scenario Changed").props("color=blue outline")

                    # Metrics comparison
                    if previous:
                        metrics_diff = compare_metrics(current, previous)

                        # Show deltas
                        if metrics_diff["give_up_delta"] != 0:
                            delta = metrics_diff["give_up_delta"]
                            color = "red" if delta > 0 else "green"
                            ui.badge(f"GiveUp: {'+' if delta > 0 else ''}{delta}").props(
                                f"color={color}"
                            )

                        if metrics_diff["retry_delta"] != 0:
                            delta = metrics_diff["retry_delta"]
                            color = "orange" if delta > 0 else "green"
                            ui.badge(f"Retry: {'+' if delta > 0 else ''}{delta}").props(
                                f"color={color}"
                            )

            # Current stats
            with ui.row().classes("gap-1 text-xs text-gray-500"):
                ui.label(f"Turns: {current.get('total_turns', 0)}")
                ui.label(f"| Retry: {current.get('retry_count', 0)}")
                ui.label(f"| Format: {current.get('format_break_count', 0)}")


def export_demo_pack():
    """Export latest demo pack results as zip."""
    registry = load_registry(REGISTRY_PATH) if REGISTRY_PATH.exists() else []
    demo_scenarios = get_demo_scenarios(registry)

    if not demo_scenarios:
        ui.notify("No demo scenarios configured", type="warning")
        return

    # Collect latest runs for each demo scenario
    scenario_dirs = []
    for scenario in demo_scenarios:
        scenario_id = scenario.get("scenario_id", "")
        pointer = load_latest_pointer(RESULTS_DIR, scenario_id)
        if pointer and pointer.get("run_dir"):
            run_dir = Path(pointer["run_dir"])
            if run_dir.exists():
                scenario_dirs.append(run_dir)

    if not scenario_dirs:
        ui.notify("No completed demo runs to export", type="warning")
        return

    # Create export zip
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_path = RESULTS_DIR / f"demo_pack_export_{timestamp}.zip"

    try:
        create_pack_export_zip(RESULTS_DIR, scenario_dirs, export_path)
        ui.notify(f"Exported to {export_path.name}", type="positive")
    except Exception as e:
        ui.notify(f"Export failed: {e}", type="negative")


def create_app():
    """Create the main application."""
    ui.page_title("duo-talk Evaluation GUI")

    with ui.header().classes("bg-blue-600"):
        ui.label("duo-talk Evaluation").classes("text-xl text-white font-bold")
        ui.label("Fast Triage + Demo Pack").classes("text-sm text-blue-200 ml-2")

    with ui.column().classes("w-full p-4 gap-4"):
        with ui.row().classes("w-full gap-4"):
            with ui.column().classes("w-1/3 gap-4"):
                create_scenario_panel()
                create_execution_panel()
                create_demo_pack_panel()

            with ui.column().classes("w-2/3"):
                create_results_panel()


# Create app
create_app()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(port=8080, title="duo-talk Evaluation")
