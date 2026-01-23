"""Evaluation package for duo-talk dialogue quality assessment"""

from .metrics import DialogueQualityMetrics
from .local_evaluator import LocalLLMEvaluator
from .ollama_evaluator import OllamaEvaluator

__all__ = [
    "DialogueQualityMetrics",
    "LocalLLMEvaluator",
    "OllamaEvaluator",
]
