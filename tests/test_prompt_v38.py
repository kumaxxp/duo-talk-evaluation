"""v3.8 Narrative Restoration テスト

v3.8の核心コンセプト: 「動作描写を許可しつつ、名前は後処理で削除する」
- Prompt: `(Action) 「Dialogue」` 形式を許可、Few-shotに動作描写を追加
- Implementation: Prefillを `Output:` に戻す（動作を書く余地を与える）
- Post-Processing: 名前クリーニングで「澄ヶ瀬やな:」等を削除

参照: docs/キャラクター設定プロンプト v3.8 改良案gemini.md
"""

import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "experiments"))

from experiments.ab_test.config import (
    LLMBackend,
    PromptStructure,
    VariationConfig,
)


class TestV38PrefillPattern:
    """v3.8 Prefillパターンのテスト

    v3.8の特徴: Prefillを `Output:` に戻す（カギカッコなし）
    これにより動作描写 (*sighs* など) を書く余地を与える
    """

    def test_output_prefill_without_bracket(self):
        """Output強制時のPrefillにカギカッコが含まれないこと"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        prefill = adapter._get_v38_output_prefill()
        assert "Output:" in prefill
        assert "「" not in prefill  # v3.7との違い: カギカッコなし

    def test_thought_prefill_unchanged(self):
        """Thought開始時のPrefillはv3.6/v3.7と同じ"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        prefill = adapter._get_v38_thought_prefill()
        assert prefill == "Thought:"


class TestV38NameCleaning:
    """v3.8 名前クリーニングのテスト

    v3.8の核心: モデルが出力した名前を後処理で削除する
    """

    def test_clean_full_name_with_colon(self):
        """「澄ヶ瀬やな:」を削除できること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        text = "澄ヶ瀬やな: 「いいじゃんいいじゃん！」"
        cleaned = adapter._clean_character_name(text)
        assert "澄ヶ瀬" not in cleaned
        assert "やな" not in cleaned
        assert "いいじゃん" in cleaned

    def test_clean_short_name_with_colon(self):
        """「やな:」を削除できること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        text = "やな: 「いいじゃんいいじゃん！」"
        cleaned = adapter._clean_character_name(text)
        assert "やな:" not in cleaned
        assert "いいじゃん" in cleaned

    def test_clean_ayu_name(self):
        """「澄ヶ瀬あゆ:」を削除できること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        text = "澄ヶ瀬あゆ: 「姉様、正気ですか？」"
        cleaned = adapter._clean_character_name(text)
        assert "澄ヶ瀬" not in cleaned
        assert "あゆ" not in cleaned
        assert "正気ですか" in cleaned

    def test_clean_surname_only(self):
        """「澄ヶ瀬」のみを削除できること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        text = "澄ヶ瀬 「いいじゃん！」"
        cleaned = adapter._clean_character_name(text)
        assert "澄ヶ瀬" not in cleaned
        assert "いいじゃん" in cleaned

    def test_preserve_action_asterisk(self):
        """動作描写 *sighs* を保持すること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        text = "*呆れたようにため息をついて* 「姉様、正気ですか？」"
        cleaned = adapter._clean_character_name(text)
        assert "*呆れたようにため息をついて*" in cleaned
        assert "正気ですか" in cleaned

    def test_preserve_action_parenthesis(self):
        """動作描写 (ガッツポーズして) を保持すること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        text = "(ガッツポーズをして) 「やったーー！」"
        cleaned = adapter._clean_character_name(text)
        assert "(ガッツポーズをして)" in cleaned
        assert "やったーー" in cleaned

    def test_clean_name_with_action(self):
        """名前を削除しつつ動作を保持すること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        # 名前の後に動作がある場合
        text = "澄ヶ瀬やな: *笑いながら* 「いいじゃん！」"
        cleaned = adapter._clean_character_name(text)
        assert "澄ヶ瀬" not in cleaned
        assert "*笑いながら*" in cleaned
        assert "いいじゃん" in cleaned


class TestV38StopSequences:
    """v3.8 Stop Sequenceのテスト

    v3.8: より緩やかなstop sequenceで動作描写を許可
    """

    def test_dialogue_stop_sequences(self):
        """Dialogue生成用のstop sequenceが正しいこと"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        stop_sequences = adapter._get_v38_dialogue_stop_sequences()
        # v3.7の「」」で止める方式ではなく、より緩やか
        assert "\nUser:" in stop_sequences or "User:" in stop_sequences


class TestV38PromptBuilder:
    """v3.8プロンプトビルダーのテスト"""

    def test_few_shot_includes_action(self):
        """Few-shot例に動作描写が含まれること"""
        from experiments.ab_test.prompts.json_v38 import JSONV38PromptBuilder

        builder = JSONV38PromptBuilder()
        prompt = builder.build_system_prompt("やな")

        # 動作描写（*asterisks* or (parentheses)）が含まれること
        assert "*" in prompt or "(" in prompt

    def test_conversation_rule_includes_action_format(self):
        """conversation_ruleに動作形式の説明が含まれること"""
        from experiments.ab_test.prompts.json_v38 import JSONV38PromptBuilder

        builder = JSONV38PromptBuilder()
        prompt = builder.build_system_prompt("やな")

        # actions指示が含まれること
        assert "Action" in prompt or "action" in prompt or "動作" in prompt


class TestV38Config:
    """v3.8設定のテスト"""

    def test_use_v38_flow_option_exists(self):
        """use_v38_flowオプションが存在すること"""
        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        assert hasattr(variation, 'use_v38_flow')
        assert variation.use_v38_flow is True

    def test_v38_adapter_uses_v38_flow(self):
        """V38ConfigurableAdapterがv3.8フローを使用すること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        assert adapter._should_use_v38_flow() is True


class TestV38FullFlow:
    """v3.8フルフローのテスト"""

    def test_full_flow_with_clean_output(self):
        """v3.8フローが名前をクリーニングして出力すること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        with patch.object(adapter, '_call_ollama_api') as mock_api:
            # Thought生成 → Dialogue生成（名前含む）
            mock_api.side_effect = [
                "(Yana: やった！)",
                "澄ヶ瀬やな: *ガッツポーズして* 「いいじゃんいいじゃん！」",
            ]
            result = adapter._generate_with_v38_flow("GPUをもう一枚買おう！")

            # 名前がクリーニングされていること
            assert "澄ヶ瀬" not in result
            # 動作は保持されること
            assert "*ガッツポーズして*" in result or "ガッツポーズ" in result
            # 対話内容は保持されること
            assert "いいじゃん" in result

    def test_full_flow_preserves_action_only_output(self):
        """動作のみの出力が正しく処理されること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        with patch.object(adapter, '_call_ollama_api') as mock_api:
            mock_api.side_effect = [
                "(Ayu: また姉様が…)",
                "*呆れたようにため息をついて* 「姉様、正気ですか？」",
            ]
            result = adapter._generate_with_v38_flow("GPUをもう一枚買おう！")

            # 動作と対話が両方保持されること
            assert "ため息" in result or "*" in result
            assert "正気ですか" in result


class TestV38Integration:
    """v3.8統合テスト"""

    def test_adapter_creates_v38_prompt_builder(self):
        """V38ConfigurableAdapterがJSONV38PromptBuilderを使用すること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter
        from experiments.ab_test.prompts.json_v38 import JSONV38PromptBuilder

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        assert isinstance(adapter.prompt_builder, JSONV38PromptBuilder)

    def test_generate_dialogue_uses_v38_flow(self):
        """generate_dialogueがv3.8フローを使用すること"""
        from experiments.ab_test.adapters.v38_adapter import V38ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v38_flow=True,
        )
        adapter = V38ConfigurableAdapter(variation)

        with patch.object(adapter, 'is_available', return_value=True):
            with patch.object(adapter, '_generate_with_v38_flow') as mock_flow:
                mock_flow.return_value = "Thought: (test)\nOutput: *笑って* 「テスト」"
                adapter.generate_dialogue("テスト", turns=1)
                mock_flow.assert_called()
