"""Zone resolver for Visual Board 3x3 grid.

Maps hakoniwa objects to grid cells using Zone-based placement.
No physics, no XY coordinates — only semantic zones.

Grid layout:
  0=NW  1=N   2=NE
  3=W   4=C   5=E
  6=SW  7=S   8=SE

Actionable cells: 1(N), 3(W), 4(C), 5(E), 7(S)
Wall/corner cells: 0, 2, 6, 8
"""

from typing import Mapping

# Zone name → grid index
ZONE_INDEX: dict[str, int] = {
    "north": 1,
    "west": 3,
    "center": 4,
    "east": 5,
    "south": 7,
}

# Name substrings → zone (checked case-insensitively)
_NAME_RULES: list[tuple[list[str], int]] = [
    (["door", "entrance", "exit"], 7),       # South
    (["shelf", "bookshelf", "bookcase"], 1),  # North
]

# Type → emoji
_TYPE_ICONS: dict[str, str] = {
    "character": "👤",
    "actor": "👤",
    "key": "🗝️",
    "door": "🚪",
    "table": "🪑",
    "furniture": "🪑",
    "item": "📦",
}

# Name substring → emoji (fallback when type is missing)
_NAME_ICONS: list[tuple[str, str]] = [
    ("door", "🚪"),
    ("key", "🗝️"),
    ("shelf", "📚"),
    ("book", "📚"),
    ("table", "🪑"),
    ("chair", "🪑"),
]

_DEFAULT_ICON = "❓"
_DEFAULT_LABEL = "???"


def resolve_zone(obj: Mapping[str, object]) -> int:
    """Resolve an object to a grid cell index (1/3/4/5/7).

    Priority:
      1. obj["ui_zone"] if present
      2. Name-based inference
      3. Center(4) fallback
    """
    # 1. Explicit ui_zone
    ui_zone = obj.get("ui_zone")
    if isinstance(ui_zone, str):
        idx = ZONE_INDEX.get(ui_zone.lower())
        if idx is not None:
            return idx

    # 2. Name inference
    name = obj.get("name")
    if isinstance(name, str):
        name_lower = name.lower()
        for keywords, zone_idx in _NAME_RULES:
            for kw in keywords:
                if kw in name_lower:
                    return zone_idx

    # 3. Default
    return 4


def icon_for(obj: Mapping[str, object]) -> str:
    """Return an emoji icon for the object.

    Checks type first, then falls back to name-based matching.
    """
    obj_type = obj.get("type")
    if isinstance(obj_type, str):
        icon = _TYPE_ICONS.get(obj_type.lower())
        if icon is not None:
            return icon

    name = obj.get("name")
    if isinstance(name, str):
        name_lower = name.lower()
        for kw, icon in _NAME_ICONS:
            if kw in name_lower:
                return icon

    return _DEFAULT_ICON


def label_for(obj: Mapping[str, object]) -> str:
    """Return a short display label for the object."""
    name = obj.get("name")
    if isinstance(name, str) and name:
        return name
    return _DEFAULT_LABEL
