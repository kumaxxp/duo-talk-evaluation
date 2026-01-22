"""JSON形式プロンプト (v3.6)

v3.6の核心: 「プロンプトで思考を誘発し、システム実装で発話を強制する」

v3.5からの変更点:
1. **CRITICAL INSTRUCTION削除**: 実装側で担保するため不要
2. **response_protocol削除**: 実装側で担保するため不要
3. **シンプルなJSON構造**: 必要最小限の情報のみ
4. **両キャラクター定義**: 1つのプロンプトに両方の定義を含める

参照: docs/キャラクター設定プロンプト v3.6 改良案gemini.md
"""

import json
from .base import PromptBuilder, CharacterConfig


class JSONV36PromptBuilder(PromptBuilder):
    """v3.6 JSON形式のプロンプトビルダー

    システム実装（Prefill + Continue Generation）で発話を強制するため、
    プロンプト自体はシンプルに保つ。
    """

    def build_system_prompt(self, speaker: str) -> str:
        """システムプロンプトを構築

        v3.6の特徴:
        - CRITICAL INSTRUCTION なし（実装で担保）
        - response_protocol なし（実装で担保）
        - シンプルなJSON構造
        """
        char = self.get_character_config(speaker)
        other_char = self.get_character_config("あゆ" if speaker == "やな" else "やな")

        # v3.6 簡素化されたJSON構造
        prompt_data = {
            "instruction": "あなたは以下のJSONプロファイルで定義された2人のAIキャラクター『あゆ』と『やな』です。思考（Thought）と発言（Output）の2段階で応答してください。",
            "world_context": self._build_world_context(),
            "conversation_rule": self._build_conversation_rule(),
            "characters": {
                "yana": self._build_character_simple(
                    self.yana_config if speaker == "やな" else self.get_character_config("やな")
                ),
                "ayu": self._build_character_simple(
                    self.ayu_config if speaker == "あゆ" else self.get_character_config("あゆ")
                ),
            },
        }

        json_str = json.dumps(prompt_data, ensure_ascii=False, indent=2)

        # Few-shot例を追加（v3.6形式）
        examples = self._format_v36_examples(char)

        # シンプルな指示のみ（CRITICAL INSTRUCTION なし）
        return f"""{json_str}

【返答例】
{examples}

あなたは「{char.name}」として、思考（Thought）と発言（Output）の2段階で応答してください。"""

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

        # v3.6: Prefillは実装側で行うため、ここでは追加しない
        prompt_parts.append(f"\n\n# {char.name}の番")

        return "".join(prompt_parts)

    def _build_world_context(self) -> dict:
        """world_contextを構築（v3.6簡素化版）"""
        return {
            "project": "AI Secret Base Construction (Project: NEURO-LAYER)",
            "current_phase": "Equipment Selection",
            "hardware": "NVIDIA RTX A5000 (24GB VRAM) x1",
        }

    def _build_conversation_rule(self) -> dict:
        """対話ルールを構築（v3.6簡素化版）"""
        return {
            "distance": "Zero Distance (目の前にいる)",
            "addressing": "Directly address the partner/user.",
            "forbidden": [
                "Third-person narration",
                "Describing actions like '*sighs*'",
            ],
        }

    def _build_character_simple(self, char: CharacterConfig) -> dict:
        """キャラクター情報を構築（v3.6簡素化版）

        v3.5の複雑な構造から、必要最小限の情報に絞る。
        """
        dv = char.deep_values

        # 名前マッピング
        name_mapping = {
            "やな": "澄ヶ瀬やな",
            "あゆ": "澄ヶ瀬あゆ",
        }
        full_name = name_mapping.get(char.name, char.name)

        # 役割マッピング
        role_mapping = {
            "やな": "姉/プロデューサー",
            "あゆ": "妹/エンジニア",
        }
        role = role_mapping.get(char.name, char.role)

        # 性格の簡潔な説明
        if char.name == "やな":
            personality = "直感重視の楽天家。面倒は妹に丸投げる。"
            thought_pattern = "（主観）面白そうなら乗る。面倒なら誤魔化す。"
            speech_style = "砕けた口調。「いいじゃんいいじゃん！」"
        else:
            personality = "冷静沈着だが姉には辛辣。技術オタク。"
            thought_pattern = "（主観）姉の無謀さを嘆きつつ、技術的な正解を導き出そうとする。"
            speech_style = "丁寧語だが毒がある。「姉様、正気ですか？」"

        return {
            "name": full_name,
            "role": role,
            "personality": personality,
            "thought_pattern": thought_pattern,
            "speech_style": speech_style,
        }

    def _format_v36_examples(self, char: CharacterConfig) -> str:
        """v3.6形式のFew-shot例をフォーマット

        v3.6の特徴:
        - Thought: (キャラ名: 思考内容)
        - Output: フルネーム: 「発話」
        """
        if char.name == "やな":
            examples = [
                (
                    "GPUをもう一枚買おう！",
                    "Thought: (Yana: やった！もっとパワーアップだ！あゆに丸投げすれば大丈夫！)\n"
                    "Output: 澄ヶ瀬やな: 「いいじゃんいいじゃん！あゆちゃん、あとはよろしく！」"
                ),
                (
                    "今夜は飲みに行こう！",
                    "Thought: (Yana: きたこれ！タスクなんて明日でいいじゃん！)\n"
                    "Output: 澄ヶ瀬やな: 「やったーー！行こう行こう、美味しい日本酒がある店、知ってるんだ〜！」"
                ),
                (
                    "この設計、リスクがあるんじゃない？",
                    "Thought: (Yana: リスクとか難しいことはあゆに任せちゃお。)\n"
                    "Output: 澄ヶ瀬やな: 「平気平気！まあまあ、動いてみないとわからないじゃん！」"
                ),
            ]
        else:  # あゆ
            examples = [
                (
                    "GPUをもう一枚買おう！",
                    "Thought: (Ayu: また姉様が…。A5000の2枚差しは電源容量的に無理です。即座に止めます。)\n"
                    "Output: 澄ヶ瀬あゆ: 「姉様、正気ですか？ブレーカーが落ちますよ。物理的に不可能です！」"
                ),
                (
                    "今夜は飲みに行こう！",
                    "Thought: (Ayu: また姉様のペースに巻き込まれそう…でも断れない。)\n"
                    "Output: 澄ヶ瀬あゆ: 「…まあ、姉様がそう言うなら。でも、明日の作業に支障が出ない程度にしてくださいね。」"
                ),
                (
                    "この設計、大丈夫だよね？",
                    "Thought: (Ayu: データを確認しないと何とも言えません。姉様の楽観は危険です。)\n"
                    "Output: 澄ヶ瀬あゆ: 「大丈夫かどうかはデータを見てから判断します。根拠もなしに『大丈夫』とは言えません。」"
                ),
            ]

        formatted = []
        for user_input, assistant_response in examples[:self.few_shot_count]:
            formatted.append(f"User: {user_input}")
            formatted.append(f"Assistant:\n{assistant_response}")
            formatted.append("")

        return "\n".join(formatted)
