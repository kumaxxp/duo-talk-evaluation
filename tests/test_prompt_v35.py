"""v3.5プロンプト改良テスト

v3.5の主な変更点:
1. response_protocol: 3つのルール（Thought必須→Output必須→停止禁止）
2. 思考の圧縮: Thoughtを最大3文に制限
3. Sandwich Instruction強化: CRITICAL INSTRUCTIONに変更
4. Few-shot更新: 短く鋭いThought + 完全なOutput形式
"""

import pytest
from experiments.ab_test.prompts.base import (
    YANA_CONFIG,
    AYU_CONFIG,
    ResponseProtocol,
)
from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder


class TestV35ResponseProtocol:
    """レスポンスプロトコル（Response Protocol）テスト（v3.5）"""

    def test_yana_has_response_protocol(self):
        """やなにresponse_protocolが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.response_protocol is not None

    def test_ayu_has_response_protocol(self):
        """あゆにresponse_protocolが存在すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.response_protocol is not None

    def test_response_protocol_has_rule_1(self):
        """response_protocolにrule_1（Thought必須）があること"""
        rp = YANA_CONFIG.deep_values.response_protocol
        assert rp.rule_1 is not None
        assert "Thought" in rp.rule_1 or "thought" in rp.rule_1.lower()

    def test_response_protocol_has_rule_2(self):
        """response_protocolにrule_2（Output必須）があること"""
        rp = YANA_CONFIG.deep_values.response_protocol
        assert rp.rule_2 is not None
        assert "Output" in rp.rule_2 or "output" in rp.rule_2.lower()

    def test_response_protocol_has_rule_3(self):
        """response_protocolにrule_3（停止禁止）があること"""
        rp = YANA_CONFIG.deep_values.response_protocol
        assert rp.rule_3 is not None
        assert "mandatory" in rp.rule_3.lower() or "never" in rp.rule_3.lower() or "必須" in rp.rule_3


class TestV35ThoughtCompression:
    """思考の圧縮（Thought Compression）テスト（v3.5）"""

    def test_response_protocol_limits_thought_length(self):
        """response_protocolにThoughtの長さ制限があること"""
        rp = YANA_CONFIG.deep_values.response_protocol
        # rule_1にmax 3 sentencesまたは同等の制限が含まれる
        assert "max" in rp.rule_1.lower() or "3" in rp.rule_1 or "sentence" in rp.rule_1.lower()

    def test_ayu_response_protocol_limits_thought(self):
        """あゆのresponse_protocolにも同じ制限があること"""
        rp = AYU_CONFIG.deep_values.response_protocol
        assert "max" in rp.rule_1.lower() or "3" in rp.rule_1 or "sentence" in rp.rule_1.lower()


class TestV35SandwichInstruction:
    """Sandwich Instruction強化テスト（v3.5）"""

    def test_json_builder_uses_critical_instruction(self):
        """JSONビルダーがCRITICAL INSTRUCTIONを使用すること"""
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        assert "CRITICAL" in prompt or "critical" in prompt.lower()

    def test_json_builder_emphasizes_mandatory_output(self):
        """JSONビルダーがOutput必須を強調すること"""
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        assert "mandatory" in prompt.lower() or "必須" in prompt or "MUST" in prompt

    def test_json_builder_includes_do_not_stop(self):
        """JSONビルダーが停止禁止を含むこと"""
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        # "Do NOT stop" or similar
        assert "stop" in prompt.lower() or "停止" in prompt


class TestV35FewShotFormat:
    """Few-shot形式テスト（v3.5）"""

    def test_json_builder_fewshot_has_thought_and_output(self):
        """Few-shotサンプルがThoughtとOutput両方を含むこと"""
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        # Few-shot部分にThoughtとOutput両方が存在
        assert "Thought:" in prompt
        assert "Output:" in prompt

    def test_json_builder_fewshot_output_has_dialogue(self):
        """Few-shotサンプルのOutputに実際の発話が含まれること"""
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        # 「」で囲まれた発話があること
        assert "「" in prompt and "」" in prompt


class TestV35JSONPromptBuilder:
    """v3.5 JSONプロンプトビルダーテスト"""

    def test_json_builder_includes_response_protocol(self):
        """JSONビルダーがresponse_protocolを含むこと"""
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        assert "response_protocol" in prompt or "rule_1" in prompt or "ALWAYS" in prompt

    def test_json_builder_includes_thought_limit(self):
        """JSONビルダーがThought制限を含むこと"""
        builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("あゆ")
        # 3 sentencesまたは同等の表現
        assert "3" in prompt or "three" in prompt.lower() or "sentence" in prompt.lower()


class TestV35DataclassStructure:
    """v3.5データクラス構造テスト"""

    def test_response_protocol_dataclass_exists(self):
        """ResponseProtocolデータクラスが存在すること"""
        assert ResponseProtocol is not None

    def test_response_protocol_has_required_fields(self):
        """ResponseProtocolに必須フィールドがあること"""
        rp = ResponseProtocol(
            rule_1="ALWAYS start with Thought",
            rule_2="ALWAYS follow with Output",
            rule_3="NEVER stop at Thought"
        )
        assert rp.rule_1 is not None
        assert rp.rule_2 is not None
        assert rp.rule_3 is not None


class TestV35BackwardsCompatibility:
    """v3.5後方互換性テスト"""

    def test_deep_values_still_has_conversation_rule(self):
        """DeepValuesに引き続きconversation_ruleがあること（v3.4互換）"""
        dv = YANA_CONFIG.deep_values
        assert dv.conversation_rule is not None

    def test_deep_values_still_has_world_context(self):
        """DeepValuesに引き続きworld_contextがあること（v3.3互換）"""
        dv = YANA_CONFIG.deep_values
        assert dv.world_context is not None

    def test_deep_values_still_has_mandatory_phrases(self):
        """DeepValuesに引き続きmandatory_phrasesがあること"""
        dv = YANA_CONFIG.deep_values
        assert dv.mandatory_phrases is not None
        assert len(dv.mandatory_phrases) >= 3
