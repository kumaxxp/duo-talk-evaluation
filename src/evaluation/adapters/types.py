"""SystemAdapter共通型定義"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ConnectionMethod(Enum):
    """接続方式"""
    CLI = "cli"
    HTTP_API = "http_api"
    LIBRARY = "library"


@dataclass
class DialogueTurn:
    """会話ターン"""
    speaker: str
    content: str
    turn_number: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """評価用標準フォーマットに変換"""
        return {"speaker": self.speaker, "content": self.content}


@dataclass
class DialogueResult:
    """会話生成結果"""
    conversation: List[DialogueTurn]
    success: bool
    system_name: str
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_standard_format(self) -> List[dict]:
        """評価用標準フォーマットに変換"""
        return [turn.to_dict() for turn in self.conversation]


@dataclass
class EvaluationScenario:
    """評価シナリオ"""
    name: str
    initial_prompt: str
    turns: int
    evaluation_focus: List[str] = field(default_factory=list)
