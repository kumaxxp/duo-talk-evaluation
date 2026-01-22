"""プロンプトビルダーのテスト

TDD: RED -> GREEN -> REFACTOR
Issue 1: 禁止ワードリスト完全化
Issue 2: Interaction Rules追加
Issue 3: 状態別Few-shot実装
"""

import sys
from pathlib import Path

import pytest

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from experiments.ab_test.prompts.base import (
    YANA_CONFIG,
    AYU_CONFIG,
    CharacterConfig,
    PromptBuilder,
)
from experiments.ab_test.prompts.simple import SimplePromptBuilder
from experiments.ab_test.prompts.layered import LayeredPromptBuilder
from experiments.ab_test.prompts.sillytavern import SillyTavernPromptBuilder


# ========== Issue 1: 禁止ワードテスト ==========

class TestForbiddenWords:
    """禁止ワードリストの完全性テスト"""

    # あゆに必須の禁止褒め言葉（duo-talk-simpleから）
    REQUIRED_AYU_FORBIDDEN_PRAISE = [
        "いい観点", "いい質問", "さすが", "鋭い", "おっしゃる通り",
        "その通り", "素晴らしい", "お見事", "よく気づ", "正解です",
        "大正解", "正解", "すごい", "完璧", "天才",
    ]

    def test_ayu_forbidden_words_count(self):
        """あゆの禁止ワードが16個以上あること"""
        assert len(AYU_CONFIG.forbidden_words) >= 16, (
            f"あゆの禁止ワードは16個以上必要: 現在{len(AYU_CONFIG.forbidden_words)}個"
        )

    def test_ayu_has_required_praise_words(self):
        """あゆに必須の禁止褒め言葉が含まれること"""
        missing = []
        for word in self.REQUIRED_AYU_FORBIDDEN_PRAISE:
            if not any(word in fw for fw in AYU_CONFIG.forbidden_words):
                missing.append(word)
        assert not missing, f"あゆの禁止ワードに不足: {missing}"

    def test_yana_forbidden_words_count(self):
        """やなの禁止ワードが適切に定義されていること"""
        assert len(YANA_CONFIG.forbidden_words) >= 5, (
            f"やなの禁止ワードは5個以上必要: 現在{len(YANA_CONFIG.forbidden_words)}個"
        )

    def test_simple_uses_all_forbidden_words(self):
        """Simpleビルダーが全禁止ワードを使用すること（[:4]でカットされない）"""
        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        # 末尾付近のワードが含まれていることを確認
        assert "完璧" in prompt, "禁止ワードが[:4]でカットされている可能性"

    def test_layered_uses_all_forbidden_words(self):
        """Layeredビルダーが全禁止ワードを使用すること"""
        builder = LayeredPromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        assert "完璧" in prompt, "禁止ワードが[:4]でカットされている可能性"

    def test_sillytavern_includes_forbidden_words(self):
        """SillyTavernビルダーが禁止ワードをサポートすること"""
        builder = SillyTavernPromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        assert "禁止" in prompt or "使用禁止" in prompt, (
            "SillyTavernに禁止ワードセクションがない"
        )


# ========== Issue 2: Interaction Rulesテスト ==========

class TestInteractionRules:
    """対話ルール（調和的対立）のテスト"""

    def test_ayu_config_has_interaction_rules(self):
        """あゆにinteraction_rulesフィールドが存在すること"""
        assert hasattr(AYU_CONFIG, 'interaction_rules'), (
            "AYU_CONFIGにinteraction_rulesフィールドがない"
        )
        assert AYU_CONFIG.interaction_rules is not None, (
            "AYU_CONFIG.interaction_rulesがNone"
        )

    def test_yana_interaction_rules_is_none(self):
        """やなにはinteraction_rulesがない（あゆ専用機能）"""
        # やなはinteraction_rulesを持たないか、Noneであるべき
        if hasattr(YANA_CONFIG, 'interaction_rules'):
            assert YANA_CONFIG.interaction_rules is None, (
                "やなにinteraction_rulesは不要"
            )

    def test_criticism_guidelines_count(self):
        """批判ガイドラインが5つあること"""
        rules = AYU_CONFIG.interaction_rules
        assert len(rules.criticism_guidelines) == 5, (
            f"批判ガイドラインは5つ必要: 現在{len(rules.criticism_guidelines)}個"
        )

    def test_criticism_guidelines_content(self):
        """批判ガイドラインに必須内容が含まれること"""
        rules = AYU_CONFIG.interaction_rules
        guidelines_text = " ".join(rules.criticism_guidelines)
        required_concepts = ["代替案", "否定", "認め", "呆れ"]
        for concept in required_concepts:
            assert concept in guidelines_text, (
                f"批判ガイドラインに「{concept}」の概念が不足"
            )

    def test_ng_examples_count(self):
        """NGパターンが3つあること"""
        rules = AYU_CONFIG.interaction_rules
        assert len(rules.ng_examples) == 3, (
            f"NGパターンは3つ必要: 現在{len(rules.ng_examples)}個"
        )

    def test_ng_examples_structure(self):
        """NGパターンが(パターン名, 悪い例)のタプルであること"""
        rules = AYU_CONFIG.interaction_rules
        for item in rules.ng_examples:
            assert isinstance(item, tuple), "NGパターンはタプルであるべき"
            assert len(item) == 2, "NGパターンは(パターン名, 悪い例)の2要素"
            assert isinstance(item[0], str), "パターン名は文字列"
            assert isinstance(item[1], str), "悪い例は文字列"

    def test_ok_examples_count(self):
        """OKパターンが3つあること"""
        rules = AYU_CONFIG.interaction_rules
        assert len(rules.ok_examples) == 3, (
            f"OKパターンは3つ必要: 現在{len(rules.ok_examples)}個"
        )

    def test_ok_examples_structure(self):
        """OKパターンが(パターン名, 良い例)のタプルであること"""
        rules = AYU_CONFIG.interaction_rules
        for item in rules.ok_examples:
            assert isinstance(item, tuple), "OKパターンはタプルであるべき"
            assert len(item) == 2, "OKパターンは(パターン名, 良い例)の2要素"
            assert isinstance(item[0], str), "パターン名は文字列"
            assert isinstance(item[1], str), "良い例は文字列"

    def test_simple_includes_interaction_rules_for_ayu(self):
        """Simpleビルダーがあゆにinteraction_rulesを含めること"""
        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("あゆ")
        # 対話ルールのセクションが存在することを確認
        assert "対話ルール" in prompt or "批判ガイドライン" in prompt, (
            "あゆのSimpleプロンプトに対話ルールがない"
        )

    def test_simple_no_interaction_rules_for_yana(self):
        """Simpleビルダーがやなにはinteraction_rulesを含めないこと"""
        builder = SimplePromptBuilder()
        prompt = builder.build_system_prompt("やな")
        # やなには対話ルールセクションがない（あゆ専用）
        assert "批判ガイドライン" not in prompt, (
            "やなに批判ガイドラインは不要"
        )


# ========== Issue 3: 状態別Few-shotテスト ==========

class TestStateBasedFewShot:
    """状態別Few-shotパターンのテスト"""

    YANA_REQUIRED_STATES = ["excited", "confident", "worried", "impatient", "focused", "curious"]
    AYU_REQUIRED_STATES = ["skeptical", "analytical", "concerned", "supportive", "proud", "focused"]

    def test_yana_has_states(self):
        """やなにstates定義があること"""
        assert hasattr(YANA_CONFIG, 'states'), (
            "YANA_CONFIGにstatesフィールドがない"
        )
        assert YANA_CONFIG.states is not None, "YANA_CONFIG.statesがNone"
        assert len(YANA_CONFIG.states) >= 6, (
            f"やなの状態は6つ以上必要: 現在{len(YANA_CONFIG.states)}個"
        )

    def test_ayu_has_states(self):
        """あゆにstates定義があること"""
        assert hasattr(AYU_CONFIG, 'states'), (
            "AYU_CONFIGにstatesフィールドがない"
        )
        assert AYU_CONFIG.states is not None, "AYU_CONFIG.statesがNone"
        assert len(AYU_CONFIG.states) >= 6, (
            f"あゆの状態は6つ以上必要: 現在{len(AYU_CONFIG.states)}個"
        )

    def test_yana_required_states(self):
        """やなに必要な状態が全てあること"""
        state_names = [s.name for s in YANA_CONFIG.states]
        missing = [s for s in self.YANA_REQUIRED_STATES if s not in state_names]
        assert not missing, f"やなに状態が不足: {missing}"

    def test_ayu_required_states(self):
        """あゆに必要な状態が全てあること"""
        state_names = [s.name for s in AYU_CONFIG.states]
        missing = [s for s in self.AYU_REQUIRED_STATES if s not in state_names]
        assert not missing, f"あゆに状態が不足: {missing}"

    def test_each_state_has_examples(self):
        """各状態に2-4個の例があること"""
        all_states = YANA_CONFIG.states + AYU_CONFIG.states
        for state in all_states:
            assert 2 <= len(state.examples) <= 4, (
                f"状態'{state.name}'の例は2-4個必要: 現在{len(state.examples)}個"
            )

    def test_state_has_triggers(self):
        """各状態にトリガーキーワードがあること"""
        all_states = YANA_CONFIG.states + AYU_CONFIG.states
        for state in all_states:
            assert hasattr(state, 'triggers'), (
                f"状態'{state.name}'にtriggersがない"
            )
            assert len(state.triggers) >= 1, (
                f"状態'{state.name}'のトリガーが空"
            )


# ========== 統合テスト ==========

class TestPromptBuilderIntegration:
    """プロンプトビルダーの統合テスト"""

    def test_all_builders_generate_valid_prompts_for_yana(self):
        """全ビルダーがやなに有効なプロンプトを生成すること"""
        builders = [
            SimplePromptBuilder(),
            LayeredPromptBuilder(),
            SillyTavernPromptBuilder(),
        ]
        for builder in builders:
            prompt = builder.build_system_prompt("やな")
            assert len(prompt) > 100, f"{type(builder).__name__}のプロンプトが短すぎる"
            assert "やな" in prompt, f"{type(builder).__name__}にやなが含まれない"

    def test_all_builders_generate_valid_prompts_for_ayu(self):
        """全ビルダーがあゆに有効なプロンプトを生成すること"""
        builders = [
            SimplePromptBuilder(),
            LayeredPromptBuilder(),
            SillyTavernPromptBuilder(),
        ]
        for builder in builders:
            prompt = builder.build_system_prompt("あゆ")
            assert len(prompt) > 100, f"{type(builder).__name__}のプロンプトが短すぎる"
            assert "あゆ" in prompt, f"{type(builder).__name__}にあゆが含まれない"

    def test_prompt_lengths_reasonable(self):
        """プロンプト長が適切な範囲内であること"""
        builder = SimplePromptBuilder()
        for speaker in ["やな", "あゆ"]:
            prompt = builder.build_system_prompt(speaker)
            assert len(prompt) < 5000, (
                f"{speaker}のプロンプトが長すぎる: {len(prompt)}文字"
            )

    def test_dialogue_prompt_includes_history(self):
        """対話プロンプトに履歴が含まれること"""
        builder = SimplePromptBuilder()
        history = [
            {"speaker": "やな", "content": "今日は天気いいね！"},
            {"speaker": "あゆ", "content": "そうですね、洗濯日和です。"},
        ]
        prompt = builder.build_dialogue_prompt(
            speaker="やな",
            topic="今日の予定",
            history=history,
        )
        assert "天気いいね" in prompt, "履歴が含まれていない"
        assert "洗濯日和" in prompt, "履歴が含まれていない"


# ========== CharacterConfigテスト ==========

class TestCharacterConfig:
    """CharacterConfigの基本テスト"""

    def test_yana_basic_config(self):
        """やなの基本設定が正しいこと"""
        assert YANA_CONFIG.name == "やな"
        assert YANA_CONFIG.callname_other == "あゆ"
        assert YANA_CONFIG.speech_register == "casual"

    def test_ayu_basic_config(self):
        """あゆの基本設定が正しいこと"""
        assert AYU_CONFIG.name == "あゆ"
        assert AYU_CONFIG.callname_other == "姉様"
        assert AYU_CONFIG.speech_register == "polite"

    def test_configs_have_few_shot_examples(self):
        """両キャラにfew_shot_examplesがあること"""
        assert len(YANA_CONFIG.few_shot_examples) >= 3
        assert len(AYU_CONFIG.few_shot_examples) >= 3
