"""v3.3プロンプト改良テスト

v3.3の主な変更点:
1. JSON Schema形式への完全移行
2. 思考プロセス（Thought）の強制
3. 動的コンテキスト（Dynamic Context）の導入
4. mandatory_phrasesの導入
"""

import json
import pytest

from experiments.ab_test.prompts.base import (
    YANA_CONFIG,
    AYU_CONFIG,
    CharacterConfig,
)


class TestV33WorldContext:
    """動的コンテキスト（World Context）テスト（v3.3）"""

    def test_yana_has_world_context(self):
        """やなにworld_contextが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.world_context is not None

    def test_ayu_has_world_context(self):
        """あゆにworld_contextが存在すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.world_context is not None

    def test_world_context_has_project(self):
        """world_contextにproject情報があること"""
        wc = YANA_CONFIG.deep_values.world_context
        assert wc.project is not None
        assert "AI" in wc.project or "基地" in wc.project

    def test_world_context_has_current_phase(self):
        """world_contextにcurrent_phaseがあること"""
        wc = YANA_CONFIG.deep_values.world_context
        assert wc.current_phase is not None

    def test_world_context_has_hardware_constraint(self):
        """world_contextにhardware_constraintがあること"""
        wc = YANA_CONFIG.deep_values.world_context
        assert wc.hardware_constraint is not None
        assert "RTX" in wc.hardware_constraint or "GPU" in wc.hardware_constraint


class TestV33ThoughtPattern:
    """思考パターン（Thought Pattern）テスト（v3.3）"""

    def test_yana_has_thought_pattern(self):
        """やなにthought_patternが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.thought_pattern is not None
        assert len(dv.thought_pattern) > 0

    def test_ayu_has_thought_pattern(self):
        """あゆにthought_patternが存在すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.thought_pattern is not None
        assert len(dv.thought_pattern) > 0

    def test_yana_thought_pattern_content(self):
        """やなのthought_patternが直感的な判断基準を含むこと"""
        tp = YANA_CONFIG.deep_values.thought_pattern
        assert "面白" in tp or "楽" in tp or "直感" in tp

    def test_ayu_thought_pattern_content(self):
        """あゆのthought_patternが分析的な判断基準を含むこと（v3.4: 主観化対応）"""
        tp = AYU_CONFIG.deep_values.thought_pattern
        # v3.3: 技術、コスト、データ、根拠
        # v3.4: リスク、論破、制御、主観（主観化された思考パターン）
        assert "技術" in tp or "コスト" in tp or "データ" in tp or "根拠" in tp or "リスク" in tp or "論破" in tp


class TestV33MandatoryPhrases:
    """必須フレーズ（Mandatory Phrases）テスト（v3.3）"""

    def test_yana_has_mandatory_phrases(self):
        """やなにmandatory_phrasesが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.mandatory_phrases is not None
        assert len(dv.mandatory_phrases) >= 3

    def test_ayu_has_mandatory_phrases(self):
        """あゆにmandatory_phrasesが存在すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.mandatory_phrases is not None
        assert len(dv.mandatory_phrases) >= 3

    def test_yana_mandatory_phrases_content(self):
        """やなのmandatory_phrasesがやならしいフレーズを含むこと"""
        mp = YANA_CONFIG.deep_values.mandatory_phrases
        phrases_text = " ".join(mp)
        # やならしいフレーズ: 楽観的、丸投げ、楽しい
        assert "あゆ" in phrases_text or "よろしく" in phrases_text or "面白" in phrases_text

    def test_ayu_mandatory_phrases_content(self):
        """あゆのmandatory_phrasesがあゆらしいフレーズを含むこと"""
        mp = AYU_CONFIG.deep_values.mandatory_phrases
        phrases_text = " ".join(mp)
        # あゆらしいフレーズ: 技術的、データ、コスト
        assert "姉様" in phrases_text or "データ" in phrases_text or "技術" in phrases_text


class TestV33RelationshipRules:
    """関係性ルール（Relationship Rules）テスト（v3.3）"""

    def test_yana_has_relationship_rules(self):
        """やなにrelationship_rulesが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.relationship_rules is not None

    def test_relationship_rules_has_dynamic(self):
        """relationship_rulesにdynamic（関係性タイプ）があること"""
        rr = YANA_CONFIG.deep_values.relationship_rules
        assert rr.dynamic is not None
        assert "調和" in rr.dynamic or "Harmoni" in rr.dynamic

    def test_relationship_rules_has_flow(self):
        """relationship_rulesにflow（会話フロー）があること"""
        rr = YANA_CONFIG.deep_values.relationship_rules
        assert rr.flow is not None
        assert len(rr.flow) > 0


class TestV33ResponseFormat:
    """レスポンスフォーマット（Response Format）テスト（v3.3）"""

    def test_yana_has_response_format(self):
        """やなにresponse_formatが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.response_format is not None

    def test_response_format_has_thought_step(self):
        """response_formatにThoughtステップがあること"""
        rf = YANA_CONFIG.deep_values.response_format
        assert rf.thought_step is not None
        assert "Thought" in rf.thought_step or "思考" in rf.thought_step

    def test_response_format_has_output_step(self):
        """response_formatにOutputステップがあること"""
        rf = YANA_CONFIG.deep_values.response_format
        assert rf.output_step is not None
        assert "Output" in rf.output_step or "発言" in rf.output_step


class TestV33JSONPromptBuilder:
    """v3.3 JSONプロンプトビルダーテスト"""

    def test_json_builder_exists(self):
        """JSONPromptBuilderが存在すること"""
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        assert builder is not None

    def test_json_builder_generates_valid_json(self):
        """JSONPromptBuilderが有効なJSONを生成すること"""
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        # プロンプトにJSON構造が含まれること
        assert "{" in prompt and "}" in prompt

    def test_json_builder_includes_world_context(self):
        """JSONPromptBuilderがworld_contextを含めること"""
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        assert "world_context" in prompt or "プロジェクト" in prompt

    def test_json_builder_includes_thought_pattern(self):
        """JSONPromptBuilderがthought_patternを含めること"""
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        assert "thought" in prompt.lower() or "思考" in prompt

    def test_json_builder_includes_response_format(self):
        """JSONPromptBuilderがresponse_formatを含めること"""
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        assert "Thought:" in prompt or "Output:" in prompt or "step" in prompt


class TestV33KnowledgeBiasUpdate:
    """知識バイアス更新テスト（v3.3）"""

    def test_yana_knowledge_bias_includes_trends(self):
        """やなのknowledge_biasにトレンド関連があること"""
        kb = YANA_CONFIG.deep_values.knowledge_bias
        kb_text = " ".join(kb.topics) if kb.topics else kb.domain
        assert "トレンド" in kb_text or "Trend" in kb_text or "酒" in kb_text

    def test_ayu_knowledge_bias_includes_tech_stack(self):
        """あゆのknowledge_biasにテックスタック関連があること"""
        kb = AYU_CONFIG.deep_values.knowledge_bias
        kb_text = " ".join(kb.topics) if kb.topics else kb.domain
        assert "Python" in kb_text or "GPU" in kb_text or "ガジェット" in kb_text or "テック" in kb_text


class TestV33CharacterPersonality:
    """キャラクター性格更新テスト（v3.3）"""

    def test_yana_personality_has_core(self):
        """やなのpersonalityにcoreが定義されていること"""
        # v3.3ではpersonalityがより詳細に定義される
        char = YANA_CONFIG
        assert len(char.personality) >= 3
        personality_text = " ".join(char.personality)
        assert "直感" in personality_text or "楽観" in personality_text

    def test_ayu_personality_has_core(self):
        """あゆのpersonalityにcoreが定義されていること"""
        char = AYU_CONFIG
        assert len(char.personality) >= 3
        personality_text = " ".join(char.personality)
        assert "論理" in personality_text or "冷静" in personality_text or "慎重" in personality_text
