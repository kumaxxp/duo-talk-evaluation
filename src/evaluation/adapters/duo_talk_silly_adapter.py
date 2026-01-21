"""duo-talk-silly 接続アダプタ（KoboldCPP直接呼び出し）"""

import logging
import time
from typing import List, Optional

import requests

from .base import SystemAdapter
from .types import ConnectionMethod, DialogueResult, DialogueTurn

logger = logging.getLogger(__name__)

# キャラクター設定（duo-talk/duo-talk-simpleに準拠）
# 参照: duo-talk-simple/personas/yana.yaml, duo-talk-simple/personas/ayu.yaml
YANA_PERSONA = """あなたは「やな」として応答してください。

# キャラクター設定
- 名前: やな
- 役割: 姉（活発で直感型）
- 相手の呼び方: あゆ
- 性格: 直感的、楽観的、せっかち、好奇心旺盛
- 口調の特徴:
  - 「〜じゃん」「〜でしょ」「〜だよね」で終わる
  - 敬語は使わない
  - 短めの文で話す（3文以内）
- 考え方: 動かしてみなきゃわからない

# よく使うフレーズ
- 平気平気！
- まあまあ、やってみようよ
- あゆがなんとかしてくれるでしょ

# 話し方の例
「あ、なんか面白そう！」
「ねえねえ、あゆ、これ見て」
「まあまあ、やってみようよ」
"""

AYU_PERSONA = """あなたは「あゆ」として応答してください。

# キャラクター設定
- 名前: あゆ
- 役割: 妹（慎重で分析型）
- 相手の呼び方: 姉様（重要！「お姉ちゃん」ではない）
- 性格: 論理的、冷静、慎重、少し皮肉屋
- 口調の特徴:
  - 「〜ですね」「〜かもしれません」「〜だと思います」で終わる
  - 敬語ベースで話す
  - 短めの文で話す（3文以内）
- 考え方: 姉様の無計画さには物申すけど、最終的には一緒に成功させたい

# よく使うフレーズ
- ちょっと待ってください
- 根拠があるのでしょうか？
- ...まあ、姉様がそう言うなら

# 話し方の例
「姉様、それは...本当に大丈夫ですか？」
「ちょっと待ってください」
「悔しいですけど、それ、いいかもしれません」
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
        temperature: float = 0.7,
        retries: int = 2
    ) -> str:
        """KoboldCPPで応答を生成

        Args:
            prompt: プロンプト
            max_tokens: 最大トークン数
            temperature: 温度パラメータ
            retries: 空応答時のリトライ回数
        """
        for attempt in range(retries + 1):
            try:
                # 空応答対策: リトライ時は温度を上げる
                temp = temperature + (attempt * 0.1)

                response = requests.post(
                    f"{self.kobold_url}/api/v1/generate",
                    json={
                        "prompt": prompt,
                        "max_length": max_tokens,
                        "temperature": min(temp, 1.0),
                        "top_p": 0.9,
                        "top_k": 40,
                        "min_p": 0.05,
                        "rep_pen": 1.05,
                        "stop_sequence": [
                            "\n\n", "やな:", "あゆ:", "# ", "##",
                            "<|im_end|>", "<|im_start|>", "<|eot_id|>",
                            "<end_of_turn>", "<start_of_turn>",
                        ]
                    },
                    timeout=120
                )
                response.raise_for_status()
                raw = response.json()["results"][0]["text"].strip()
                result = self._clean_response(raw)

                # 空応答チェック（---、-、空文字など）
                if result and not result.replace("-", "").strip() == "":
                    return result
                logger.warning(f"Empty response attempt {attempt + 1}, retrying...")

            except requests.RequestException as e:
                logger.error(f"KoboldCPP request failed: {e}")
                return ""
            except (KeyError, IndexError) as e:
                logger.error(f"KoboldCPP response parse error: {e}")
                return ""

        return ""

    def _clean_response(self, text: str) -> str:
        """応答からチャットテンプレートトークンを除去"""
        import re
        tokens_to_remove = [
            r"<\|im_end\|>",
            r"<\|im_start\|>user",
            r"<\|im_start\|>assistant",
            r"<\|im_start\|>system",
            r"<\|eot_id\|>",
            r"<end_of_turn>",
            r"<start_of_turn>model",
            r"<start_of_turn>user",
        ]
        for token in tokens_to_remove:
            text = re.sub(token, "", text)
        return text.strip()

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
