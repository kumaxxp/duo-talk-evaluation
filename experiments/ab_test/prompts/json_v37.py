"""JSON形式プロンプト (v3.7)

v3.7の核心: 「名前を出力させない（発言内容のみ出力）」

v3.6からの変更点:
1. **Few-shot例**: 名前表記を削除、`Output: 「...」` 形式に統一
2. **conversation_rule**: format指示を追加

参照: docs/キャラクター設定プロンプト v3.7 改良案gemini.md
"""

import json
from .base import PromptBuilder, CharacterConfig


class JSONV37PromptBuilder(PromptBuilder):
    """v3.7 JSON形式のプロンプトビルダー

    名前を書かせず、発言内容のみを出力させる。
    """

    def build_system_prompt(self, speaker: str) -> str:
        """システムプロンプトを構築

        v3.7の特徴:
        - Few-shot例から名前を削除
        - `Output: 「...」` 形式を強制
        """
        char = self.get_character_config(speaker)
        other_char = self.get_character_config("あゆ" if speaker == "やな" else "やな")

        # v3.7 JSON構造
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

        # Few-shot例を追加（v3.7形式: 名前なし）
        examples = self._format_v37_examples(char)

        return f"""{json_str}

【返答例】
{examples}

あなたは「{char.name}」として、思考（Thought）と発言（Output）の2段階で応答してください。
Outputは必ず「」で始めてください。名前は書かないでください。"""

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

        # v3.7: Prefillは実装側で行うため、ここでは追加しない
        prompt_parts.append(f"\n\n# {char.name}の番")

        return "".join(prompt_parts)

    def _build_world_context(self) -> dict:
        """world_contextを構築"""
        return {
            "project": "AI Secret Base Construction (Project: NEURO-LAYER)",
            "current_phase": "Equipment Selection",
            "hardware": "NVIDIA RTX A5000 (24GB VRAM) x1",
        }

    def _build_conversation_rule(self) -> dict:
        """対話ルールを構築（v3.7拡張版）

        v3.7: format指示を追加
        """
        return {
            "distance": "Zero Distance (目の前にいる)",
            "addressing": "Directly address the partner.",
            "format": "Output MUST start with '「' (opening bracket). Do NOT write character names.",
            "forbidden": [
                "Third-person narration",
                "Describing actions like '*sighs*'",
                "Writing character names before dialogue",
            ],
        }

    def _build_character_simple(self, char: CharacterConfig) -> dict:
        """キャラクター情報を構築（簡素化版）"""
        dv = char.deep_values

        # 名前マッピング
        name_mapping = {
            "やな": "澄ヶ瀬やな",
            "あゆ": "澄ヶ瀬あゆ",
        }
        full_name = name_mapping.get(char.name, char.name)

        # 性格の簡潔な説明
        if char.name == "やな":
            personality = "直感重視の楽天家。"
            thought_pattern = "（主観）面白そうなら乗る。"
            speech_style = "砕けた口調。「いいじゃんいいじゃん！」"
        else:
            personality = "冷静沈着だが姉には辛辣。"
            thought_pattern = "（主観）姉の無謀さを嘆く。"
            speech_style = "丁寧語だが毒がある。「姉様、正気ですか？」"

        return {
            "name": full_name,
            "personality": personality,
            "thought_pattern": thought_pattern,
            "speech_style": speech_style,
        }

    def _format_v37_examples(self, char: CharacterConfig) -> str:
        """v3.7形式のFew-shot例をフォーマット

        v3.7の特徴:
        - Thought: (キャラ名: 思考内容)
        - Output: 「発話」 ← 名前なし！
        """
        if char.name == "やな":
            examples = [
                (
                    "GPUをもう一枚買おう！",
                    "Thought: (Yana: やった！もっとパワーアップだ！)\n"
                    "Output: 「いいじゃんいいじゃん！あゆ、あとはよろしく！」"
                ),
                (
                    "今夜は飲みに行こう！",
                    "Thought: (Yana: きたこれ！タスクなんて明日でいいじゃん！)\n"
                    "Output: 「やったーー！行こう行こう！美味しい日本酒がある店、知ってるんだ〜！」"
                ),
                (
                    "この設計、リスクがあるんじゃない？",
                    "Thought: (Yana: リスクとか難しいことはあゆに任せちゃお。)\n"
                    "Output: 「平気平気！まあまあ、動いてみないとわからないじゃん！」"
                ),
            ]
        else:  # あゆ
            examples = [
                (
                    "GPUをもう一枚買おう！",
                    "Thought: (Ayu: また姉様が…。電源容量的に無理です。)\n"
                    "Output: 「姉様、正気ですか？ブレーカーが落ちますよ。」"
                ),
                (
                    "今夜は飲みに行こう！",
                    "Thought: (Ayu: また姉様のペースに巻き込まれそう…でも断れない。)\n"
                    "Output: 「…まあ、姉様がそう言うなら。でも、明日の作業に支障が出ない程度にしてくださいね。」"
                ),
                (
                    "この設計、大丈夫だよね？",
                    "Thought: (Ayu: データを確認しないと何とも言えません。)\n"
                    "Output: 「大丈夫かどうかはデータを見てから判断します。根拠もなしに『大丈夫』とは言えません。」"
                ),
            ]

        formatted = []
        for user_input, assistant_response in examples[:self.few_shot_count]:
            formatted.append(f"User: {user_input}")
            formatted.append(f"Assistant:\n{assistant_response}")
            formatted.append("")

        return "\n".join(formatted)
