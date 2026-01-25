"""HAKONIWA GUI - Main entry point.

NiceGUI-based minimal GUI for HAKONIWA-G3 system.

Usage:
    python -m gui.main

Features:
    - Phase A: Scenario Editor
    - Phase B: Run Launcher
    - Phase C: Log Viewer
"""

from nicegui import ui

from gui.pages.scenario_editor import create_scenario_editor_page
from gui.pages.run_launcher import create_run_launcher_page
from gui.pages.log_viewer import create_log_viewer_page


def create_header():
    """Create navigation header."""
    with ui.header().classes("bg-primary"):
        ui.label("HAKONIWA GUI").classes("text-h5 text-white")
        ui.space()
        with ui.row():
            ui.link("Scenario Editor", "/").classes("text-white mx-2")
            ui.link("Run Launcher", "/run").classes("text-white mx-2")
            ui.link("Log Viewer", "/logs").classes("text-white mx-2")


@ui.page("/")
def scenario_editor_page():
    """Phase A: Scenario Editor."""
    create_header()
    create_scenario_editor_page()


@ui.page("/run")
def run_launcher_page():
    """Phase B: Run Launcher."""
    create_header()
    create_run_launcher_page()


@ui.page("/logs")
def log_viewer_page():
    """Phase C: Log Viewer."""
    create_header()
    create_log_viewer_page()


def main():
    """Run the GUI."""
    ui.run(
        title="HAKONIWA GUI",
        port=8080,
        reload=True,
        show=False,  # Don't auto-open browser
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
