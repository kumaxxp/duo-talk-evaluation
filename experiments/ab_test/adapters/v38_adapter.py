"""v3.8 Narrative Restoration アダプタ

v3.8の核心コンセプト: 「動作描写を許可しつつ、名前は後処理で削除する」

v3.7からの変更点:
1. **Prompt**: `(Action) 「Dialogue」` 形式を許可、Few-shotに動作描写を追加
2. **Implementation**: Prefillを `Output:` に戻す（動作を書く余地を与える）
3. **Post-Processing**: 名前クリーニングで「澄ヶ瀬やな:」等を削除

参照: docs/キャラクター設定プロンプト v3.8 改良案gemini.md
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


class V38ConfigurableAdapter:
    """v3.8 Narrative Restoration アダプタ

    動作描写（*sighs* など）を許可しつつ、名前は後処理で削除する。
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
        # v3.8フロー有効時はJSONV38PromptBuilderを使用
        if self.variation.use_v38_flow and self.variation.prompt_structure == PromptStructure.JSON:
            from experiments.ab_test.prompts.json_v38 import JSONV38PromptBuilder
            return JSONV38PromptBuilder(
                max_sentences=self.variation.max_sentences,
                few_shot_count=self.variation.few_shot_count,
            )

        # v3.7フロー有効時
        if self.variation.use_v37_flow and self.variation.prompt_structure == PromptStructure.JSON:
            from experiments.ab_test.prompts.json_v37 import JSONV37PromptBuilder
            return JSONV37PromptBuilder(
                max_sentences=self.variation.max_sentences,
                few_shot_count=self.variation.few_shot_count,
            )

        # v3.6フロー有効時
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

    def _should_use_v38_flow(self) -> bool:
        """v3.8フローを使用すべきかどうか"""
        return self.variation.use_v38_flow

    # ===== v3.8 Core Methods =====

    def _get_v38_thought_prefill(self) -> str:
        """Thought開始時のPrefill文字列"""
        return "Thought:"

    def _get_v38_output_prefill(self) -> str:
        """Output強制時のPrefill文字列

        v3.8の特徴: カギカッコなしの `Output:` に戻す
        これにより *sighs* などの動作描写を書く余地を与える
        """
        return "\nOutput:"

    def _get_v38_thought_stop_sequences(self) -> list[str]:
        """Thought生成用のstop sequence"""
        return [
            "Output",
            "Output:",
            "\nOutput",
            "\n\n",
            "やな:",
            "あゆ:",
            "<|im_end|>",
            "<|im_start|>",
            "<|eot_id|>",
            "<end_of_turn>",
            "<start_of_turn>",
        ]

    def _get_v38_dialogue_stop_sequences(self) -> list[str]:
        """Dialogue生成用のstop sequence

        v3.8: より緩やかにして動作描写を許可
        """
        return [
            "\nUser:",
            "\nThought:",
            "\n\n",
            "<|im_end|>",
            "<|im_start|>",
            "<|eot_id|>",
            "<end_of_turn>",
            "<start_of_turn>",
        ]

    def _clean_character_name(self, text: str) -> str:
        """モデルが誤って出力したキャラクター名を削除する

        v3.8の核心: 「Let it write, then delete」方式
        動作描写 (*sighs* など) は保持する
        """
        # パターン: 文頭にある "澄ヶ瀬[あゆ|やな][:：]" などを除去
        # 複数のパターンを試行
        patterns = [
            r"^\s*澄ヶ瀬\s*(あゆ|やな)\s*[:：]\s*",  # 澄ヶ瀬やな: / 澄ヶ瀬あゆ:
            r"^\s*澄ヶ瀬\s*[:：]?\s*",  # 澄ヶ瀬 / 澄ヶ瀬:
            r"^\s*(あゆ|やな)\s*[:：]\s*",  # やな: / あゆ:
            r"^\s*(Ayu|Yana)\s*[:：]\s*",  # Ayu: / Yana:
            r"^\s*Sumigase\s*(Ayu|Yana)?\s*[:：]?\s*",  # Sumigase Yana:
        ]

        result = text
        for pattern in patterns:
            result = re.sub(pattern, "", result, count=1, flags=re.IGNORECASE)

        return result.strip()

    def _call_ollama_api(
        self,
        messages: list[dict],
        stop: Optional[list[str]] = None,
        max_tokens: int = 300,
    ) -> str:
        """Ollama APIを呼び出し"""
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

    def _generate_with_v38_flow(self, prompt: str) -> str:
        """v3.8フローで応答を生成

        1. Prefill: "Thought:" を追加してリクエスト
        2. Stop: "Output", "Output:", "\nOutput" で止める
        3. Prefill: "Output:" のみ（カギカッコなし、動作記述可）
        4. 名前クリーニング: 生成後に名前を削除

        Args:
            prompt: システムプロンプト（対話プロンプト全体）

        Returns:
            クリーニング済みの "Thought: ... Output: ..." 形式の応答
        """
        # メッセージを構築
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": self._get_v38_thought_prefill()},
        ]

        # 1st generation: Thoughtを生成
        stop_sequences = self._get_v38_thought_stop_sequences()
        thought_content = self._call_ollama_api(
            messages=messages,
            stop=stop_sequences,
            max_tokens=200,
        )

        full_content = "Thought:" + thought_content.rstrip()

        # 2nd generation: Output生成（カギカッコなし、動作記述可）
        continued_content = full_content + self._get_v38_output_prefill()

        continue_messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": continued_content},
        ]

        # Dialogue生成
        raw_output = self._call_ollama_api(
            messages=continue_messages,
            stop=self._get_v38_dialogue_stop_sequences(),
            max_tokens=300,
        )

        # Post-Processing: 名前クリーニング
        clean_output = self._clean_character_name(raw_output)

        return continued_content + " " + clean_output

    # ===== Public Interface =====

    def generate_dialogue(
        self,
        initial_prompt: str,
        turns: int,
    ) -> dict:
        """対話を生成"""
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

                # 応答生成（v3.8フロー）
                if self._should_use_v38_flow():
                    response = self._generate_with_v38_flow(prompt)
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
                    "use_v38_flow": self.variation.use_v38_flow,
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
        """通常の応答生成（v3.8フロー無効時）"""
        if self.variation.llm_backend == LLMBackend.OLLAMA:
            return self._generate_ollama(prompt)
        elif self.variation.llm_backend == LLMBackend.KOBOLDCPP:
            return self._generate_koboldcpp(prompt)
        return ""

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
