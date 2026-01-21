"""設定可能なアダプタ

変数（LLM、プロンプト構造、RAG、Director）を切り替え可能なアダプタ。
A/Bテスト用に変数を隔離して実験可能。
"""

import logging
import time
from typing import Optional

import requests

from experiments.ab_test.config import LLMBackend, PromptStructure, VariationConfig
from experiments.ab_test.prompts import (
    LayeredPromptBuilder,
    PromptBuilder,
    SimplePromptBuilder,
    SillyTavernPromptBuilder,
)

logger = logging.getLogger(__name__)


class ConfigurableAdapter:
    """設定可能な対話生成アダプタ"""

    def __init__(self, variation: VariationConfig):
        """
        Args:
            variation: バリエーション設定
        """
        self.variation = variation
        self.prompt_builder = self._create_prompt_builder()

    def _create_prompt_builder(self) -> PromptBuilder:
        """プロンプトビルダーを作成"""
        builders = {
            PromptStructure.LAYERED: LayeredPromptBuilder,
            PromptStructure.SIMPLE: SimplePromptBuilder,
            PromptStructure.SILLYTAVERN: SillyTavernPromptBuilder,
        }
        builder_class = builders.get(self.variation.prompt_structure, SimplePromptBuilder)
        return builder_class(
            max_sentences=self.variation.max_sentences,
            few_shot_count=self.variation.few_shot_count,
        )

    def is_available(self) -> bool:
        """バックエンドが利用可能かチェック"""
        if self.variation.llm_backend == LLMBackend.OLLAMA:
            return self._check_ollama()
        elif self.variation.llm_backend == LLMBackend.KOBOLDCPP:
            return self._check_koboldcpp()
        return False

    def _check_ollama(self) -> bool:
        """Ollamaの可用性チェック"""
        try:
            # OpenAI互換APIのモデルエンドポイントを確認
            response = requests.get(
                f"{self.variation.ollama_url}/models",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            # 直接Ollama APIを試行
            try:
                response = requests.get(
                    "http://localhost:11434/api/tags",
                    timeout=5
                )
                return response.status_code == 200
            except requests.RequestException:
                return False

    def _check_koboldcpp(self) -> bool:
        """KoboldCPPの可用性チェック"""
        try:
            response = requests.get(
                f"{self.variation.kobold_url}/api/v1/model",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def generate_dialogue(
        self,
        initial_prompt: str,
        turns: int,
    ) -> dict:
        """対話を生成

        Args:
            initial_prompt: 初期プロンプト（お題）
            turns: 会話ターン数

        Returns:
            対話結果
        """
        start_time = time.time()
        conversation = []
        history = []
        speakers = ["やな", "あゆ"]

        if not self.is_available():
            return {
                "conversation": [],
                "success": False,
                "error": f"{self.variation.llm_backend.value} not available",
                "execution_time_seconds": time.time() - start_time,
                "variation": self.variation.name,
            }

        try:
            for turn_num in range(turns):
                speaker = speakers[turn_num % 2]

                # プロンプト構築
                prompt = self.prompt_builder.build_dialogue_prompt(
                    speaker=speaker,
                    topic=initial_prompt,
                    history=history,
                )

                # 応答生成
                response = self._generate_response(prompt)

                if not response:
                    logger.warning(f"Empty response at turn {turn_num}")
                    response = "..."

                # 履歴に追加
                history.append({"speaker": speaker, "content": response})
                conversation.append({
                    "speaker": speaker,
                    "content": response,
                    "turn_number": turn_num,
                })

            return {
                "conversation": conversation,
                "success": True,
                "execution_time_seconds": time.time() - start_time,
                "variation": self.variation.name,
                "metadata": {
                    "llm_backend": self.variation.llm_backend.value,
                    "llm_model": self.variation.llm_model,
                    "prompt_structure": self.variation.prompt_structure.value,
                    "rag_enabled": self.variation.rag_enabled,
                    "director_enabled": self.variation.director_enabled,
                },
            }

        except Exception as e:
            logger.exception("Dialogue generation failed")
            return {
                "conversation": conversation,
                "success": False,
                "error": str(e),
                "execution_time_seconds": time.time() - start_time,
                "variation": self.variation.name,
            }

    def _generate_response(self, prompt: str) -> str:
        """LLMで応答を生成"""
        if self.variation.llm_backend == LLMBackend.OLLAMA:
            raw = self._generate_ollama(prompt)
        elif self.variation.llm_backend == LLMBackend.KOBOLDCPP:
            raw = self._generate_koboldcpp(prompt)
        else:
            return ""
        return self._clean_response(raw)

    def _clean_response(self, text: str) -> str:
        """応答からチャットテンプレートトークンを除去"""
        import re
        # チャットテンプレートトークンを除去
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

    def _generate_ollama(self, prompt: str) -> str:
        """Ollamaで応答を生成"""
        try:
            # OpenAI互換APIを使用
            response = requests.post(
                f"{self.variation.ollama_url}/chat/completions",
                json={
                    "model": self.variation.ollama_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": self.variation.temperature,
                    "max_tokens": 300,
                    "stop": [
                        "\n\n", "やな:", "あゆ:", "# ", "##",
                        "<|im_end|>", "<|im_start|>", "<|eot_id|>",
                        "<end_of_turn>", "<start_of_turn>",
                    ],
                },
                timeout=120
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            return ""
        except (KeyError, IndexError) as e:
            logger.error(f"Ollama response parse error: {e}")
            return ""

    def _generate_koboldcpp(self, prompt: str, retries: int = 2) -> str:
        """KoboldCPPで応答を生成

        Args:
            prompt: プロンプト
            retries: 空応答時のリトライ回数
        """
        for attempt in range(retries + 1):
            try:
                # 空応答対策: リトライ時は温度を上げる
                temp = self.variation.temperature + (attempt * 0.1)

                response = requests.post(
                    f"{self.variation.kobold_url}/api/v1/generate",
                    json={
                        "prompt": prompt,
                        "max_length": 300,
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
                result = response.json()["results"][0]["text"].strip()

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

    def to_standard_format(self, result: dict) -> list[dict]:
        """標準形式に変換（評価器用）"""
        return [
            {"speaker": turn["speaker"], "content": turn["content"]}
            for turn in result.get("conversation", [])
        ]
