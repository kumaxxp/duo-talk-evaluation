"""v3.2プロンプト改良テスト

v3.2の主な変更点:
1. 知識発動のトリガー制限（文脈判断必須）
2. 口調のゆらぎ（定型句の乱用禁止）
3. 会話の「ノイズ」許容（論理的な結論不要）
"""

import pytest

from experiments.ab_test.prompts.base import (
    YANA_CONFIG,
    AYU_CONFIG,
    CharacterConfig,
)
from experiments.ab_test.prompts.simple import SimplePromptBuilder


class TestV32KnowledgeBiasRestriction:
    """知識発動のトリガー制限テスト（v3.2）"""

    def test_yana_knowledge_bias_has_context_restriction(self):
        """やなの知識の偏りに文脈制限があること"""
        dv = YANA_CONFIG.deep_values
        assert dv.knowledge_bias is not None
        # v3.2: 文脈判断が必須
        assert dv.knowledge_bias.context_restriction is not None
        assert "挨拶" in dv.knowledge_bias.context_restriction or "関係ない" in dv.knowledge_bias.context_restriction

    def test_ayu_knowledge_bias_has_context_restriction(self):
        """あゆの知識の偏りに文脈制限があること"""
        dv = AYU_CONFIG.deep_values
        assert dv.knowledge_bias is not None
        # v3.2: 文脈判断が必須
        assert dv.knowledge_bias.context_restriction is not None
        assert "挨拶" in dv.knowledge_bias.context_restriction or "日常会話" in dv.knowledge_bias.context_restriction

    def test_ayu_knowledge_bias_hidden_tendency(self):
        """あゆのテックオタク面を隠す設定があること"""
        dv = AYU_CONFIG.deep_values
        assert dv.knowledge_bias is not None
        # v3.2: 日常会話ではテックオタクな面を隠そうとする
        assert dv.knowledge_bias.hidden_tendency is not None


class TestV32CatchphraseRestriction:
    """定型句の乱用禁止テスト（v3.2）"""

    def test_yana_has_catchphrase_limit(self):
        """やなに定型句制限があること"""
        dv = YANA_CONFIG.deep_values
        assert dv.catchphrase_rules is not None
        # 「あゆがなんとかしてくれる」は会話全体で1回まで
        assert dv.catchphrase_rules.max_usage is not None
        assert dv.catchphrase_rules.max_usage <= 1

    def test_yana_has_catchphrase_alternatives(self):
        """やなに定型句の言い換えがあること"""
        dv = YANA_CONFIG.deep_values
        assert dv.catchphrase_rules is not None
        # 言い換え例: 「頼んだ！」「あゆなら余裕っしょ」など
        assert len(dv.catchphrase_rules.alternatives) >= 2

    def test_ayu_has_catchphrase_restriction(self):
        """あゆに定型句制限があること"""
        dv = AYU_CONFIG.deep_values
        assert dv.catchphrase_rules is not None
        # 「ちょっと待ってください」を連呼しない
        assert dv.catchphrase_rules.restricted_phrases is not None
        assert "ちょっと待ってください" in dv.catchphrase_rules.restricted_phrases

    def test_ayu_has_catchphrase_alternatives(self):
        """あゆに定型句の言い換えがあること"""
        dv = AYU_CONFIG.deep_values
        assert dv.catchphrase_rules is not None
        # 言い換え例: 「え？」「本気ですか？」「いやいや...」
        assert len(dv.catchphrase_rules.alternatives) >= 3


class TestV32ConversationNoise:
    """会話の「ノイズ」許容テスト（v3.2）"""

    def test_yana_allows_incomplete_turns(self):
        """やなが不完全なターンを許容すること"""
        dv = YANA_CONFIG.deep_values
        assert dv.conversation_style is not None
        # 単なる独り言や感嘆詞だけでターンを終えてもよい
        assert dv.conversation_style.allows_incomplete_turns is True

    def test_ayu_allows_reaction_only(self):
        """あゆがリアクションのみのターンを許容すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.conversation_style is not None
        # 「え、無理ですよ」の一言だけでもよい
        assert dv.conversation_style.allows_reaction_only is True

    def test_ayu_allows_broken_structure(self):
        """あゆが論理構成を崩すことを許容すること"""
        dv = AYU_CONFIG.deep_values
        assert dv.conversation_style is not None
        # 「結論→理由→対策」の順序を守らなくてよい
        assert dv.conversation_style.allows_broken_structure is True


class TestV32SpeechVariation:
    """口調のゆらぎテスト（v3.2）"""

    def test_yana_has_speech_variations(self):
        """やなに口調バリエーションがあること"""
        dv = YANA_CONFIG.deep_values
        assert dv.speech_variations is not None
        # 〜じゃん、〜かも？、〜だしねー、フィラー
        assert len(dv.speech_variations) >= 4

    def test_yana_speech_variations_include_fillers(self):
        """やなの口調バリエーションにフィラーが含まれること"""
        dv = YANA_CONFIG.deep_values
        variations = " ".join(dv.speech_variations)
        # 笑い声や、えー、などのフィラーを含める
        assert "えー" in variations or "フィラー" in variations or "笑い" in variations

    def test_ayu_has_speech_variations(self):
        """あゆに口調バリエーションがあること"""
        dv = AYU_CONFIG.deep_values
        assert dv.speech_variations is not None
        # 〜ですね、〜ですけど...、〜なんです、はぁ...
        assert len(dv.speech_variations) >= 4

    def test_ayu_speech_variations_include_sighs(self):
        """あゆの口調バリエーションにため息が含まれること"""
        dv = AYU_CONFIG.deep_values
        variations = " ".join(dv.speech_variations)
        # はぁ...（ため息）
        assert "はぁ" in variations or "ため息" in variations


class TestV32FewShotExamples:
    """v3.2 Few-shot例テスト"""

    def test_yana_has_natural_examples(self):
        """やなのFew-shot例が自然であること"""
        examples = YANA_CONFIG.few_shot_examples
        # 短文・体言止め・感嘆詞のみの例が含まれる
        short_examples = [ex for ex in examples if len(ex) < 30]
        assert len(short_examples) >= 2

    def test_yana_examples_include_fillers(self):
        """やなのFew-shot例にフィラーが含まれること"""
        examples = " ".join(YANA_CONFIG.few_shot_examples)
        # えー、んー、などのフィラー
        assert "えー" in examples or "んー" in examples or "まじ" in examples

    def test_ayu_has_reaction_examples(self):
        """あゆのFew-shot例にリアクション例があること"""
        examples = YANA_CONFIG.few_shot_examples
        # 「え、無理ですよ」のような短いツッコミ
        short_reactions = [ex for ex in AYU_CONFIG.few_shot_examples if len(ex) < 30]
        assert len(short_reactions) >= 1

    def test_ayu_examples_include_sighs(self):
        """あゆのFew-shot例にため息が含まれること"""
        examples = " ".join(AYU_CONFIG.few_shot_examples)
        # はぁ...
        assert "はぁ" in examples


class TestV32PromptOutput:
    """v3.2プロンプト出力テスト"""

    def test_simple_includes_context_restriction(self):
        """Simpleビルダーが文脈制限を含めること"""
        builder = SimplePromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        # 文脈判断が必須という記載
        assert "文脈" in prompt or "挨拶" in prompt

    def test_simple_includes_catchphrase_limit(self):
        """Simpleビルダーが定型句制限を含めること"""
        builder = SimplePromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        # 乱用禁止の記載
        assert "1回" in prompt or "乱用" in prompt or "連呼" in prompt

    def test_simple_includes_speech_variations(self):
        """Simpleビルダーが口調バリエーションを含めること"""
        builder = SimplePromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")
        # 口調バリエーションの記載
        assert "かも" in prompt or "だしねー" in prompt

    def test_simple_ayu_includes_broken_structure(self):
        """Simpleビルダー（あゆ）が論理構成を崩す許可を含めること"""
        builder = SimplePromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("あゆ")
        # 順序を守らなくてよい、一言だけでもよい等
        assert "順序" in prompt or "一言" in prompt or "リアクション" in prompt
