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

        # 禁止ワードの整形（全てのワードを含める）
        forbidden_section = ""
        if char.forbidden_words:
            forbidden_section = f"★ 禁止ワード: {', '.join(f'「{w}」' for w in char.forbidden_words)}"

        # 対話ルールの整形（あゆ専用）
        interaction_rules_section = self._format_interaction_rules(char)

        return f"""あなたは{char.name}。{char.role}。
信念: 「{char.core_belief}」
{self._format_background_info(char)}
【関係性】
{char.name}と{char.callname_other}は姉妹。
- 意見が違っても最終的には認め合う
- 互いの強みを尊重している
- {char.name}は相手を「{char.callname_other}」と呼ぶ
{self._format_knowledge_bias(char)}
{self._format_ai_base_attitude(char)}
★★★ {self.max_sentences}文以内で返答 ★★★

【会話構造ルール】
{STRICT_CONVERSATION_RULES}
{self._format_conversation_style(char)}
{self._format_catchphrase_rules(char)}
【キャラクター専用ルール】
{constraints}
{forbidden_section}
{interaction_rules_section}
【口調】
{'敬語ベース: ' if char.speech_register == 'polite' else 'カジュアル: '}{', '.join(char.speech_patterns)}
{self._format_speech_variations(char)}
{self._format_decision_style(char)}
{self._format_feature_phrases(char)}
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

    def _format_interaction_rules(self, char: CharacterConfig) -> str:
        """対話ルールをフォーマット（あゆ専用）"""
        if not char.interaction_rules:
            return ""

        rules = char.interaction_rules
        sections = ["\n【対話ルール（調和的対立）】"]

        # 批判ガイドライン
        sections.append("＜批判ガイドライン＞")
        for i, guideline in enumerate(rules.criticism_guidelines, 1):
            sections.append(f"{i}. {guideline}")

        # NGパターン
        sections.append("\n＜NGパターン（避けるべき）＞")
        for pattern_name, bad_example in rules.ng_examples:
            sections.append(f"- {pattern_name}: 「{bad_example}」")

        # OKパターン
        sections.append("\n＜OKパターン（推奨）＞")
        for pattern_name, good_example in rules.ok_examples:
            sections.append(f"- {pattern_name}: 「{good_example}」")

        return "\n".join(sections)

    def _format_decision_style(self, char: CharacterConfig) -> str:
        """判断スタイルをフォーマット（v3.0）"""
        if not char.deep_values:
            return ""

        dv = char.deep_values
        lines = ["\n【判断スタイル】"]
        for style in dv.decision_style:
            lines.append(f"- {style}")
        return "\n".join(lines)

    def _format_feature_phrases(self, char: CharacterConfig) -> str:
        """特徴フレーズをフォーマット（v3.0）"""
        if not char.feature_phrases:
            return ""

        lines = ["\n【特徴的なフレーズ - 積極的に使う】"]
        for phrase in char.feature_phrases:
            lines.append(f"- 「{phrase}」")
        return "\n".join(lines)

    def _format_background_info(self, char: CharacterConfig) -> str:
        """背景情報をフォーマット（v3.1）"""
        if not char.deep_values or not char.deep_values.identity:
            return ""

        dv = char.deep_values
        identity = dv.identity

        lines = ["\n【基本情報】"]
        lines.append(f"- フルネーム: {identity.full_name}（{identity.reading}）")
        lines.append(f"- 誕生日: {identity.birthday}（{identity.birthplace}で誕生）")
        if identity.name_origin:
            lines.append(f"- 名前由来: {identity.name_origin}")
        lines.append(f"- 役割: {identity.role}")
        lines.append("- 居住地: オーナーのPC内に「住み着いている」")

        return "\n".join(lines)

    def _format_knowledge_bias(self, char: CharacterConfig) -> str:
        """知識の偏りをフォーマット（v3.1, v3.2拡張）"""
        if not char.deep_values or not char.deep_values.knowledge_bias:
            return ""

        kb = char.deep_values.knowledge_bias
        lines = [f"\n【知識の偏り - {kb.domain}】"]
        # v3.2: 文脈制限を最初に明記
        if kb.context_restriction:
            lines.append(f"※文脈判断が必須。{kb.context_restriction}")
        lines.append(kb.reason)
        for topic in kb.topics:
            lines.append(f"- {topic}")
        lines.append(f"→ {kb.trigger}")
        # v3.2: 隠す傾向（あゆ専用）
        if kb.hidden_tendency:
            lines.append(f"- {kb.hidden_tendency}")

        return "\n".join(lines)

    def _format_ai_base_attitude(self, char: CharacterConfig) -> str:
        """AI基地建設への態度をフォーマット（v3.1）"""
        if not char.deep_values or not char.deep_values.ai_base_attitude:
            return ""

        aba = char.deep_values.ai_base_attitude
        lines = ["\n【AI基地建設計画】"]
        lines.append(f"- 目標: {aba.goal}")
        if aba.approach:
            lines.append(f"- アプローチ: {aba.approach}")
        if aba.role:
            lines.append(f"- 役割: {aba.role}")
        lines.append("- 期限: 2026年4月")

        return "\n".join(lines)

    def _format_catchphrase_rules(self, char: CharacterConfig) -> str:
        """定型句ルールをフォーマット（v3.2）"""
        if not char.deep_values or not char.deep_values.catchphrase_rules:
            return ""

        cr = char.deep_values.catchphrase_rules
        lines = ["\n【定型句ルール（乱用禁止）】"]

        if cr.max_usage is not None:
            lines.append(f"- 以下は会話全体で{cr.max_usage}回まで:")
            for phrase in cr.restricted_phrases:
                lines.append(f"  - 「{phrase}」")
        else:
            lines.append("- 以下は連呼しない:")
            for phrase in cr.restricted_phrases:
                lines.append(f"  - 「{phrase}」")

        if cr.alternatives:
            lines.append("- 言い換え例:")
            for alt in cr.alternatives:
                lines.append(f"  - 「{alt}」")

        return "\n".join(lines)

    def _format_conversation_style(self, char: CharacterConfig) -> str:
        """会話スタイルをフォーマット（v3.2）"""
        if not char.deep_values or not char.deep_values.conversation_style:
            return ""

        cs = char.deep_values.conversation_style
        lines = ["\n【会話構造ルール（人間らしさ）】"]

        if cs.allows_incomplete_turns:
            lines.append("- 質問で終わる義務はない: 単なる独り言や感嘆詞だけでターンを終えてもよい")
        if cs.allows_reaction_only:
            lines.append("- リアクションのみ可: 「え、無理ですよ」の一言だけでもよい")
        if cs.allows_broken_structure:
            lines.append("- 論理構成を崩す: 「結論→理由→対策」の順序を守らなくてよい")

        return "\n".join(lines)

    def _format_speech_variations(self, char: CharacterConfig) -> str:
        """口調バリエーションをフォーマット（v3.2）"""
        if not char.deep_values or not char.deep_values.speech_variations:
            return ""

        sv = char.deep_values.speech_variations
        lines = ["\n【口調バリエーション】"]
        lines.append("同じ語尾を続けない:")
        for variation in sv:
            lines.append(f"- {variation}")

        return "\n".join(lines)
