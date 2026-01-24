"""Evaluation metrics module (Phase 2.3+)

Provides metrics calculation for:
- Thought quality evaluation
- Character consistency analysis
- Emotion distribution analysis
"""

from .thought_metrics import (
    ThoughtMetrics,
    ThoughtMetricsCalculator,
    CharacterProfile,
)

__all__ = [
    "ThoughtMetrics",
    "ThoughtMetricsCalculator",
    "CharacterProfile",
]
