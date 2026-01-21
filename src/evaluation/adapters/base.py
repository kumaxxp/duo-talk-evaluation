"""LLMバックエンドアダプタの基底クラス"""

from abc import ABC, abstractmethod
from typing import Dict, List

from .types import ConnectionMethod, DialogueResult, EvaluationScenario


class LLMBackendAdapter(ABC):
    """LLMバックエンドアダプタの基底クラス"""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """
        テキスト生成

        Args:
            prompt: 入力プロンプト
            max_tokens: 最大生成トークン数

        Returns:
            生成されたテキスト
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """バックエンドが利用可能かチェック"""
        pass


class DialogueSystemAdapter(ABC):
    """対話システムアダプタの基底クラス（レガシー）"""

    @abstractmethod
    def get_dialogue(self, prompt: str, turns: int) -> List[Dict[str, str]]:
        """
        対話を生成

        Args:
            prompt: 初期プロンプト
            turns: 会話ターン数

        Returns:
            [{"speaker": "やな", "content": "..."}] 形式の会話履歴
        """
        pass


class SystemAdapter(ABC):
    """
    対話システムアダプタ基底クラス（拡張版）

    3つの既存プロジェクトに統一インターフェースで接続するための基底クラス。
    各サブクラスは generate_dialogue() を実装する必要がある。
    """

    def __init__(
        self,
        system_name: str,
        connection_method: ConnectionMethod,
        timeout_seconds: int = 300
    ):
        """
        Args:
            system_name: システム識別名
            connection_method: 接続方式
            timeout_seconds: タイムアウト秒数
        """
        self.system_name = system_name
        self.connection_method = connection_method
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def is_available(self) -> bool:
        """システムが利用可能かチェック"""
        pass

    @abstractmethod
    def generate_dialogue(
        self,
        initial_prompt: str,
        turns: int,
        temperature: float = 0.7
    ) -> DialogueResult:
        """
        会話を生成

        Args:
            initial_prompt: 初期プロンプト（お題）
            turns: 会話ターン数
            temperature: 生成の温度パラメータ

        Returns:
            DialogueResult: 会話生成結果
        """
        pass

    def run_scenario(self, scenario: EvaluationScenario) -> DialogueResult:
        """
        評価シナリオを実行

        Args:
            scenario: 評価シナリオ

        Returns:
            DialogueResult: 会話生成結果
        """
        return self.generate_dialogue(
            initial_prompt=scenario.initial_prompt,
            turns=scenario.turns
        )

    def get_system_info(self) -> dict:
        """システム情報を取得"""
        return {
            "name": self.system_name,
            "connection_method": self.connection_method.value,
            "timeout_seconds": self.timeout_seconds,
            "available": self.is_available()
        }
