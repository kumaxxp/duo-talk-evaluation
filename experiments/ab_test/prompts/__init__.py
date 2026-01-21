"""プロンプトテンプレート

3種類のプロンプト構造を定義:
- layered: duo-talk方式 (XML階層)
- simple: duo-talk-simple方式
- sillytavern: SillyTavern形式
"""

from .layered import LayeredPromptBuilder
from .simple import SimplePromptBuilder
from .sillytavern import SillyTavernPromptBuilder
from .base import PromptBuilder, CharacterConfig

__all__ = [
    "PromptBuilder",
    "CharacterConfig",
    "LayeredPromptBuilder",
    "SimplePromptBuilder",
    "SillyTavernPromptBuilder",
]
