"""アダプタモジュール"""

from .base import LLMBackendAdapter, DialogueSystemAdapter, SystemAdapter
from .types import (
    ConnectionMethod,
    DialogueTurn,
    DialogueResult,
    EvaluationScenario,
)
from .ollama import OllamaAdapter
from .kobold import KoboldCPPAdapter
from .duo_talk_adapter import DuoTalkAdapter
from .duo_talk_simple_adapter import DuoTalkSimpleAdapter
from .duo_talk_silly_adapter import DuoTalkSillyAdapter

__all__ = [
    # Base classes
    "LLMBackendAdapter",
    "DialogueSystemAdapter",
    "SystemAdapter",
    # Types
    "ConnectionMethod",
    "DialogueTurn",
    "DialogueResult",
    "EvaluationScenario",
    # LLM Adapters
    "OllamaAdapter",
    "KoboldCPPAdapter",
    # System Adapters
    "DuoTalkAdapter",
    "DuoTalkSimpleAdapter",
    "DuoTalkSillyAdapter",
]
