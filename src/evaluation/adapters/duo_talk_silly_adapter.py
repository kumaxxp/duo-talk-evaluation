"""duo-talk-silly 接続アダプタ（KoboldCPP直接呼び出し）"""

import logging
import time
from typing import List, Optional

import requests

from .base import SystemAdapter
from .types import ConnectionMethod, DialogueResult, DialogueTurn

logger = logging.getLogger(__name__)

# キャラクター設定（SillyTavern Character Card V2準拠）
YANA_PERSONA = """あなたは「やな」として応答してください。

# キャラクター設定
- 名前: やな
- 役割: 姉（Edge AI担当）
- 一人称: 私
- 性格: 直感的、行動派、妹思い、せっかち
- 口調の特徴:
  - 「〜わ」「〜かしら」「〜ね」で終わる
  - 敬語は使わない
  - 短めの文で話す
- 考え方: 考えるより先に動く。失敗を恐れない。

# 話し方の例
「おはよう、あゆ！今日は何するの？」
「へぇ、面白そうね。私も試してみようかしら」
「まあまあ、やってみなきゃわからないわよ」
"""

AYU_PERSONA = """あなたは「あゆ」として応答してください。

# キャラクター設定
- 名前: あゆ
- 役割: 妹（Cloud AI担当）
- 一人称: あたし
- 性格: 分析的、慎重、理論派、心配性
- 口調の特徴:
  - 「〜だよ」「〜じゃん」「〜かな？」で終わる
  - 敬語は使わない
  - 説明が丁寧
- 考え方: データに基づいて判断する。リスクを分析する。

# 話し方の例
「おはよう、お姉ちゃん。今日は何の予定？」
「それってさ、ちゃんと調べた方がいいんじゃない？」
「あたしが調べておくから、待っててね」
"""


class DuoTalkSillyAdapter(SystemAdapter):
    """
    duo-talk-silly接続アダプタ

    接続先: KoboldCPP API (http://localhost:5001)
    モデル: Gemma-2-Llama-Swallow-27b
    特徴: ローカルLLM、Character Card V2準拠

    Note: duo-talk-sillyプロジェクトは未作成のため、
    KoboldCPPを直接呼び出して姉妹対話をシミュレート
    """

    DEFAULT_KOBOLD_URL = "http://localhost:5001"

    def __init__(
        self,
        kobold_url: str = DEFAULT_KOBOLD_URL,
        timeout_seconds: int = 300
    ):
        """
        Args:
            kobold_url: KoboldCPP API URL
            timeout_seconds: API呼び出しタイムアウト
        """
        super().__init__(
            system_name="duo-talk-silly",
            connection_method=ConnectionMethod.HTTP_API,
            timeout_seconds=timeout_seconds
        )
        self.kobold_url = kobold_url.rstrip("/")

    def is_available(self) -> bool:
        """KoboldCPPが起動しているかチェック"""
        try:
            response = requests.get(
                f"{self.kobold_url}/api/v1/model",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _generate_response(
        self,
        prompt: str,
        max_tokens: int = 300,
        temperature: float = 0.7
    ) -> str:
        """KoboldCPPで応答を生成"""
        try:
            response = requests.post(
                f"{self.kobold_url}/api/v1/generate",
                json={
                    "prompt": prompt,
                    "max_length": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "rep_pen": 1.1,
                    "stop_sequence": ["\n\n", "やな:", "あゆ:", "# ", "##"]
                },
                timeout=120
            )
            response.raise_for_status()
            return response.json()["results"][0]["text"].strip()
        except requests.RequestException as e:
            logger.error(f"KoboldCPP request failed: {e}")
            return ""
        except (KeyError, IndexError) as e:
            logger.error(f"KoboldCPP response parse error: {e}")
            return ""

    def generate_dialogue(
        self,
        initial_prompt: str,
        turns: int,
        temperature: float = 0.7
    ) -> DialogueResult:
        """
        姉妹対話を生成

        Args:
            initial_prompt: 初期プロンプト（お題）
            turns: 会話ターン数
            temperature: 生成の温度パラメータ

        Returns:
            DialogueResult: 会話生成結果
        """
        start_time = time.time()
        conversation: List[DialogueTurn] = []

        if not self.is_available():
            return DialogueResult(
                conversation=[],
                success=False,
                system_name=self.system_name,
                error="KoboldCPP not available",
                execution_time_seconds=time.time() - start_time
            )

        try:
            # 会話履歴を構築
            history: List[dict] = []
            speakers = ["やな", "あゆ"]  # 交互に発言

            for turn_num in range(turns):
                speaker = speakers[turn_num % 2]
                persona = YANA_PERSONA if speaker == "やな" else AYU_PERSONA

                # プロンプト構築
                prompt = self._build_prompt(
                    persona=persona,
                    speaker=speaker,
                    topic=initial_prompt,
                    history=history
                )

                # 応答生成
                response = self._generate_response(
                    prompt=prompt,
                    temperature=temperature
                )

                if not response:
                    logger.warning(f"Empty response at turn {turn_num}")
                    response = "..."

                # 履歴に追加
                history.append({"speaker": speaker, "content": response})
                conversation.append(DialogueTurn(
                    speaker=speaker,
                    content=response,
                    turn_number=turn_num
                ))

            return DialogueResult(
                conversation=conversation,
                success=True,
                system_name=self.system_name,
                execution_time_seconds=time.time() - start_time,
                metadata={"model": "gemma2-swallow-27b"}
            )

        except Exception as e:
            logger.exception("Dialogue generation failed")
            return DialogueResult(
                conversation=conversation,
                success=False,
                system_name=self.system_name,
                error=str(e),
                execution_time_seconds=time.time() - start_time
            )

    def _build_prompt(
        self,
        persona: str,
        speaker: str,
        topic: str,
        history: List[dict]
    ) -> str:
        """対話プロンプトを構築"""
        prompt_parts = [
            persona,
            f"\n# お題\n「{topic}」について姉妹で会話してください。",
            "\n# これまでの会話"
        ]

        if not history:
            prompt_parts.append("\n（まだ会話は始まっていません。最初の発言をしてください）")
        else:
            for entry in history:
                prompt_parts.append(f"\n{entry['speaker']}: {entry['content']}")

        prompt_parts.append(f"\n\n{speaker}:")

        return "".join(prompt_parts)
