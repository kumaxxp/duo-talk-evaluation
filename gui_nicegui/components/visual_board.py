"""Visual Board component — 3x3 grid displaying hakoniwa objects by Zone.

Grid layout:
  0=NW(wall)  1=N       2=NE(wall)
  3=W         4=C       5=E
  6=SW(wall)  7=S       8=SE(wall)

Objects are placed into actionable cells (1,3,4,5,7) via zone_resolver.
Wall/corner cells (0,2,6,8) are display-only.
"""

from collections import defaultdict
from typing import Callable, Mapping, Sequence

from nicegui import ui

from hakoniwa.ui.zone_resolver import resolve_zone, icon_for, label_for

# Cell index constants
WALL_CELLS = frozenset({0, 2, 6, 8})
ACTIONABLE_CELLS = frozenset({1, 3, 4, 5, 7})
CELL_LABELS = {
    0: "NW", 1: "N", 2: "NE",
    3: "W", 4: "C", 5: "E",
    6: "SW", 7: "S", 8: "SE",
}


def _build_zone_map(
    objects: Sequence[Mapping[str, object]],
) -> dict[int, list[Mapping[str, object]]]:
    """Group objects by their resolved grid cell index."""
    zone_map: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for obj in objects:
        idx = resolve_zone(obj)
        zone_map[idx].append(obj)
    return dict(zone_map)


def _tooltip_text(obj: Mapping[str, object]) -> str:
    """Build tooltip: 'Name (State)' or just 'Name'."""
    name = label_for(obj)
    state = obj.get("state")
    if isinstance(state, str) and state:
        return f"{name} ({state})"
    if isinstance(state, list) and state:
        return f"{name} ({', '.join(str(s) for s in state)})"
    return name


def create_visual_board(
    objects: Sequence[Mapping[str, object]],
    on_select: Callable[[Mapping[str, object]], None] | None = None,
    selected_id: str | None = None,
) -> None:
    """Render the 3x3 Visual Board.

    Args:
        objects: List of hakoniwa objects (dicts with name/type/state/ui_zone).
        on_select: Callback when an object chip is clicked.
        selected_id: Currently selected object's id/name for highlighting.
    """
    zone_map = _build_zone_map(objects)

    with ui.element("div").classes(
        "grid grid-cols-3 gap-1 w-80"
    ).style("aspect-ratio: 1 / 1;"):
        for cell_idx in range(9):
            is_wall = cell_idx in WALL_CELLS
            cell_objects = zone_map.get(cell_idx, [])

            # Cell container
            bg = "bg-gray-200" if is_wall else "bg-gray-50"
            border = "border border-gray-300 rounded"
            cell_classes = f"{bg} {border} flex flex-wrap items-start justify-center content-start p-1 overflow-auto"

            with ui.element("div").classes(cell_classes).style(
                "min-height: 60px;"
            ):
                if is_wall:
                    # Wall cells: show label only
                    ui.label(CELL_LABELS[cell_idx]).classes(
                        "text-xs text-gray-400 select-none"
                    )
                elif cell_objects:
                    for obj in cell_objects:
                        _render_object_chip(obj, on_select, selected_id)
                else:
                    # Empty actionable cell
                    ui.label("·").classes(
                        "text-lg text-gray-300 select-none"
                    )


def _render_object_chip(
    obj: Mapping[str, object],
    on_select: Callable[[Mapping[str, object]], None] | None,
    selected_id: str | None,
) -> None:
    """Render a single clickable object chip inside a cell."""
    icon = icon_for(obj)
    name = label_for(obj)
    tooltip = _tooltip_text(obj)

    obj_id = obj.get("id") or obj.get("name", "")
    is_selected = selected_id is not None and str(obj_id) == str(selected_id)

    highlight = "ring-2 ring-blue-500" if is_selected else ""

    btn = ui.button(
        f"{icon}",
        on_click=lambda o=obj: on_select(o) if on_select else None,
    ).props("flat dense padding='2px 6px'").classes(
        f"text-base {highlight}"
    ).tooltip(tooltip)
