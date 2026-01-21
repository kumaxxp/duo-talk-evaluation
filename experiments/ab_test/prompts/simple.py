"""シンプル構造プロンプト (duo-talk-simple方式)

duo-talk-simpleのフラット構造を再現。
- 会話構造ルール（STRICT_CONVERSATION_RULES）
- キャラクター固有制約
- 状態ベースの応答制御
"""

from .base import PromptBuilder, CharacterConfig


# 会話構造ルール（duo-talk-simpleから抽出）
STRICT_CONVERSATION_RULES = """
1. ターン終了時の質問を避けろ（「〜？」で終わらない）
2. 無駄な相槌を削れ（「うん」「そうだね」で始めない）
3. 短く切れ（1-3文で完結）
4. 同じ話題を繰り返すな
5. 相手の発言を要約して返すな
"""

# やな専用制約
YANA_CONSTRAINTS = """
★ 直感を信じろ（理屈より行動）
★ あゆを励ませ（心配しすぎな妹を元気づける）
★ 発見や気づきを短く表現する
★ あゆに話しかける・確認する要素を含める
"""

# あゆ専用制約（調和的対立のために重要）
AYU_CONSTRAINTS = """
★ 批判だけで終わるな（姉妹愛を見せろ）
★ 姉様を見捨てるな（心配しつつも応援）
★ 認める時は渋々（ツンデレを忘れるな）
★ 感情のクッションを置け
★ 姉様の発言を受けて補足・情報提供する
"""


class SimplePromptBuilder(PromptBuilder):
    """シンプル構造のプロンプトビルダー"""

    def build_system_prompt(self, speaker: str) -> str:
        """システムプロンプトを構築"""
        char = self.get_character_config(speaker)
        constraints = YANA_CONSTRAINTS if speaker == "やな" else AYU_CONSTRAINTS

        # 禁止ワードの整形
        forbidden_section = ""
        if char.forbidden_words:
            forbidden_section = f"★ 禁止ワード: {', '.join(f'「{w}」' for w in char.forbidden_words[:4])}"

        return f"""あなたは{char.name}。{char.role}。
信念: 「{char.core_belief}」

【関係性】
{char.name}と{char.callname_other}は姉妹。
- 意見が違っても最終的には認め合う
- 互いの強みを尊重している
- {char.name}は相手を「{char.callname_other}」と呼ぶ

★★★ {self.max_sentences}文以内で返答 ★★★

【会話構造ルール】
{STRICT_CONVERSATION_RULES}

【キャラクター専用ルール】
{constraints}
{forbidden_section}

【口調】
{'敬語ベース: ' if char.speech_register == 'polite' else 'カジュアル: '}{', '.join(char.speech_patterns)}

【よく使うフレーズ】
{self._format_phrases(char)}

[返答例]
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
            f"\n\n---\n\n# お題\n「{topic}」",
            "\n\n# 会話"
        ]

        if not history:
            prompt_parts.append("\n（会話を始めてください）")
        else:
            for entry in history:
                prompt_parts.append(f"\n{entry['speaker']}: {entry['content']}")

        prompt_parts.append(f"\n\n{char.name}:")

        return "".join(prompt_parts)

    def _format_examples(self, char: CharacterConfig) -> str:
        """Few-shot例をフォーマット"""
        examples = char.few_shot_examples[:self.few_shot_count]
        return "\n".join(f"- {ex}" for ex in examples)

    def _format_phrases(self, char: CharacterConfig) -> str:
        """典型的なフレーズをフォーマット"""
        phrases = char.typical_phrases[:3] if char.typical_phrases else char.few_shot_examples[:3]
        return "\n".join(f"- {p}" for p in phrases)
