"""v3.0プロンプト改良のテスト

TDD RED phase: DeepValues, SisterRelation, feature_phrasesの
データ構造とプロンプト出力をテストする。
"""

import pytest


class TestDeepValues:
    """deep_values構造のテスト"""

    def test_yana_has_deep_values(self):
        """やなにdeep_valuesが存在すること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        assert hasattr(YANA_CONFIG, "deep_values")
        assert YANA_CONFIG.deep_values is not None

    def test_yana_decision_style(self):
        """やなの判断スタイルが5つあること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        dv = YANA_CONFIG.deep_values
        assert len(dv.decision_style) == 5
        # 「まず動かす > 計画を練る」が含まれること
        assert any("動かす" in s for s in dv.decision_style)

    def test_yana_quick_rules(self):
        """やなの即断ルールが4つあること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        dv = YANA_CONFIG.deep_values
        assert len(dv.quick_rules) == 4
        # 「迷ったらとりあえず試す」が含まれること
        assert any("試す" in r for r in dv.quick_rules)

    def test_yana_preferences(self):
        """やなの好み（exciting/frustrating）が定義されていること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        dv = YANA_CONFIG.deep_values
        assert "exciting" in dv.preferences
        assert "frustrating" in dv.preferences
        assert len(dv.preferences["exciting"]) >= 2
        assert len(dv.preferences["frustrating"]) >= 2

    def test_ayu_has_deep_values(self):
        """あゆにdeep_valuesが存在すること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        assert hasattr(AYU_CONFIG, "deep_values")
        assert AYU_CONFIG.deep_values is not None

    def test_ayu_decision_style(self):
        """あゆの判断スタイルが5つあること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        dv = AYU_CONFIG.deep_values
        assert len(dv.decision_style) == 5
        # 「データ > 感覚」が含まれること
        assert any("データ" in s for s in dv.decision_style)

    def test_ayu_quick_rules(self):
        """あゆの即断ルールが4つあること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        dv = AYU_CONFIG.deep_values
        assert len(dv.quick_rules) == 4

    def test_ayu_preferences(self):
        """あゆの好みが定義されていること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        dv = AYU_CONFIG.deep_values
        assert "exciting" in dv.preferences
        assert "frustrating" in dv.preferences


class TestSisterRelation:
    """姉妹関係パターンのテスト"""

    def test_yana_sister_relation_exists(self):
        """やなのsister_relationが存在すること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        dv = YANA_CONFIG.deep_values
        assert dv.sister_relation is not None

    def test_yana_toward_other(self):
        """やなの「あゆへの態度」が定義されていること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        dv = YANA_CONFIG.deep_values
        assert len(dv.sister_relation.toward_other) >= 2
        # 「頼りにしている」が含まれること
        assert any("頼り" in t for t in dv.sister_relation.toward_other)

    def test_yana_patterns(self):
        """やなの姉妹パターンが4つあること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        dv = YANA_CONFIG.deep_values
        assert len(dv.sister_relation.patterns) >= 4
        # 「when_ayu_worries」パターンが存在
        assert "when_ayu_worries" in dv.sister_relation.patterns

    def test_ayu_sister_relation_exists(self):
        """あゆのsister_relationが存在すること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        dv = AYU_CONFIG.deep_values
        assert dv.sister_relation is not None

    def test_ayu_toward_other(self):
        """あゆの「やなへの態度」が定義されていること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        dv = AYU_CONFIG.deep_values
        assert len(dv.sister_relation.toward_other) >= 2
        # 「尊敬」が含まれること
        assert any("尊敬" in t for t in dv.sister_relation.toward_other)

    def test_ayu_patterns(self):
        """あゆの姉妹パターンが4つあること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        dv = AYU_CONFIG.deep_values
        assert len(dv.sister_relation.patterns) >= 4
        # 「when_yana_rushes」パターンが存在
        assert "when_yana_rushes" in dv.sister_relation.patterns


class TestFeaturePhrases:
    """特徴フレーズのテスト"""

    YANA_REQUIRED_PHRASES = [
        "あゆがなんとかしてくれるでしょ",
        "平気平気",
        "動いてみないとわからない",
    ]

    AYU_REQUIRED_PHRASES = [
        "まあ、姉様がそう言うなら",
        "ちょっと待ってください",
        "根拠があるのでしょうか",
    ]

    def test_yana_has_feature_phrases(self):
        """やなにfeature_phrasesが存在すること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        assert hasattr(YANA_CONFIG, "feature_phrases")
        assert len(YANA_CONFIG.feature_phrases) >= 3

    def test_yana_feature_phrases_content(self):
        """やなの特徴フレーズが必須フレーズを含むこと"""
        from experiments.ab_test.prompts.base import YANA_CONFIG

        phrases = YANA_CONFIG.feature_phrases
        for required in self.YANA_REQUIRED_PHRASES:
            assert any(
                required in p for p in phrases
            ), f"'{required}' not found in yana's feature_phrases"

    def test_ayu_has_feature_phrases(self):
        """あゆにfeature_phrasesが存在すること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        assert hasattr(AYU_CONFIG, "feature_phrases")
        assert len(AYU_CONFIG.feature_phrases) >= 3

    def test_ayu_feature_phrases_content(self):
        """あゆの特徴フレーズが必須フレーズを含むこと"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        phrases = AYU_CONFIG.feature_phrases
        for required in self.AYU_REQUIRED_PHRASES:
            assert any(
                required in p for p in phrases
            ), f"'{required}' not found in ayu's feature_phrases"


class TestPromptOutputV3:
    """v3.0プロンプト出力のテスト"""

    def test_simple_includes_decision_style(self):
        """Simpleビルダーがdecision_styleを含めること"""
        from experiments.ab_test.prompts.simple import SimplePromptBuilder

        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("やな")
        # 判断スタイルセクションが含まれること
        assert "判断スタイル" in prompt or "decision_style" in prompt

    def test_simple_includes_feature_phrases(self):
        """Simpleビルダーが特徴フレーズを含めること"""
        from experiments.ab_test.prompts.simple import SimplePromptBuilder

        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("やな")
        assert "あゆがなんとかしてくれる" in prompt

    def test_simple_ayu_includes_decision_style(self):
        """あゆのSimpleプロンプトがdecision_styleを含めること"""
        from experiments.ab_test.prompts.simple import SimplePromptBuilder

        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        assert "判断スタイル" in prompt or "decision_style" in prompt
        # 「データ > 感覚」が含まれること
        assert "データ" in prompt

    def test_simple_ayu_includes_feature_phrases(self):
        """あゆのSimpleプロンプトが特徴フレーズを含めること"""
        from experiments.ab_test.prompts.simple import SimplePromptBuilder

        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        assert "姉様がそう言うなら" in prompt

    def test_sillytavern_has_mes_example(self):
        """SillyTavernがmes_exampleスタイルの例文を含めること"""
        from experiments.ab_test.prompts.sillytavern import SillyTavernPromptBuilder

        builder = SillyTavernPromptBuilder()
        prompt = builder.build_system_prompt("やな")
        # SillyTavern形式の例文
        assert "平気平気" in prompt or "動いてみないと" in prompt

    def test_sillytavern_ayu_has_feature_phrases(self):
        """あゆのSillyTavernプロンプトが特徴フレーズを含めること"""
        from experiments.ab_test.prompts.sillytavern import SillyTavernPromptBuilder

        builder = SillyTavernPromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        assert "姉様がそう言うなら" in prompt or "ちょっと待って" in prompt


class TestDataclassStructure:
    """データクラス構造のテスト"""

    def test_deep_values_dataclass_exists(self):
        """DeepValuesデータクラスが存在すること"""
        from experiments.ab_test.prompts.base import DeepValues

        assert DeepValues is not None

    def test_sister_relation_dataclass_exists(self):
        """SisterRelationデータクラスが存在すること"""
        from experiments.ab_test.prompts.base import SisterRelation

        assert SisterRelation is not None

    def test_deep_values_fields(self):
        """DeepValuesに必要なフィールドがあること"""
        from experiments.ab_test.prompts.base import DeepValues

        # dataclassのフィールドを確認
        import dataclasses

        fields = {f.name for f in dataclasses.fields(DeepValues)}
        required_fields = {
            "core_belief",
            "one_liner",
            "decision_style",
            "quick_rules",
            "preferences",
            "sister_relation",
            "speech_habits",
            "out_of_character",
        }
        assert required_fields.issubset(
            fields
        ), f"Missing fields: {required_fields - fields}"

    def test_sister_relation_fields(self):
        """SisterRelationに必要なフィールドがあること"""
        from experiments.ab_test.prompts.base import SisterRelation

        import dataclasses

        fields = {f.name for f in dataclasses.fields(SisterRelation)}
        required_fields = {"toward_other", "patterns"}
        assert required_fields.issubset(
            fields
        ), f"Missing fields: {required_fields - fields}"


class TestBackwardsCompatibility:
    """後方互換性のテスト"""

    def test_character_config_still_works(self):
        """既存のCharacterConfigが動作すること"""
        from experiments.ab_test.prompts.base import CharacterConfig, YANA_CONFIG

        # 既存フィールドが存在すること
        assert YANA_CONFIG.name == "やな"
        assert YANA_CONFIG.callname_self == "やな"
        assert YANA_CONFIG.callname_other == "あゆ"
        assert len(YANA_CONFIG.personality) >= 3
        assert len(YANA_CONFIG.forbidden_words) >= 3

    def test_existing_states_preserved(self):
        """既存のstates定義が保持されていること"""
        from experiments.ab_test.prompts.base import YANA_CONFIG, AYU_CONFIG

        assert len(YANA_CONFIG.states) >= 4
        assert len(AYU_CONFIG.states) >= 4

    def test_existing_interaction_rules_preserved(self):
        """既存のinteraction_rulesが保持されていること"""
        from experiments.ab_test.prompts.base import AYU_CONFIG

        assert AYU_CONFIG.interaction_rules is not None
        assert len(AYU_CONFIG.interaction_rules.criticism_guidelines) >= 3
