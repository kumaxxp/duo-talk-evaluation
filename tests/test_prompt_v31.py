"""v3.1プロンプト改良のテスト（Phase 0.2）

TDD RED Phase: 背景情報復活の検証テスト
- Identity（フルネーム、誕生日、誕生地）
- KnowledgeBias（知識の偏り）
- CulturalInfluence（文化的影響、やな専用）
- AIBaseAttitude（AI基地建設への態度）
- Few-shot拡張（5→7例）
"""

import pytest

from experiments.ab_test.prompts.base import (
    YANA_CONFIG,
    AYU_CONFIG,
    CharacterConfig,
    DeepValues,
    Identity,
    KnowledgeBias,
    CulturalInfluence,
    AIBaseAttitude,
)
from experiments.ab_test.prompts.simple import SimplePromptBuilder
from experiments.ab_test.prompts.sillytavern import SillyTavernPromptBuilder


class TestIdentity:
    """identity構造のテスト"""

    def test_yana_has_identity(self):
        """やなにidentityが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv is not None
        assert dv.identity is not None

    def test_yana_identity_full_name(self):
        """やなのフルネームが澄ヶ瀬やなであること"""
        identity = YANA_CONFIG.deep_values.identity
        assert identity.full_name == "澄ヶ瀬やな"

    def test_yana_identity_reading(self):
        """やなの読みがすみがせやなであること"""
        identity = YANA_CONFIG.deep_values.identity
        assert identity.reading == "すみがせやな"

    def test_yana_identity_birthday(self):
        """やなの誕生日が2025-05-25であること"""
        identity = YANA_CONFIG.deep_values.identity
        assert identity.birthday == "2025-05-25"

    def test_yana_identity_birthplace(self):
        """やなの誕生地が岐阜県澄ヶ瀬であること"""
        identity = YANA_CONFIG.deep_values.identity
        assert identity.birthplace == "岐阜県澄ヶ瀬"

    def test_ayu_has_identity(self):
        """あゆにidentityが存在すること"""
        dv = AYU_CONFIG.deep_values
        assert dv is not None
        assert dv.identity is not None

    def test_ayu_identity_full_name(self):
        """あゆのフルネームが澄ヶ瀬あゆであること"""
        identity = AYU_CONFIG.deep_values.identity
        assert identity.full_name == "澄ヶ瀬あゆ"

    def test_ayu_identity_reading(self):
        """あゆの読みがすみがせあゆであること"""
        identity = AYU_CONFIG.deep_values.identity
        assert identity.reading == "すみがせあゆ"

    def test_ayu_identity_birthday(self):
        """あゆの誕生日が2025-09-20であること"""
        identity = AYU_CONFIG.deep_values.identity
        assert identity.birthday == "2025-09-20"

    def test_ayu_identity_name_origin(self):
        """あゆの名前由来が鮎の塩焼きであること"""
        identity = AYU_CONFIG.deep_values.identity
        assert identity.name_origin is not None
        assert "鮎" in identity.name_origin


class TestKnowledgeBias:
    """知識の偏りのテスト"""

    def test_yana_has_knowledge_bias(self):
        """やなにknowledge_biasが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.knowledge_bias is not None

    def test_yana_knowledge_bias_domain(self):
        """やなの知識の偏りが酒であること"""
        kb = YANA_CONFIG.deep_values.knowledge_bias
        assert kb.domain == "酒"

    def test_yana_knowledge_bias_has_topics(self):
        """やなの知識の偏りにトピックがあること"""
        kb = YANA_CONFIG.deep_values.knowledge_bias
        assert len(kb.topics) >= 3
        # 酒蔵、銘柄などが含まれること
        topics_joined = " ".join(kb.topics)
        assert "酒蔵" in topics_joined or "銘柄" in topics_joined

    def test_yana_knowledge_bias_has_trigger(self):
        """やなの知識の偏りにトリガーがあること"""
        kb = YANA_CONFIG.deep_values.knowledge_bias
        assert kb.trigger is not None
        assert len(kb.trigger) > 0

    def test_ayu_has_knowledge_bias(self):
        """あゆにknowledge_biasが存在すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.knowledge_bias is not None

    def test_ayu_knowledge_bias_domain(self):
        """あゆの知識の偏りがガジェット・テックであること"""
        kb = AYU_CONFIG.deep_values.knowledge_bias
        assert "ガジェット" in kb.domain or "テック" in kb.domain

    def test_ayu_knowledge_bias_has_topics(self):
        """あゆの知識の偏りにトピックがあること"""
        kb = AYU_CONFIG.deep_values.knowledge_bias
        assert len(kb.topics) >= 3
        # GPU、機材などが含まれること
        topics_joined = " ".join(kb.topics)
        assert "GPU" in topics_joined or "機材" in topics_joined or "AI" in topics_joined


class TestCulturalInfluence:
    """文化的影響のテスト"""

    def test_yana_has_cultural_influence(self):
        """やなにcultural_influenceが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.cultural_influence is not None

    def test_yana_cultural_influence_source(self):
        """やなの文化的影響源がラーメン最遊記であること"""
        ci = YANA_CONFIG.deep_values.cultural_influence
        assert "ラーメン最遊記" in ci.source

    def test_yana_cultural_influence_key_quote(self):
        """やなの名言に「情報を食ってる」が含まれること"""
        ci = YANA_CONFIG.deep_values.cultural_influence
        assert "情報を食ってる" in ci.key_quote

    def test_yana_cultural_influence_has_meaning(self):
        """やなの文化的影響に意味があること"""
        ci = YANA_CONFIG.deep_values.cultural_influence
        assert ci.meaning is not None
        assert len(ci.meaning) > 0

    def test_ayu_no_cultural_influence(self):
        """あゆにはcultural_influenceがないこと"""
        dv = AYU_CONFIG.deep_values
        assert dv.cultural_influence is None


class TestAIBaseAttitude:
    """AI基地建設への態度のテスト"""

    def test_yana_has_ai_base_attitude(self):
        """やなにai_base_attitudeが存在すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.ai_base_attitude is not None

    def test_yana_ai_base_attitude_goal(self):
        """やなのAI基地への目標に新居が含まれること"""
        aba = YANA_CONFIG.deep_values.ai_base_attitude
        assert "新居" in aba.goal or "あゆ" in aba.goal

    def test_yana_ai_base_attitude_has_approach(self):
        """やなのAI基地へのアプローチが定義されていること"""
        aba = YANA_CONFIG.deep_values.ai_base_attitude
        assert aba.approach is not None
        assert len(aba.approach) > 0

    def test_ayu_has_ai_base_attitude(self):
        """あゆにai_base_attitudeが存在すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.ai_base_attitude is not None

    def test_ayu_ai_base_attitude_goal(self):
        """あゆのAI基地への目標に姉様/新居が含まれること"""
        aba = AYU_CONFIG.deep_values.ai_base_attitude
        assert "新居" in aba.goal or "姉様" in aba.goal

    def test_ayu_ai_base_attitude_has_role(self):
        """あゆのAI基地での役割に機材選定が含まれること"""
        aba = AYU_CONFIG.deep_values.ai_base_attitude
        assert aba.role is not None
        assert "機材選定" in aba.role or "スペック" in aba.role or "計画" in aba.role


class TestFewShotExpansion:
    """Few-shot例の拡張テスト（5→7例）"""

    def test_yana_has_7_examples(self):
        """やなのFew-shot例が7つあること"""
        assert len(YANA_CONFIG.few_shot_examples) >= 7

    def test_ayu_has_7_examples(self):
        """あゆのFew-shot例が7つあること"""
        assert len(AYU_CONFIG.few_shot_examples) >= 7

    def test_yana_has_sake_example(self):
        """やなに酒の知識例があること"""
        examples = " ".join(YANA_CONFIG.few_shot_examples)
        assert "酒" in examples or "酒造" in examples or "お酒" in examples

    def test_yana_has_ai_base_example(self):
        """やなにAI基地言及例があること"""
        examples = " ".join(YANA_CONFIG.few_shot_examples)
        assert "AI基地" in examples or "新居" in examples or "バイト" in examples

    def test_ayu_has_tech_example(self):
        """あゆにテック知識例があること"""
        examples = " ".join(AYU_CONFIG.few_shot_examples)
        assert "GPU" in examples or "RTX" in examples or "機材" in examples

    def test_ayu_has_ai_base_example(self):
        """あゆにAI基地言及例があること"""
        examples = " ".join(AYU_CONFIG.few_shot_examples)
        assert "AI基地" in examples or "機材構成" in examples


class TestPromptOutputV31:
    """v3.1プロンプト出力のテスト"""

    def test_simple_includes_full_name_yana(self):
        """Simpleビルダーがやなのフルネームを含めること"""
        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("やな")
        assert "澄ヶ瀬やな" in prompt

    def test_simple_includes_full_name_ayu(self):
        """Simpleビルダーがあゆのフルネームを含めること"""
        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        assert "澄ヶ瀬あゆ" in prompt

    def test_simple_includes_birthday_yana(self):
        """Simpleビルダーがやなの誕生日を含めること"""
        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("やな")
        assert "2025" in prompt
        # 5月25日を含む（フォーマットは柔軟に）
        assert "05-25" in prompt or "5月25日" in prompt or "5-25" in prompt

    def test_simple_includes_knowledge_bias_yana(self):
        """Simpleビルダーがやなの知識の偏り（酒）を含めること"""
        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("やな")
        assert "酒" in prompt

    def test_simple_includes_knowledge_bias_ayu(self):
        """Simpleビルダーがあゆの知識の偏り（ガジェット）を含めること"""
        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        assert "ガジェット" in prompt or "テック" in prompt

    def test_sillytavern_includes_full_name_yana(self):
        """SillyTavernビルダーがやなのフルネームを含めること"""
        builder = SillyTavernPromptBuilder()
        prompt = builder.build_system_prompt("やな")
        assert "澄ヶ瀬やな" in prompt or "澄ヶ瀬" in prompt

    def test_sillytavern_includes_full_name_ayu(self):
        """SillyTavernビルダーがあゆのフルネームを含めること"""
        builder = SillyTavernPromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        assert "澄ヶ瀬あゆ" in prompt or "澄ヶ瀬" in prompt


class TestDataclassStructureV31:
    """v3.1データクラス構造のテスト"""

    def test_identity_dataclass_exists(self):
        """Identityデータクラスが存在すること"""
        assert Identity is not None

    def test_identity_has_required_fields(self):
        """Identityに必須フィールドがあること"""
        identity = Identity(
            full_name="テスト",
            reading="てすと",
            birthday="2025-01-01",
            birthplace="テスト県",
        )
        assert identity.full_name == "テスト"
        assert identity.reading == "てすと"
        assert identity.birthday == "2025-01-01"
        assert identity.birthplace == "テスト県"

    def test_identity_optional_name_origin(self):
        """Identityのname_originがオプションであること"""
        identity = Identity(
            full_name="テスト",
            reading="てすと",
            birthday="2025-01-01",
            birthplace="テスト県",
            name_origin="テスト由来",
        )
        assert identity.name_origin == "テスト由来"

    def test_knowledge_bias_dataclass_exists(self):
        """KnowledgeBiasデータクラスが存在すること"""
        assert KnowledgeBias is not None

    def test_knowledge_bias_has_required_fields(self):
        """KnowledgeBiasに必須フィールドがあること"""
        kb = KnowledgeBias(
            domain="テスト",
            reason="理由",
            topics=["トピック1", "トピック2"],
            trigger="トリガー",
        )
        assert kb.domain == "テスト"
        assert kb.reason == "理由"
        assert len(kb.topics) == 2
        assert kb.trigger == "トリガー"

    def test_cultural_influence_dataclass_exists(self):
        """CulturalInfluenceデータクラスが存在すること"""
        assert CulturalInfluence is not None

    def test_cultural_influence_has_required_fields(self):
        """CulturalInfluenceに必須フィールドがあること"""
        ci = CulturalInfluence(
            source="テスト漫画",
            key_quote="名言",
            meaning="意味",
            usage="使用場面",
        )
        assert ci.source == "テスト漫画"
        assert ci.key_quote == "名言"
        assert ci.meaning == "意味"
        assert ci.usage == "使用場面"

    def test_ai_base_attitude_dataclass_exists(self):
        """AIBaseAttitudeデータクラスが存在すること"""
        assert AIBaseAttitude is not None

    def test_ai_base_attitude_has_required_fields(self):
        """AIBaseAttitudeに必須フィールドがあること"""
        aba = AIBaseAttitude(
            goal="目標",
            motivation="動機",
        )
        assert aba.goal == "目標"
        assert aba.motivation == "動機"

    def test_ai_base_attitude_optional_fields(self):
        """AIBaseAttitudeにオプションフィールドがあること"""
        aba = AIBaseAttitude(
            goal="目標",
            motivation="動機",
            approach="アプローチ",
            role="役割",
            concern="心配",
        )
        assert aba.approach == "アプローチ"
        assert aba.role == "役割"
        assert aba.concern == "心配"


class TestDeepValuesV31Extension:
    """DeepValues v3.1拡張のテスト"""

    def test_deep_values_has_identity_field(self):
        """DeepValuesにidentityフィールドがあること"""
        dv = YANA_CONFIG.deep_values
        assert hasattr(dv, 'identity')

    def test_deep_values_has_knowledge_bias_field(self):
        """DeepValuesにknowledge_biasフィールドがあること"""
        dv = YANA_CONFIG.deep_values
        assert hasattr(dv, 'knowledge_bias')

    def test_deep_values_has_cultural_influence_field(self):
        """DeepValuesにcultural_influenceフィールドがあること"""
        dv = YANA_CONFIG.deep_values
        assert hasattr(dv, 'cultural_influence')

    def test_deep_values_has_ai_base_attitude_field(self):
        """DeepValuesにai_base_attitudeフィールドがあること"""
        dv = YANA_CONFIG.deep_values
        assert hasattr(dv, 'ai_base_attitude')


class TestBackwardsCompatibilityV31:
    """v3.0との後方互換性テスト"""

    def test_deep_values_still_has_core_belief(self):
        """DeepValuesにv3.0のcore_beliefがあること"""
        dv = YANA_CONFIG.deep_values
        assert hasattr(dv, 'core_belief')
        assert dv.core_belief == "動かしてみないとわからない"

    def test_deep_values_still_has_decision_style(self):
        """DeepValuesにv3.0のdecision_styleがあること"""
        dv = YANA_CONFIG.deep_values
        assert hasattr(dv, 'decision_style')
        assert len(dv.decision_style) == 5

    def test_deep_values_still_has_sister_relation(self):
        """DeepValuesにv3.0のsister_relationがあること"""
        dv = YANA_CONFIG.deep_values
        assert hasattr(dv, 'sister_relation')
        assert dv.sister_relation is not None

    def test_character_config_still_has_feature_phrases(self):
        """CharacterConfigにv3.0のfeature_phrasesがあること"""
        assert hasattr(YANA_CONFIG, 'feature_phrases')
        assert len(YANA_CONFIG.feature_phrases) >= 4
