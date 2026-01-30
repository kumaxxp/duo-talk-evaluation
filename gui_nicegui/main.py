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
from gui_nicegui.components.visual_board import create_visual_board


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
        # Visual Board state (Single Source of Truth)
        self.selected_object: dict | None = None

        # HAKONIWA Console state (Phase 4)
        self.speaker: str = "やな"  # Current speaker selection
        self.topic: str = ""  # Current topic/prompt

        # Dialogue log - list of conversation turns
        self.dialogue_log: list[dict] = [
            {
                "turn": 1,
                "speaker": "やな",
                "thought": "妹と一緒に朝を迎えられて嬉しいな。今日も楽しい一日になりそう。",
                "speech": "おはよう、あゆ〜！今日もいい天気だね！",
                "status": "PASS",
            },
            {
                "turn": 2,
                "speaker": "あゆ",
                "thought": "姉様は相変わらず朝から元気ね。少し眩しいけど、悪くない。",
                "speech": "おはようございます、姉様。...朝から声が大きいですよ。",
                "status": "PASS",
            },
            {
                "turn": 3,
                "speaker": "やな",
                "thought": "あゆったら、素直じゃないんだから。でもそこが可愛いよね。",
                "speech": "えへへ、ごめんね〜。でもあゆの寝癖、可愛いよ？",
                "status": "RETRY",
                "raw_output": "あゆの寝癖可愛い",
                "repaired_output": "えへへ、ごめんね〜。でもあゆの寝癖、可愛いよ？",
            },
        ]

        # Director status - last check result and retry count
        self.director_status: dict = {
            "last_stage": "speech",
            "last_status": "PASS",
            "retry_count": 1,
            "give_up": False,
            "reasons": [],
            "injected_facts": [],
        }

        # World state summary from GM
        self.world_state_summary: dict = {
            "current_location": "寝室",
            "time": "朝 7:00",
            "characters": {
                "やな": {"location": "寝室", "holding": []},
                "あゆ": {"location": "寝室", "holding": []},
            },
            "recent_changes": ["やなが起床した", "あゆが起床した"],
        }

        # Action logs from GM
        self.action_logs: list[dict] = [
            {
                "turn": 1,
                "action": "WAKE_UP",
                "actor": "やな",
                "result": "SUCCESS",
                "description": "やなが起床しました",
            },
            {
                "turn": 2,
                "action": "WAKE_UP",
                "actor": "あゆ",
                "result": "SUCCESS",
                "description": "あゆが起床しました",
            },
        ]

        # Connection status indicators
        self.core_connected: bool = True
        self.director_connected: bool = True
        self.gm_connected: bool = False  # GM requires health check


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

        def on_scenario_change(e):
            update_summary(e.value)
            state.selected_object = None
            _refresh_board()
            _refresh_action_panel()

        select.on_value_change(on_scenario_change)


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
        _refresh_board()
        _refresh_action_panel()

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


def _resolve_scenario_path(scenario_id: str) -> Path | None:
    """Resolve scenario_id to file path using registry, then fallback."""
    # 1. Registry lookup (authoritative)
    registry = load_registry(REGISTRY_PATH) if REGISTRY_PATH.exists() else []
    for entry in registry:
        if entry.get("scenario_id") == scenario_id and entry.get("path"):
            candidate = SCENARIOS_DIR / entry["path"]
            if candidate.exists():
                return candidate

    # 2. Direct filename
    candidate = SCENARIOS_DIR / f"{scenario_id}.json"
    if candidate.exists():
        return candidate

    # 3. scn_ prefix
    candidate = SCENARIOS_DIR / f"scn_{scenario_id}.json"
    if candidate.exists():
        return candidate

    return None


def _get_scenario_objects(scenario_id: str | None) -> list[dict]:
    """Extract objects from the selected scenario for Visual Board display."""
    if not scenario_id:
        return []

    scenario_path = _resolve_scenario_path(scenario_id)
    if not scenario_path:
        return []

    scenario = load_scenario(scenario_path)
    if not scenario:
        return []

    objects: list[dict] = []

    # Extract characters
    characters = scenario.get("characters", {})
    for char_name, char_data in characters.items():
        obj: dict = {"id": char_name, "name": char_name, "type": "character"}
        if isinstance(char_data, dict):
            obj["state"] = char_data.get("location", "")
        objects.append(obj)

    # Extract props from all locations
    locations = scenario.get("locations", {})
    for loc_name, loc_data in locations.items():
        if not isinstance(loc_data, dict):
            continue
        props = loc_data.get("props", [])
        for prop_name in props:
            objects.append({"id": prop_name, "name": prop_name, "type": "item"})

        # Locked exits (doors)
        locked = loc_data.get("locked_exits", {})
        for _exit_id, exit_data in locked.items():
            if isinstance(exit_data, dict):
                door_name = exit_data.get("door_name", _exit_id)
                objects.append({
                    "id": door_name,
                    "name": door_name,
                    "type": "door",
                    "state": "locked" if exit_data.get("locked") else "unlocked",
                })

    return objects


# Visual Board panel + Action Panel references
board_container = None
action_container = None


def _on_object_select(obj: dict) -> None:
    """Handle object selection from Visual Board."""
    state.selected_object = obj
    _refresh_action_panel()
    _refresh_board()


def _refresh_board() -> None:
    """Re-render the Visual Board."""
    if board_container is None:
        return
    board_container.clear()
    objects = _get_scenario_objects(state.selected_scenario)
    selected_id = None
    if state.selected_object:
        selected_id = state.selected_object.get("id") or state.selected_object.get("name")
    with board_container:
        if objects:
            create_visual_board(objects, on_select=_on_object_select, selected_id=selected_id)
        else:
            ui.label("Select a scenario to display objects").classes("text-sm text-gray-400")


def _refresh_action_panel() -> None:
    """Re-render the Action Panel for the selected object."""
    if action_container is None:
        return
    action_container.clear()
    obj = state.selected_object
    with action_container:
        if not obj:
            ui.label("No object selected").classes("text-sm text-gray-400")
            return

        from hakoniwa.ui.zone_resolver import icon_for, label_for
        icon = icon_for(obj)
        name = label_for(obj)

        ui.label(f"{icon} {name}").classes("text-lg font-bold")

        # Object details
        obj_type = obj.get("type", "unknown")
        ui.label(f"Type: {obj_type}").classes("text-sm text-gray-600")

        obj_state = obj.get("state")
        if obj_state:
            state_str = obj_state if isinstance(obj_state, str) else ", ".join(str(s) for s in obj_state)
            ui.label(f"State: {state_str}").classes("text-sm text-gray-600")

        obj_id = obj.get("id", "")
        ui.label(f"ID: {obj_id}").classes("text-xs text-gray-400 font-mono")


def create_visual_board_panel() -> None:
    """Create the Visual Board + Action Panel section."""
    global board_container, action_container

    with ui.card().classes("w-full"):
        ui.label("Visual Board").classes("text-lg font-bold")
        board_container = ui.column().classes("w-full items-center")
        _refresh_board()

    with ui.card().classes("w-full"):
        ui.label("Selected Object").classes("text-lg font-bold")
        action_container = ui.column().classes("w-full")
        _refresh_action_panel()


# ============================================================
# HAKONIWA Console Components (Phase 4)
# ============================================================

# Main Stage container reference
main_stage_container = None


def _refresh_main_stage() -> None:
    """Re-render the Main Stage dialogue cards."""
    if main_stage_container is None:
        return
    main_stage_container.clear()
    with main_stage_container:
        for turn_data in state.dialogue_log:
            _create_dialogue_card(turn_data)


def _create_dialogue_card(turn_data: dict) -> None:
    """Create a single dialogue card for Main Stage."""
    turn_num = turn_data.get("turn", 0)
    speaker = turn_data.get("speaker", "?")
    thought = turn_data.get("thought", "")
    speech = turn_data.get("speech", "")
    status = turn_data.get("status", "PASS")

    # Card styling based on status
    border_class = ""
    if status == "RETRY":
        border_class = " border-l-4 border-orange-400"
    elif status == "GIVE_UP":
        border_class = " border-l-4 border-red-400"

    # Speaker-based color
    speaker_color = "pink" if speaker == "やな" else "purple"

    with ui.card().classes(f"w-full mb-2{border_class}"):
        # Header row
        with ui.row().classes("items-center gap-2"):
            ui.badge(f"T{turn_num}").props("color=primary")
            ui.badge(speaker).props(f"color={speaker_color}")

            # Status badge
            if status == "PASS":
                ui.badge("PASS").props("color=green outline")
            elif status == "RETRY":
                ui.badge("RETRY").props("color=orange")
            elif status == "GIVE_UP":
                ui.badge("GIVE_UP").props("color=red")

        # Thought (collapsed by default)
        if thought:
            with ui.expansion("Thought", icon="psychology").classes("text-sm").props("dense"):
                ui.label(thought).classes("text-gray-600 italic")

        # Speech
        if speech:
            ui.label(speech).classes("text-base mt-1")

        # Show repair diff if exists
        if turn_data.get("raw_output") and turn_data.get("repaired_output"):
            with ui.expansion("Repair Diff", icon="compare").classes("text-xs").props("dense"):
                ui.label("Raw:").classes("text-xs font-bold")
                ui.code(turn_data["raw_output"]).classes("text-xs")
                ui.label("Repaired:").classes("text-xs font-bold mt-1")
                ui.code(turn_data["repaired_output"]).classes("text-xs")


def create_control_panel() -> None:
    """Create Control Panel (left pane) for HAKONIWA Console."""
    with ui.card().classes("w-full"):
        ui.label("Control Panel").classes("text-lg font-bold")

        # Connection status indicators
        with ui.row().classes("gap-2 mb-2"):
            core_color = "green" if state.core_connected else "red"
            director_color = "green" if state.director_connected else "red"
            gm_color = "green" if state.gm_connected else "grey"

            ui.badge("Core").props(f"color={core_color}")
            ui.badge("Director").props(f"color={director_color}")
            ui.badge("GM").props(f"color={gm_color}")

        ui.separator()

        # Profile selection
        ui.select(
            options=["dev", "gate", "full"],
            value=state.profile,
            label="Profile",
            on_change=lambda e: setattr(state, "profile", e.value),
        ).classes("w-full")

        # Speaker selection
        ui.select(
            options=["やな", "あゆ"],
            value=state.speaker,
            label="Speaker",
            on_change=lambda e: setattr(state, "speaker", e.value),
        ).classes("w-full")

        # Topic input
        ui.input(
            label="Topic / Prompt",
            value=state.topic,
            on_change=lambda e: setattr(state, "topic", e.value),
        ).classes("w-full")

        ui.separator()

        # Manual trigger buttons
        ui.label("Manual Triggers").classes("text-sm font-bold mt-2")

        with ui.column().classes("w-full gap-2"):
            ui.button(
                "Generate Thought",
                on_click=lambda: ui.notify("Generate Thought (Step2で実装)", type="info"),
                icon="psychology",
            ).classes("w-full").props("outline")

            ui.button(
                "Generate Utterance",
                on_click=lambda: ui.notify("Generate Utterance (Step2で実装)", type="info"),
                icon="chat",
            ).classes("w-full").props("outline")

            ui.button(
                "One-Step",
                on_click=lambda: ui.notify("One-Step (Step4で実装)", type="info"),
                icon="play_arrow",
            ).classes("w-full").props("color=primary")

        ui.separator()

        # Director status display
        ui.label("Director Status").classes("text-sm font-bold mt-2")
        with ui.column().classes("w-full text-xs"):
            ds = state.director_status
            ui.label(f"Last Stage: {ds.get('last_stage', 'N/A')}")
            ui.label(f"Last Status: {ds.get('last_status', 'N/A')}")
            ui.label(f"Retry Count: {ds.get('retry_count', 0)}")
            if ds.get("give_up"):
                ui.badge("GIVE_UP").props("color=red")


def create_main_stage() -> None:
    """Create Main Stage (center pane) for HAKONIWA Console."""
    global main_stage_container

    with ui.card().classes("w-full h-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Main Stage").classes("text-lg font-bold")
            ui.badge(f"{len(state.dialogue_log)} turns").props("color=blue outline")

        # Character placeholders (future: actual images)
        with ui.row().classes("w-full justify-center gap-8 my-2"):
            with ui.column().classes("items-center"):
                ui.icon("face", size="48px").classes("text-pink-400")
                ui.label("やな").classes("text-sm")
            with ui.column().classes("items-center"):
                ui.icon("face", size="48px").classes("text-purple-400")
                ui.label("あゆ").classes("text-sm")

        ui.separator()

        # Dialogue log scroll area
        with ui.scroll_area().classes("h-[50vh]"):
            main_stage_container = ui.column().classes("w-full")
            _refresh_main_stage()


def create_god_view() -> None:
    """Create God View (right pane) for HAKONIWA Console."""
    with ui.card().classes("w-full"):
        ui.label("God View (GM Monitor)").classes("text-lg font-bold")

        # World State Summary
        ui.label("World State").classes("text-sm font-bold mt-2")
        ws = state.world_state_summary

        with ui.card().classes("w-full bg-gray-50"):
            with ui.column().classes("text-xs gap-1"):
                ui.label(f"Location: {ws.get('current_location', 'N/A')}")
                ui.label(f"Time: {ws.get('time', 'N/A')}")

                # Characters
                chars = ws.get("characters", {})
                for char_name, char_data in chars.items():
                    loc = char_data.get("location", "?")
                    holding = char_data.get("holding", [])
                    holding_str = ", ".join(holding) if holding else "(none)"
                    ui.label(f"  {char_name}: {loc} [holding: {holding_str}]")

        # Recent changes (highlighted)
        changes = ws.get("recent_changes", [])
        if changes:
            ui.label("Recent Changes").classes("text-sm font-bold mt-2")
            with ui.card().classes("w-full bg-yellow-50"):
                for change in changes[-3:]:  # Show last 3
                    ui.label(f"• {change}").classes("text-xs")

        ui.separator()

        # Action Log
        ui.label("Action Log").classes("text-sm font-bold mt-2")

        with ui.scroll_area().classes("h-32"):
            for action in reversed(state.action_logs[-5:]):  # Show last 5, newest first
                turn_num = action.get("turn", 0)
                action_type = action.get("action", "?")
                actor = action.get("actor", "?")
                result = action.get("result", "?")
                desc = action.get("description", "")

                result_color = "green" if result == "SUCCESS" else "orange"

                with ui.row().classes("items-center gap-1 text-xs"):
                    ui.badge(f"T{turn_num}").props("color=grey outline")
                    ui.badge(action_type).props(f"color={result_color} outline")
                    ui.label(f"{actor}: {desc}").classes("text-gray-600")


def create_hakoniwa_console() -> None:
    """Create the HAKONIWA Console 3-pane layout."""
    with ui.row().classes("w-full gap-4"):
        # Left pane: Control Panel (20%)
        with ui.column().classes("w-1/5 gap-4"):
            create_control_panel()

        # Center pane: Main Stage (50%)
        with ui.column().classes("w-3/5"):
            create_main_stage()

        # Right pane: God View (30%)
        with ui.column().classes("w-1/5 gap-4"):
            create_god_view()


def create_app():
    """Create the main application."""
    ui.page_title("HAKONIWA Console")

    with ui.header().classes("bg-indigo-700"):
        ui.label("HAKONIWA Console").classes("text-xl text-white font-bold")

        # Connection indicators in header
        with ui.row().classes("ml-4 gap-2"):
            core_color = "green" if state.core_connected else "red"
            director_color = "green" if state.director_connected else "red"
            gm_color = "green" if state.gm_connected else "grey"

            ui.badge("Core").props(f"color={core_color} outline")
            ui.badge("Director").props(f"color={director_color} outline")
            ui.badge("GM").props(f"color={gm_color} outline")

        ui.space()
        ui.label("Phase 4: Integration Dashboard").classes("text-sm text-indigo-200")

    # Main content area with tabs for Console vs Legacy
    with ui.tabs().classes("w-full") as tabs:
        console_tab = ui.tab("Console", icon="dashboard")
        legacy_tab = ui.tab("Legacy", icon="history")

    with ui.tab_panels(tabs, value=console_tab).classes("w-full"):
        # HAKONIWA Console (new 3-pane layout)
        with ui.tab_panel(console_tab).classes("p-4"):
            create_hakoniwa_console()

        # Legacy view (original layout)
        with ui.tab_panel(legacy_tab).classes("p-4"):
            with ui.column().classes("w-full gap-4"):
                with ui.row().classes("w-full gap-4"):
                    with ui.column().classes("w-1/4 gap-4"):
                        create_scenario_panel()
                        create_execution_panel()
                        create_visual_board_panel()

                    with ui.column().classes("w-1/2"):
                        create_results_panel()

                    with ui.column().classes("w-1/4 gap-4"):
                        create_demo_pack_panel()

    # Footer with status log
    with ui.footer().classes("bg-gray-100"):
        ui.label("Ready").classes("text-xs text-gray-500").bind_text_from(
            state, "log_output", lambda x: x.split("\n")[-1] if x else "Ready"
        )


# Create app
create_app()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(port=8080, title="duo-talk Evaluation")
