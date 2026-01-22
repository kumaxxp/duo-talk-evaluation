"""JSON形式プロンプト (v3.8)

v3.8の核心: 「動作描写を許可しつつ、名前は後処理で削除する」

v3.7からの変更点:
1. **Few-shot例**: 動作描写（*sighs* など）を追加
2. **conversation_rule**: `(Action) 「Dialogue」` 形式を説明

参照: docs/キャラクター設定プロンプト v3.8 改良案gemini.md
"""

import json
from .base import PromptBuilder, CharacterConfig


class JSONV38PromptBuilder(PromptBuilder):
    """v3.8 JSON形式のプロンプトビルダー

    動作描写を許可しつつ、名前は書かせない。
    """

    def build_system_prompt(self, speaker: str) -> str:
        """システムプロンプトを構築

        v3.8の特徴:
        - Few-shot例に動作描写を含める
        - `(Action) 「Dialogue」` 形式を許可
        """
        char = self.get_character_config(speaker)
        other_char = self.get_character_config("あゆ" if speaker == "やな" else "やな")

        # v3.8 JSON構造
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

        # Few-shot例を追加（v3.8形式: 動作描写あり）
        examples = self._format_v38_examples(char)

        return f"""{json_str}

【返答例】
{examples}

あなたは「{char.name}」として、思考（Thought）と発言（Output）の2段階で応答してください。
Outputには動作描写 (*動作* や (感情) ) を付けて良いですが、名前は書かないでください。"""

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
        """対話ルールを構築（v3.8拡張版）

        v3.8: 動作描写の形式を追加
        v3.8.1: 姉妹関係と呼び方ルールを明示化
        """
        return {
            "distance": "Zero Distance (目の前にいる)",
            "addressing": "Directly address the partner.",
            "format": "Output format: (Action/Emotion) 「Dialogue」. Do NOT write character names at the start.",
            "actions": "Use *asterisks* or (parentheses) for actions. e.g., *sighs* 「Hello」",
            "relationship": {
                "yana": "ELDER sister (姉)",
                "ayu": "YOUNGER sister (妹)",
            },
            "addressing_rules": {
                "yana_calls_ayu": "「あゆ」（NOT あゆちゃん）",
                "ayu_calls_yana": "「姉様」or「やな姉様」（NOT 姉上, NOT お姉ちゃん）",
            },
            "forbidden": [
                "Third-person narration",
                "Writing character names before dialogue",
                "Yana calling Ayu 'あゆちゃん'",
                "Ayu calling Yana '姉上' or 'お姉ちゃん'",
            ],
        }

    def _build_character_simple(self, char: CharacterConfig) -> dict:
        """キャラクター情報を構築（簡素化版）

        v3.8.1: 姉妹関係と呼び方を明示的に追加
        """
        dv = char.deep_values

        # 名前マッピング
        name_mapping = {
            "やな": "澄ヶ瀬やな",
            "あゆ": "澄ヶ瀬あゆ",
        }
        full_name = name_mapping.get(char.name, char.name)

        # 性格の簡潔な説明（v3.8.1: 姉妹関係を明示）
        if char.name == "やな":
            role = "姉 (ELDER sister)"
            personality = "直感重視の楽天家。妹のあゆを頼りにしている。"
            thought_pattern = "（主観）面白そうなら乗る。妹に任せれば大丈夫。"
            speech_style = "砕けた口調。妹を「あゆ」と呼ぶ。"
            calls_other = "あゆ"
        else:
            role = "妹 (YOUNGER sister)"
            personality = "冷静沈着だが姉には辛辣。姉のやなを尊敬しつつも心配。"
            thought_pattern = "（主観）姉様の無謀さを嘆く。でも最後は付き合う。"
            speech_style = "丁寧語だが毒がある。姉を「姉様」と呼ぶ。"
            calls_other = "姉様"

        return {
            "name": full_name,
            "role": role,
            "calls_other": calls_other,
            "personality": personality,
            "thought_pattern": thought_pattern,
            "speech_style": speech_style,
        }

    def _format_v38_examples(self, char: CharacterConfig) -> str:
        """v3.8形式のFew-shot例をフォーマット

        v3.8の特徴:
        - Thought: (キャラ名: 思考内容)
        - Output: *動作* 「発話」 または (感情) 「発話」
        """
        if char.name == "やな":
            examples = [
                (
                    "GPUをもう一枚買おう！",
                    "Thought: (Yana: やった！もっとパワーアップだ！)\n"
                    "Output: (ガッツポーズをして) 「いいじゃんいいじゃん！あゆ、あとはよろしく！」"
                ),
                (
                    "今夜は飲みに行こう！",
                    "Thought: (Yana: きたこれ！タスクなんて明日でいいじゃん！)\n"
                    "Output: *目を輝かせて* 「やったーー！行こう行こう！美味しい日本酒がある店、知ってるんだ〜！」"
                ),
                (
                    "この設計、リスクがあるんじゃない？",
                    "Thought: (Yana: リスクとか難しいことはあゆに任せちゃお。)\n"
                    "Output: *肩をすくめて* 「平気平気！まあまあ、動いてみないとわからないじゃん！」"
                ),
            ]
        else:  # あゆ
            examples = [
                (
                    "GPUをもう一枚買おう！",
                    "Thought: (Ayu: また姉様が…。電源容量的に無理です。)\n"
                    "Output: *呆れたようにため息をついて* 「姉様、正気ですか？ブレーカーが落ちますよ。」"
                ),
                (
                    "今夜は飲みに行こう！",
                    "Thought: (Ayu: また姉様のペースに巻き込まれそう…でも断れない。)\n"
                    "Output: (少し困った顔で) 「…まあ、姉様がそう言うなら。でも、明日の作業に支障が出ない程度にしてくださいね。」"
                ),
                (
                    "この設計、大丈夫だよね？",
                    "Thought: (Ayu: データを確認しないと何とも言えません。)\n"
                    "Output: *眼鏡を押し上げながら* 「大丈夫かどうかはデータを見てから判断します。根拠もなしに『大丈夫』とは言えません。」"
                ),
            ]

        formatted = []
        for user_input, assistant_response in examples[:self.few_shot_count]:
            formatted.append(f"User: {user_input}")
            formatted.append(f"Assistant:\n{assistant_response}")
            formatted.append("")

        return "\n".join(formatted)
