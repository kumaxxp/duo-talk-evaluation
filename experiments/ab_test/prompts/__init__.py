"""プロンプトテンプレート

4種類のプロンプト構造を定義:
- layered: duo-talk方式 (XML階層)
- simple: duo-talk-simple方式
- sillytavern: SillyTavern形式
- json: v3.3 JSON Schema形式
"""

from .layered import LayeredPromptBuilder
from .simple import SimplePromptBuilder
from .sillytavern import SillyTavernPromptBuilder
from .json_prompt import JSONPromptBuilder
from .base import PromptBuilder, CharacterConfig

__all__ = [
    "PromptBuilder",
    "CharacterConfig",
    "LayeredPromptBuilder",
    "SimplePromptBuilder",
    "SillyTavernPromptBuilder",
    "JSONPromptBuilder",
]
