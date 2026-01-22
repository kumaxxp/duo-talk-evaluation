"""v3.7 Direct Dialogue Enforcement テスト

v3.7の核心コンセプト: 「名前を出力させない（発言内容のみ出力）」
- Prompt: Few-shot例から名前表記を削除、`Output: 「...」` 形式に統一
- Implementation: Output強制時のPrefillを `\nOutput: 「` に変更

参照: docs/キャラクター設定プロンプト v3.7 改良案gemini.md
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


class TestV37PrefillPattern:
    """v3.7 Prefillパターンのテスト

    v3.7の核心: Output強制時に `Output: 「` までPrefillし、
    モデルが名前を書く余地をなくす。
    """

    def test_output_prefill_includes_opening_bracket(self):
        """Output強制時のPrefillに開きカッコが含まれること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        # v3.7: Output強制時のPrefill文字列を取得
        prefill = adapter._get_v37_output_prefill()
        assert "Output:" in prefill
        assert "「" in prefill

    def test_thought_prefill_unchanged(self):
        """Thought開始時のPrefillはv3.6と同じ"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        prefill = adapter._get_v37_thought_prefill()
        assert prefill == "Thought:"


class TestV37StopSequences:
    """v3.7 Stop Sequenceのテスト

    v3.7の変更点:
    - Thought生成: "Output", "Output:", "\nOutput" で停止
    - Dialogue生成: "」", "\n" で停止
    """

    def test_thought_stop_sequences(self):
        """Thought生成用のstop sequenceが正しいこと"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        stop_sequences = adapter._get_v37_thought_stop_sequences()
        assert "Output" in stop_sequences
        assert "Output:" in stop_sequences
        assert "\nOutput" in stop_sequences

    def test_dialogue_stop_sequences(self):
        """Dialogue生成用のstop sequenceが正しいこと"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        stop_sequences = adapter._get_v37_dialogue_stop_sequences()
        assert "」" in stop_sequences
        assert "\n" in stop_sequences

    def test_stop_sequences_used_in_thought_generation(self):
        """Thought生成でstop sequenceが正しく使用されること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        with patch.object(adapter, '_call_ollama_api') as mock_api:
            mock_api.side_effect = ["面白そう！", "いいじゃん！"]
            adapter._generate_with_v37_flow("Test prompt")

            # 1回目のAPIコールでThought用stop sequenceが渡されていること
            first_call_args = mock_api.call_args_list[0]
            stop_sequences = first_call_args[1].get("stop", [])
            assert "Output" in stop_sequences or "Output:" in stop_sequences

    def test_stop_sequences_used_in_dialogue_generation(self):
        """Dialogue生成でstop sequenceが正しく使用されること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        with patch.object(adapter, '_call_ollama_api') as mock_api:
            mock_api.side_effect = ["面白そう！", "いいじゃん！"]
            adapter._generate_with_v37_flow("Test prompt")

            # 2回目のAPIコールでDialogue用stop sequenceが渡されていること
            second_call_args = mock_api.call_args_list[1]
            stop_sequences = second_call_args[1].get("stop", [])
            assert "」" in stop_sequences


class TestV37ClosingBracket:
    """閉じカッコ補完のテスト

    v3.7: 閉じカッコがなければ補完する
    """

    def test_closing_bracket_added_when_missing(self):
        """閉じカッコがなければ補完されること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        # 閉じカッコがない場合
        response = adapter._ensure_closing_bracket("いいじゃん！")
        assert response.endswith("」")

    def test_closing_bracket_not_duplicated(self):
        """閉じカッコが既にある場合は重複しないこと"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        # 閉じカッコがある場合
        response = adapter._ensure_closing_bracket("いいじゃん！」")
        assert response == "いいじゃん！」"
        assert not response.endswith("」」")


class TestV37FullFlow:
    """v3.7フルフローのテスト"""

    def test_full_flow_produces_dialogue_content(self):
        """v3.7フローが対話内容を生成すること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        with patch.object(adapter, '_call_ollama_api') as mock_api:
            # Thought生成 → Dialogue生成
            mock_api.side_effect = [
                "(Yana: やった！もっとパワーアップだ！)",
                "いいじゃんいいじゃん！あゆちゃん、あとはよろしく！",
            ]
            result = adapter._generate_with_v37_flow("GPUをもう一枚買おう！")

            # Thoughtを含む
            assert "Thought:" in result
            # Outputを含む
            assert "Output:" in result
            # 開きカッコを含む
            assert "「" in result
            # 対話内容を含む
            assert "いいじゃん" in result

    def test_full_flow_does_not_include_character_name_in_output(self):
        """v3.7フローでOutputにキャラクター名が含まれないこと"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        with patch.object(adapter, '_call_ollama_api') as mock_api:
            mock_api.side_effect = [
                "(Ayu: また姉様が…。)",
                "姉様、正気ですか？",
            ]
            result = adapter._generate_with_v37_flow("GPUをもう一枚買おう！")

            # Outputの後に「澄ヶ瀬」が来ないこと
            output_part = result.split("Output:")[1] if "Output:" in result else ""
            # Output:の直後が「「」で始まること
            output_stripped = output_part.strip()
            assert output_stripped.startswith("「")


class TestV37PromptBuilder:
    """v3.7プロンプトビルダーのテスト"""

    def test_few_shot_examples_no_character_names(self):
        """Few-shot例にキャラクター名が含まれないこと"""
        from experiments.ab_test.prompts.json_v37 import JSONV37PromptBuilder

        builder = JSONV37PromptBuilder()
        prompt = builder.build_system_prompt("やな")

        # Few-shot例の部分を確認
        # Output:の直後に「澄ヶ瀬」がないこと
        lines = prompt.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("Output:"):
                # Output:の次が「「」で始まるか確認
                output_content = line.replace("Output:", "").strip()
                if output_content:
                    assert output_content.startswith("「"), f"Output should start with 「: {output_content}"

    def test_few_shot_format_is_bracket_style(self):
        """Few-shot例が「...」形式であること"""
        from experiments.ab_test.prompts.json_v37 import JSONV37PromptBuilder

        builder = JSONV37PromptBuilder()
        prompt = builder.build_system_prompt("やな")

        # Output:の後に「...」形式があること
        assert "Output: 「" in prompt

    def test_conversation_rule_includes_format_instruction(self):
        """conversation_ruleにformat指示が含まれること"""
        from experiments.ab_test.prompts.json_v37 import JSONV37PromptBuilder

        builder = JSONV37PromptBuilder()
        prompt = builder.build_system_prompt("やな")

        # format指示が含まれること
        assert "「" in prompt
        assert "Do NOT write character names" in prompt or "名前" in prompt


class TestV37Config:
    """v3.7設定のテスト"""

    def test_use_v37_flow_option_exists(self):
        """use_v37_flowオプションが存在すること"""
        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        assert hasattr(variation, 'use_v37_flow')
        assert variation.use_v37_flow is True

    def test_v37_adapter_uses_v37_flow(self):
        """V37ConfigurableAdapterがv3.7フローを使用すること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        assert adapter._should_use_v37_flow() is True


class TestV37ResponseParsing:
    """v3.7レスポンスパースのテスト"""

    def test_parse_thought_and_dialogue(self):
        """ThoughtとDialogueを正しくパースすること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        response = "Thought: (Yana: 面白そう！)\nOutput: 「いいじゃんいいじゃん！」"
        thought, dialogue = adapter._parse_v37_response(response)

        assert "面白そう" in thought
        assert "いいじゃん" in dialogue

    def test_parse_extracts_dialogue_without_brackets(self):
        """Dialogueからカッコを除いた内容を取得できること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        response = "Thought: (Ayu: 姉様…)\nOutput: 「姉様、正気ですか？」"
        thought, dialogue = adapter._parse_v37_response(response)

        # dialogueにカッコが含まれていても良いが、内容を正しく取得できること
        assert "正気ですか" in dialogue


class TestV37Integration:
    """v3.7統合テスト"""

    def test_adapter_creates_v37_prompt_builder(self):
        """V37ConfigurableAdapterがJSONV37PromptBuilderを使用すること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter
        from experiments.ab_test.prompts.json_v37 import JSONV37PromptBuilder

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        assert isinstance(adapter.prompt_builder, JSONV37PromptBuilder)

    def test_generate_dialogue_uses_v37_flow(self):
        """generate_dialogueがv3.7フローを使用すること"""
        from experiments.ab_test.adapters.v37_adapter import V37ConfigurableAdapter

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v37_flow=True,
        )
        adapter = V37ConfigurableAdapter(variation)

        with patch.object(adapter, 'is_available', return_value=True):
            with patch.object(adapter, '_generate_with_v37_flow') as mock_flow:
                mock_flow.return_value = "Thought: (test)\nOutput: 「テスト」"
                adapter.generate_dialogue("テスト", turns=1)
                mock_flow.assert_called()
