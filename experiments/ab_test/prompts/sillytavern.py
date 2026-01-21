"""SillyTavern形式プロンプト (duo-talk-silly方式)

SillyTavern Character Card V2形式を再現。
最小限の構造でシンプルなキャラクター定義。
"""

from .base import PromptBuilder, CharacterConfig


class SillyTavernPromptBuilder(PromptBuilder):
    """SillyTavern Character Card V2準拠のプロンプトビルダー"""

    def build_system_prompt(self, speaker: str) -> str:
        """システムプロンプトを構築"""
        char = self.get_character_config(speaker)

        # 敬語/カジュアルの説明
        register_note = "敬語ベースで話す" if char.speech_register == "polite" else "敬語は使わない"

        return f"""あなたは「{char.name}」として応答してください。

# キャラクター設定
- 名前: {char.name}
- 役割: {char.role}
- 相手の呼び方: {char.callname_other}
- 性格: {', '.join(char.personality)}
- 口調の特徴:
  - 「{char.speech_patterns[0]}」「{char.speech_patterns[1]}」「{char.speech_patterns[2]}」で終わる
  - {register_note}
  - 短めの文で話す（{self.max_sentences}文以内）
- 考え方: {char.core_belief}

# よく使うフレーズ
{self._format_phrases(char)}

# 話し方の例
{self._format_examples(char)}"""

    def build_dialogue_prompt(
        self,
        speaker: str,
        topic: str,
        history: list[dict],
    ) -> str:
        """対話プロンプトを構築"""
        char = self.get_character_config(speaker)

        prompt_parts = [
            self.build_system_prompt(speaker),
            f"\n\n# お題\n「{topic}」について姉妹で会話してください。",
            "\n\n# これまでの会話"
        ]

        if not history:
            prompt_parts.append("\n（まだ会話は始まっていません。最初の発言をしてください）")
        else:
            for entry in history:
                prompt_parts.append(f"\n{entry['speaker']}: {entry['content']}")

        prompt_parts.append(f"\n\n{char.name}:")

        return "".join(prompt_parts)

    def _format_examples(self, char: CharacterConfig) -> str:
        """Few-shot例をフォーマット"""
        examples = char.few_shot_examples[:self.few_shot_count]
        return "\n".join(f"「{ex}」" for ex in examples)

    def _format_phrases(self, char: CharacterConfig) -> str:
        """典型的なフレーズをフォーマット"""
        phrases = char.typical_phrases[:3] if char.typical_phrases else char.few_shot_examples[:3]
        return "\n".join(f"- {p}" for p in phrases)
