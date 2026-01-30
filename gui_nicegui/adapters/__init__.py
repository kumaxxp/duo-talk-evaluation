"""Adapters for connecting GUI to backend services."""

from gui_nicegui.adapters.core_adapter import generate_thought, generate_utterance
from gui_nicegui.adapters.director_adapter import check as director_check

__all__ = ["generate_thought", "generate_utterance", "director_check"]
