"""JSON形式プロンプト (v3.5)

Gemma 3等の最新モデル向けにJSON Schema形式を採用。
ただし、値の中身は「Simple形式」のように文章で詳細に記述し、表現力の低下を防ぐ。

v3.3の主な特徴:
1. JSON Schema形式への移行
2. 思考プロセス（Thought）の強制
3. 動的コンテキスト（Dynamic Context）の導入

v3.4の追加特徴:
1. conversation_rule: Zero Distance（ゼロ距離）対話ルール
2. 思考パターンの主観化（観察者視点→当事者視点）
3. Sandwich Instruction: 出力形式の厳密なロック

v3.5の追加特徴:
1. response_protocol: 3つのルール（Thought必須→Output必須→停止禁止）
2. 思考の圧縮: Thoughtを最大3文に制限
3. Sandwich Instruction強化: CRITICAL INSTRUCTIONに変更
4. Few-shot更新: 短く鋭いThought + 完全なOutput形式
"""

import json
from .base import PromptBuilder, CharacterConfig


class JSONPromptBuilder(PromptBuilder):
    """JSON形式のプロンプトビルダー（v3.3）"""

    def build_system_prompt(self, speaker: str) -> str:
        """システムプロンプトを構築"""
        char = self.get_character_config(speaker)
        dv = char.deep_values

        # JSON構造を構築（v3.5: response_protocol追加）
        prompt_data = {
            "instruction": f"あなたは「{char.name}」として応答してください。以下のJSONプロファイルに従って行動し、発言してください。",
            "world_context": self._build_world_context(dv),
            "conversation_rule": self._build_conversation_rule(dv),  # v3.4追加
            "character": self._build_character(char),
            "relationship_rules": self._build_relationship_rules(dv),
            "response_format": self._build_response_format(dv),
            "response_protocol": self._build_response_protocol(dv),  # v3.5追加
        }

        # JSON部分を文字列化
        json_str = json.dumps(prompt_data, ensure_ascii=False, indent=2)

        # 補足説明を追加
        # v3.4: Sandwich Instruction追加
        return f"""以下のJSONプロファイルに基づいて「{char.name}」を演じてください。

{json_str}

【重要なルール】
1. response_formatに従い、まずThoughtで内部推論を行い、次にOutputで発言してください。
2. {self.max_sentences}文以内で返答してください。
3. mandatory_phrasesを適切なタイミングで使用してください。
4. 相手を「{char.callname_other}」と呼んでください。

[返答例]
{self._format_examples(char)}

{self._build_sandwich_instruction(char)}"""

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
            "\n\n# 会話履歴"
        ]

        if not history:
            prompt_parts.append("\n（会話を始めてください）")
        else:
            for entry in history:
                prompt_parts.append(f"\n{entry['speaker']}: {entry['content']}")

        prompt_parts.append(f"\n\n# あなたの番\nThought: ")

        return "".join(prompt_parts)

    def _build_world_context(self, dv) -> dict:
        """world_contextを構築"""
        if not dv or not dv.world_context:
            return {
                "project": "AI基地建設計画",
                "current_phase": "機材選定中",
                "location": "オーナーのPC内",
                "hardware_constraint": "NVIDIA RTX A5000 (24GB VRAM)",
            }

        wc = dv.world_context
        return {
            "project": wc.project,
            "current_phase": wc.current_phase,
            "location": wc.location,
            "hardware_constraint": wc.hardware_constraint,
        }

    def _build_character(self, char: CharacterConfig) -> dict:
        """キャラクター情報を構築"""
        dv = char.deep_values

        # 基本情報
        character = {
            "name": char.name,
            "role": char.role,
            "personality": {
                "core": dv.one_liner if dv else char.core_belief,
                "speech_style": self._get_speech_style(char),
                "knowledge_bias": self._get_knowledge_bias(dv),
            },
            "thought_pattern": dv.thought_pattern if dv and dv.thought_pattern else "直感に従う",
            "mandatory_phrases": dv.mandatory_phrases if dv and dv.mandatory_phrases else char.feature_phrases,
        }

        return character

    def _get_speech_style(self, char: CharacterConfig) -> str:
        """口調スタイルを取得"""
        register = "丁寧語（〜です、〜ます）" if char.speech_register == "polite" else "砕けた口調（〜だよ、〜じゃん）"
        patterns = "、".join(char.speech_patterns[:3])
        return f"{register}。語尾: {patterns}"

    def _get_knowledge_bias(self, dv) -> list:
        """知識バイアスを取得"""
        if not dv or not dv.knowledge_bias:
            return []

        kb = dv.knowledge_bias
        return kb.topics if kb.topics else [kb.domain]

    def _build_relationship_rules(self, dv) -> dict:
        """関係性ルールを構築"""
        if not dv or not dv.relationship_rules:
            return {
                "dynamic": "Harmonious Conflict (調和的対立)",
                "flow": "アイデア提案 -> 課題指摘 -> 交渉 -> 妥協",
            }

        rr = dv.relationship_rules
        return {
            "dynamic": rr.dynamic,
            "flow": rr.flow,
        }

    def _build_response_format(self, dv) -> dict:
        """レスポンスフォーマットを構築"""
        if not dv or not dv.response_format:
            return {
                "step1": "Thought: キャラクターの内部推論。thought_patternに基づいて考える。",
                "step2": "Output: [キャラクター名]: 実際の発言。speech_styleに従う。",
            }

        rf = dv.response_format
        return {
            "step1": rf.thought_step,
            "step2": rf.output_step,
        }

    def _format_examples(self, char: CharacterConfig) -> str:
        """Few-shot例をフォーマット（v3.5）

        短く鋭いThought + 完全なOutput形式を使用。
        Thoughtは最大3文に制限し、Outputは必ず「」で囲む。
        """
        dv = char.deep_values

        # キャラクター固有のThought例
        if char.name == "やな":
            thought_examples = [
                "面白そう。とりあえず動かしてみよ。",
                "難しいことはあゆに任せちゃお。",
                "えー、そんな心配いらないって！",
            ]
        else:  # あゆ
            thought_examples = [
                "また姉様が無茶を…。リスク評価が必要です。",
                "データを確認してから判断すべきです。",
                "姉様の直感も一理あるかも…悔しいですが。",
            ]

        examples = char.few_shot_examples[:self.few_shot_count]
        formatted = []
        for i, ex in enumerate(examples):
            thought = thought_examples[i % len(thought_examples)]
            formatted.append(f"Thought: {thought}")
            formatted.append(f"Output: {char.name}: 「{ex.strip('「」')}」")
        return "\n".join(formatted[:6])  # 3例まで（各例2行）

    def _build_conversation_rule(self, dv) -> dict:
        """対話ルールを構築（v3.4）

        Zero Distance（ゼロ距離）対話を強制し、
        「観察者効果」「メール的距離感」を解消する。
        """
        if not dv or not dv.conversation_rule:
            return {
                "distance": "Zero Distance (同室にいて、顔を見合わせている距離感)",
                "addressing": "Directly address the partner. Never use third-person narration.",
                "forbidden_style": [
                    "Email-like formality",
                    "Detached observation",
                    "Narrating user's intent",
                    "Describing actions like '*sighs*'",
                ],
            }

        cr = dv.conversation_rule
        return {
            "distance": cr.distance,
            "addressing": cr.addressing,
            "forbidden_style": cr.forbidden_style,
        }

    def _build_sandwich_instruction(self, char: CharacterConfig) -> str:
        """Sandwich Instructionを構築（v3.5）

        ユーザー入力の直前に出力形式をロックし、
        思考と発言の分離を徹底する。
        v3.5: CRITICAL INSTRUCTIONに強化し、Output必須を明確化。
        """
        return f"""*** CRITICAL INSTRUCTION ***
Response Structure:
Thought: (Brief internal monologue in First-Person. Max 3 sentences.)
Output: 「(ACTUAL DIALOGUE. Mandatory.)」

Constraint:
- Do NOT stop generating until 'Output' is complete.
- Talk DIRECTLY to the partner.
- 'Output' is MANDATORY. Never stop at Thought only."""

    def _build_response_protocol(self, dv) -> dict:
        """レスポンスプロトコルを構築（v3.5）

        v3.4で発生した「Thoughtのみ出力」問題を解決するため、
        Thought→Outputの不可分なフローを強制する。
        """
        if not dv or not dv.response_protocol:
            return {
                "rule_1": "ALWAYS start with 'Thought:'. Analyze the input emotionally (max 3 sentences).",
                "rule_2": "ALWAYS follow with 'Output:'. This contains the spoken dialogue.",
                "rule_3": "NEVER stop at Thought. 'Output' is mandatory.",
            }

        rp = dv.response_protocol
        return {
            "rule_1": rp.rule_1,
            "rule_2": rp.rule_2,
            "rule_3": rp.rule_3,
        }
