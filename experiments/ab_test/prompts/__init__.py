"""プロンプトテンプレート

7種類のプロンプト構造を定義:
- layered: duo-talk方式 (XML階層)
- simple: duo-talk-simple方式
- sillytavern: SillyTavern形式
- json: v3.3 JSON Schema形式
- json_v36: v3.6 System-Assisted形式
- json_v37: v3.7 Direct Dialogue Enforcement形式
- json_v38: v3.8 Narrative Restoration形式
"""

from .layered import LayeredPromptBuilder
from .simple import SimplePromptBuilder
from .sillytavern import SillyTavernPromptBuilder
from .json_prompt import JSONPromptBuilder
from .json_v36 import JSONV36PromptBuilder
from .json_v37 import JSONV37PromptBuilder
from .json_v38 import JSONV38PromptBuilder
from .base import PromptBuilder, CharacterConfig

__all__ = [
    "PromptBuilder",
    "CharacterConfig",
    "LayeredPromptBuilder",
    "SimplePromptBuilder",
    "SillyTavernPromptBuilder",
    "JSONPromptBuilder",
    "JSONV36PromptBuilder",
    "JSONV37PromptBuilder",
    "JSONV38PromptBuilder",
]
