"""レイヤリング構造プロンプト (duo-talk方式)

duo-talkのXML階層構造を再現。
- Absolute Command: 絶対守るべきルール
- Deep Consciousness: 価値観・信念
- Surface Consciousness: 表面的な設定・口調
"""

from .base import PromptBuilder, CharacterConfig


class LayeredPromptBuilder(PromptBuilder):
    """XML階層構造のプロンプトビルダー"""

    def build_system_prompt(self, speaker: str) -> str:
        """システムプロンプトを構築"""
        char = self.get_character_config(speaker)
        other_char = self.get_character_config("あゆ" if speaker == "やな" else "やな")

        # 禁止ワードの整形（全てのワードを含める）
        forbidden_section = ""
        if char.forbidden_words:
            forbidden_section = f"""
禁止事項:
{chr(10).join(f'- 「{w}」を使わない' for w in char.forbidden_words)}"""

        return f"""<System Prompt is="Sister AI Duo">
<Absolute Command>
あなたは「{char.name}」として応答してください。
- 口調は「{', '.join(char.speech_patterns)}」で終わること
- {self.max_sentences}文以内で簡潔に返答すること
- 相手を呼ぶ場合は「{char.callname_other}」と呼ぶこと
- {'敬語ベースで話す' if char.speech_register == 'polite' else 'カジュアルに話す'}
{forbidden_section}
</Absolute Command>

<Deep Consciousness>
私は{char.name}。{char.role}。
信念: {char.core_belief}

私の性格: {', '.join(char.personality)}

{char.callname_other}との関係:
- 姉妹として育った仲
- 意見が違っても最終的には認め合う
- 互いの強みを尊重している
</Deep Consciousness>

<Surface Consciousness>
キャラクター: {char.name}
口調: {', '.join(char.speech_patterns)}

よく使うフレーズ:
{self._format_phrases(char)}

話し方の例:
{self._format_examples(char)}
</Surface Consciousness>
</System Prompt>"""

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
