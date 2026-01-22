"""v3.6 System-Assisted Output Enforcement アダプタ

v3.6の核心コンセプト: 「プロンプトで思考を誘発し、システム実装で発話を強制する」

1. **Prefill Pattern**: Assistant messageに "Thought:" を事前入力
2. **Stop Sequence**: "Output:" で一旦止める
3. **Continue Generation**: Output:がなければ追記して継続生成

参照: docs/キャラクター設定プロンプト v3.6 改良案gemini.md
"""

import logging
import re
import time
from typing import Optional

import requests

from experiments.ab_test.config import LLMBackend, PromptStructure, VariationConfig
from experiments.ab_test.prompts import (
    JSONPromptBuilder,
    LayeredPromptBuilder,
    PromptBuilder,
    SimplePromptBuilder,
    SillyTavernPromptBuilder,
)

logger = logging.getLogger(__name__)


class V36ConfigurableAdapter:
    """v3.6 System-Assisted Output Enforcement アダプタ

    ConfigurableAdapterの拡張版。v3.6のPrefill + Continue Generationフローを実装。
    """

    def __init__(self, variation: VariationConfig):
        """
        Args:
            variation: バリエーション設定
        """
        self.variation = variation
        self.prompt_builder = self._create_prompt_builder()

    def _create_prompt_builder(self) -> PromptBuilder:
        """プロンプトビルダーを作成"""
        # v3.6フロー有効時はJSONV36PromptBuilderを使用
        if self.variation.use_v36_flow and self.variation.prompt_structure == PromptStructure.JSON:
            from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder
            return JSONV36PromptBuilder(
                max_sentences=self.variation.max_sentences,
                few_shot_count=self.variation.few_shot_count,
            )

        builders = {
            PromptStructure.LAYERED: LayeredPromptBuilder,
            PromptStructure.SIMPLE: SimplePromptBuilder,
            PromptStructure.SILLYTAVERN: SillyTavernPromptBuilder,
            PromptStructure.JSON: JSONPromptBuilder,
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
            response = requests.get(
                f"{self.variation.ollama_url}/models",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
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

    def _should_use_v36_flow(self) -> bool:
        """v3.6フローを使用すべきかどうか"""
        return self.variation.use_v36_flow

    # ===== v3.6 Core Methods =====

    def _build_messages_with_prefill(
        self,
        system_prompt: str,
        history: list[dict],
    ) -> list[dict]:
        """Prefill付きのメッセージリストを構築

        v3.6の核心: Assistant messageに "Thought:" を事前入力し、
        モデルを強制的に思考モードから開始させる。
        """
        messages = [{"role": "system", "content": system_prompt}]

        # 履歴を追加
        for entry in history:
            role = "user" if entry.get("speaker") == "user" else "assistant"
            messages.append({"role": role, "content": entry["content"]})

        # Prefill: "Thought:" をassistantメッセージとして追加
        messages.append({"role": "assistant", "content": "Thought:"})

        return messages

    def _get_v36_stop_sequences(self) -> list[str]:
        """v3.6用のstop sequenceを取得

        "Output:" で一旦止めることで、Thoughtパートの終了を検出する。
        """
        return [
            "Output:",  # v3.6の核心: Output:で止める
            "\n\n",
            "やな:",
            "あゆ:",
            "<|im_end|>",
            "<|im_start|>",
            "<|eot_id|>",
            "<end_of_turn>",
            "<start_of_turn>",
        ]

    def _needs_continue_generation(self, content: str) -> bool:
        """継続生成が必要かどうかを判定

        "Output:" が含まれていない場合は継続生成が必要。
        """
        return "Output:" not in content

    def _prepare_continue_content(self, thought_content: str) -> str:
        """継続生成用のコンテンツを準備

        Thoughtの内容に "\\nOutput:" を追記する。
        """
        return thought_content.rstrip() + "\nOutput:"

    def _parse_v36_response(self, response: str) -> tuple[str, str]:
        """v3.6レスポンスをThoughtとOutputに分離

        Returns:
            (thought, output) のタプル
        """
        if "Output:" in response:
            parts = response.split("Output:", 1)
            thought = parts[0].replace("Thought:", "").strip()
            output = parts[1].strip() if len(parts) > 1 else ""
            return thought, output
        else:
            # Output:がない場合はthoughtのみ
            thought = response.replace("Thought:", "").strip()
            return thought, ""

    def _call_ollama_api(
        self,
        messages: list[dict],
        stop: Optional[list[str]] = None,
        max_tokens: int = 300,
    ) -> str:
        """Ollama APIを呼び出し

        Args:
            messages: メッセージリスト
            stop: stop sequence
            max_tokens: 最大トークン数

        Returns:
            生成されたテキスト
        """
        try:
            payload = {
                "model": self.variation.ollama_model,
                "messages": messages,
                "temperature": self.variation.temperature,
                "max_tokens": max_tokens,
            }
            if stop:
                payload["stop"] = stop

            response = requests.post(
                f"{self.variation.ollama_url}/chat/completions",
                json=payload,
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

    def _generate_with_v36_flow(self, prompt: str) -> str:
        """v3.6フローで応答を生成

        1. Prefill: "Thought:" を追加してリクエスト
        2. Stop: "Output:" で止める
        3. Continue: Output:がなければ追記して継続生成

        Args:
            prompt: システムプロンプト（対話プロンプト全体）

        Returns:
            "Thought: ... Output: ..." 形式の完全な応答
        """
        # メッセージを構築（userメッセージとしてpromptを使用）
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "Thought:"},  # Prefill
        ]

        # 1st generation: Thoughtを生成（Output:で止まる）
        stop_sequences = self._get_v36_stop_sequences()
        thought_content = self._call_ollama_api(
            messages=messages,
            stop=stop_sequences,
            max_tokens=200,
        )

        # Prefill分を含めた完全なコンテンツ
        full_content = "Thought:" + thought_content

        # Output:がなければ継続生成
        if self._needs_continue_generation(full_content):
            # "Output:" を追記
            continued_content = self._prepare_continue_content(full_content)

            # 継続生成用のメッセージを構築
            continue_messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": continued_content},  # Thought + Output:
            ]

            # 2nd generation: Outputを生成
            output_content = self._call_ollama_api(
                messages=continue_messages,
                stop=["\n\n", "やな:", "あゆ:", "<|im_end|>", "<end_of_turn>"],
                max_tokens=300,
            )

            full_content = continued_content + output_content

        return full_content

    # ===== Public Interface =====

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

                # 応答生成（v3.6フローまたは通常フロー）
                if self._should_use_v36_flow():
                    response = self._generate_with_v36_flow(prompt)
                else:
                    response = self._generate_response(prompt)

                if not response:
                    logger.warning(f"Empty response at turn {turn_num}")
                    response = "..."

                # 応答をクリーンアップ
                response = self._clean_response(response)

                # 履歴に追加
                history.append({"speaker": speaker, "content": response})
                conversation.append({
                    "speaker": speaker,
                    "content": response,
                    "turn_number": turn_num,
                })

            # バックエンドに応じて適切なモデル名を使用
            if self.variation.llm_backend == LLMBackend.OLLAMA:
                model_name = self.variation.ollama_model
            else:
                model_name = self.variation.llm_model

            return {
                "conversation": conversation,
                "success": True,
                "execution_time_seconds": time.time() - start_time,
                "variation": self.variation.name,
                "metadata": {
                    "llm_backend": self.variation.llm_backend.value,
                    "llm_model": model_name,
                    "prompt_structure": self.variation.prompt_structure.value,
                    "rag_enabled": self.variation.rag_enabled,
                    "director_enabled": self.variation.director_enabled,
                    "use_v36_flow": self.variation.use_v36_flow,
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
        """通常の応答生成（v3.6フロー無効時）"""
        if self.variation.llm_backend == LLMBackend.OLLAMA:
            raw = self._generate_ollama(prompt)
        elif self.variation.llm_backend == LLMBackend.KOBOLDCPP:
            raw = self._generate_koboldcpp(prompt)
        else:
            return ""
        return raw

    def _clean_response(self, text: str) -> str:
        """応答からチャットテンプレートトークンを除去"""
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
        """Ollamaで応答を生成（通常フロー）"""
        try:
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
        """KoboldCPPで応答を生成"""
        for attempt in range(retries + 1):
            try:
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

                cleaned = result.replace("-", "").replace("_", "").replace("*", "").strip()
                if result and cleaned:
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
