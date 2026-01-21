"""duo-talk (メインプロジェクト) 接続アダプタ"""

import logging
import time
from typing import Optional

import requests

from .base import SystemAdapter
from .types import ConnectionMethod, DialogueResult, DialogueTurn

logger = logging.getLogger(__name__)


class DuoTalkAdapter(SystemAdapter):
    """
    duo-talk接続アダプタ

    接続先: /home/owner/work/duo-talk/
    API: Flask /api/unified/run/start-sync
    特徴: Director、ChromaDB RAG、UnifiedPipeline
    """

    DEFAULT_BASE_URL = "http://localhost:5000"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: int = 300
    ):
        """
        Args:
            base_url: duo-talk Flask server URL
            timeout_seconds: API呼び出しタイムアウト
        """
        super().__init__(
            system_name="duo-talk",
            connection_method=ConnectionMethod.HTTP_API,
            timeout_seconds=timeout_seconds
        )
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """Flaskサーバーが起動しているかチェック"""
        try:
            response = requests.get(
                f"{self.base_url}/api/unified/health",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def generate_dialogue(
        self,
        initial_prompt: str,
        turns: int,
        temperature: float = 0.7
    ) -> DialogueResult:
        """
        API経由で会話を生成

        Args:
            initial_prompt: 初期プロンプト（お題）
            turns: 会話ターン数
            temperature: 未使用（APIに渡せない）

        Returns:
            DialogueResult: 会話生成結果
        """
        start_time = time.time()

        try:
            response = requests.post(
                f"{self.base_url}/api/unified/run/start-sync",
                json={
                    "text": initial_prompt,
                    "maxTurns": turns
                },
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            data = response.json()

            # 応答をDialogueTurnに変換
            conversation = []
            for i, turn in enumerate(data.get("dialogue", [])):
                # speaker_nameがない場合はspeaker（A/B）から推定
                speaker_name = turn.get("speaker_name")
                if not speaker_name:
                    speaker_code = turn.get("speaker", "")
                    speaker_name = "やな" if speaker_code == "A" else "あゆ"

                conversation.append(DialogueTurn(
                    speaker=speaker_name,
                    content=turn.get("text", ""),
                    turn_number=turn.get("turn_number", i),
                    metadata={
                        "evaluation_status": turn.get("evaluation_status"),
                        "rag_hints": turn.get("rag_hints", [])
                    }
                ))

            success = data.get("status") == "success"
            error_msg = data.get("error") if not success else None

            return DialogueResult(
                conversation=conversation,
                success=success,
                system_name=self.system_name,
                error=error_msg,
                execution_time_seconds=time.time() - start_time,
                metadata={"run_id": data.get("run_id")}
            )

        except requests.Timeout:
            return DialogueResult(
                conversation=[],
                success=False,
                system_name=self.system_name,
                error=f"Timeout after {self.timeout_seconds}s",
                execution_time_seconds=time.time() - start_time
            )
        except requests.RequestException as e:
            return DialogueResult(
                conversation=[],
                success=False,
                system_name=self.system_name,
                error=f"Request failed: {e}",
                execution_time_seconds=time.time() - start_time
            )
        except (KeyError, ValueError) as e:
            return DialogueResult(
                conversation=[],
                success=False,
                system_name=self.system_name,
                error=f"Response parse error: {e}",
                execution_time_seconds=time.time() - start_time
            )
