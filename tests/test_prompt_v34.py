"""v3.4プロンプトテスト

v3.4の主な変更点:
1. 思考（Thought）の主観化 - 観察者視点から当事者視点へ
2. 対話距離の「ゼロ距離」化 - conversation_rule追加
3. 出力分離の徹底 - Sandwich Instruction
"""

import pytest
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))

from experiments.ab_test.prompts.base import (
    YANA_CONFIG,
    AYU_CONFIG,
    ConversationRule,
)


class TestV34ConversationRule:
    """対話ルール（Conversation Rule）テスト（v3.4）"""

    def test_yana_has_conversation_rule(self):
        """やなにconversation_ruleが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.conversation_rule is not None

    def test_ayu_has_conversation_rule(self):
        """あゆにconversation_ruleが存在すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.conversation_rule is not None

    def test_conversation_rule_has_distance(self):
        """conversation_ruleにdistanceがあること"""
        cr = YANA_CONFIG.deep_values.conversation_rule
        assert cr.distance is not None
        assert "Zero" in cr.distance or "ゼロ" in cr.distance

    def test_conversation_rule_has_addressing(self):
        """conversation_ruleにaddressingがあること"""
        cr = YANA_CONFIG.deep_values.conversation_rule
        assert cr.addressing is not None
        assert "Direct" in cr.addressing or "直接" in cr.addressing

    def test_conversation_rule_has_forbidden_style(self):
        """conversation_ruleにforbidden_styleがあること"""
        cr = YANA_CONFIG.deep_values.conversation_rule
        assert cr.forbidden_style is not None
        assert len(cr.forbidden_style) >= 2


class TestV34SubjectiveThought:
    """主観的思考パターンテスト（v3.4）"""

    def test_yana_thought_pattern_is_subjective(self):
        """やなのthought_patternが主観的であること"""
        dv = YANA_CONFIG.deep_values
        tp = dv.thought_pattern
        # v3.4では主観的な表現が含まれる
        assert "主観" in tp or "言い訳" in tp or "面白" in tp or "任せる" in tp

    def test_ayu_thought_pattern_is_subjective(self):
        """あゆのthought_patternが主観的であること"""
        dv = AYU_CONFIG.deep_values
        tp = dv.thought_pattern
        # v3.4では主観的な表現が含まれる
        assert "主観" in tp or "言い返" in tp or "論破" in tp or "制御" in tp


class TestV34ForbiddenStyle:
    """禁止スタイルテスト（v3.4）"""

    def test_forbidden_style_includes_email_formality(self):
        """Email-like formalityが禁止されていること"""
        cr = YANA_CONFIG.deep_values.conversation_rule
        forbidden = " ".join(cr.forbidden_style).lower()
        assert "email" in forbidden or "メール" in forbidden or "距離" in forbidden

    def test_forbidden_style_includes_detached_observation(self):
        """Detached observationが禁止されていること"""
        cr = YANA_CONFIG.deep_values.conversation_rule
        forbidden = " ".join(cr.forbidden_style).lower()
        assert "detach" in forbidden or "観察" in forbidden or "分析" in forbidden or "第三者" in forbidden

    def test_forbidden_style_includes_action_description(self):
        """アクション描写（*sighs*等）が禁止されていること"""
        cr = YANA_CONFIG.deep_values.conversation_rule
        forbidden = " ".join(cr.forbidden_style).lower()
        assert "action" in forbidden or "描写" in forbidden or "*" in forbidden or "ナレーション" in forbidden


class TestV34OutputSeparation:
    """出力分離テスト（v3.4）"""

    def test_response_format_enforces_separation(self):
        """response_formatが分離を強制すること"""
        dv = YANA_CONFIG.deep_values
        rf = dv.response_format
        # Thought stepに「内部」「First-Person」「主観」などが含まれる
        assert "First" in rf.thought_step or "内部" in rf.thought_step or "主観" in rf.thought_step or "感情" in rf.thought_step
        # Output stepに「直接」「DIRECT」「発言」などが含まれる
        assert "Direct" in rf.output_step or "直接" in rf.output_step or "発言" in rf.output_step


class TestV34JSONPromptBuilder:
    """v3.4 JSONプロンプトビルダーテスト"""

    def test_json_builder_includes_conversation_rule(self):
        """JSONビルダーがconversation_ruleを含めること"""
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        assert "conversation_rule" in prompt or "Zero" in prompt or "distance" in prompt

    def test_json_builder_includes_sandwich_instruction(self):
        """JSONビルダーがSandwich Instructionを含めること"""
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_dialogue_prompt("やな", "テスト", [])
        # Sandwich Instruction（出力制約）が含まれる
        assert "Output:" in prompt or "Thought:" in prompt

    def test_json_builder_forbids_narration(self):
        """JSONビルダーがナレーション禁止を含めること"""
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        # ナレーション禁止の指示が含まれる
        assert "narrat" in prompt.lower() or "ナレーション" in prompt or "第三者" in prompt or "forbidden" in prompt.lower()


class TestV34FewShotExamples:
    """v3.4 Few-shot例テスト"""

    def test_yana_has_subjective_examples(self):
        """やなのFew-shot例が主観的であること"""
        examples = YANA_CONFIG.few_shot_examples
        # 主観的な表現（感嘆符、直接的な呼びかけ）が含まれる
        examples_text = " ".join(examples)
        assert "！" in examples_text or "あゆ" in examples_text

    def test_ayu_has_direct_examples(self):
        """あゆのFew-shot例が直接的であること"""
        examples = AYU_CONFIG.few_shot_examples
        # 直接的な表現が含まれる
        examples_text = " ".join(examples)
        assert "姉様" in examples_text or "です" in examples_text


class TestV34DataclassStructure:
    """v3.4データクラス構造テスト"""

    def test_conversation_rule_dataclass_exists(self):
        """ConversationRuleデータクラスが存在すること"""
        assert ConversationRule is not None

    def test_conversation_rule_has_required_fields(self):
        """ConversationRuleに必須フィールドがあること"""
        cr = ConversationRule(
            distance="Zero Distance",
            addressing="Direct",
            forbidden_style=["Email-like formality"]
        )
        assert cr.distance == "Zero Distance"
        assert cr.addressing == "Direct"
        assert len(cr.forbidden_style) == 1


class TestV34BackwardsCompatibility:
    """v3.4後方互換性テスト"""

    def test_deep_values_still_has_world_context(self):
        """DeepValuesにworld_contextがまだあること（v3.3）"""
        dv = YANA_CONFIG.deep_values
        assert dv.world_context is not None

    def test_deep_values_still_has_mandatory_phrases(self):
        """DeepValuesにmandatory_phrasesがまだあること（v3.3）"""
        dv = YANA_CONFIG.deep_values
        assert dv.mandatory_phrases is not None
        assert len(dv.mandatory_phrases) >= 3

    def test_deep_values_still_has_response_format(self):
        """DeepValuesにresponse_formatがまだあること（v3.3）"""
        dv = YANA_CONFIG.deep_values
        assert dv.response_format is not None
