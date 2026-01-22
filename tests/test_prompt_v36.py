"""v3.6プロンプト改良テスト

v3.6の主な変更点:
1. **System-Assisted Output Enforcement**: プロンプトだけでなく実装で発話を強制
2. **Prefill Pattern**: Assistant messageに "Thought:" を事前入力
3. **Stop Sequence + Continue**: "Output:" で止め、なければ追記して継続
4. **Simplified Prompt**: 複雑な命令は実装側で担保するためシンプル化

参照: docs/キャラクター設定プロンプト v3.6 改良案gemini.md
"""

import pytest
from unittest.mock import MagicMock, patch

# v3.6 imports will be created
# from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder
# from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter


class TestV36PrefillPattern:
    """Prefillパターンのテスト（v3.6）

    Assistant messageに "Thought:" を事前入力し、
    モデルを強制的に思考モードから開始させる。
    """

    def test_prefill_adds_thought_prefix(self):
        """Prefillが "Thought:" を追加すること"""
        # V36ConfigurableAdapterがprefillを追加することをテスト
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        # _build_messages_with_prefill メソッドをテスト
        messages = adapter._build_messages_with_prefill(
            system_prompt="Test system prompt",
            history=[{"speaker": "user", "content": "Hello"}],
        )

        # 最後のメッセージがassistantで "Thought:" で始まること
        assert messages[-1]["role"] == "assistant"
        assert messages[-1]["content"] == "Thought:"

    def test_prefill_works_with_empty_history(self):
        """空の履歴でもPrefillが動作すること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        messages = adapter._build_messages_with_prefill(
            system_prompt="Test system prompt",
            history=[],
        )

        # system + assistant(prefill) の2つ
        assert len(messages) >= 2
        assert messages[-1]["role"] == "assistant"
        assert messages[-1]["content"] == "Thought:"


class TestV36StopSequence:
    """Stop Sequenceのテスト（v3.6）

    "Output:" をstop sequenceとして使用し、
    Thoughtパートの終了を検出する。
    """

    def test_stop_sequence_includes_output(self):
        """stop sequenceに "Output:" が含まれること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        stop_sequences = adapter._get_v36_stop_sequences()
        assert "Output:" in stop_sequences

    def test_stop_sequence_is_used_in_first_generation(self):
        """最初の生成でstop sequenceが使用されること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        # _generate_with_v36_flow内でstop sequenceが使用されることを確認
        # 実際のAPIコールはモック（2回呼ばれる）
        with patch.object(adapter, '_call_ollama_api') as mock_api:
            mock_api.side_effect = ["面白そう！", "やな: 「いいじゃん！」"]
            adapter._generate_with_v36_flow("Test prompt")

            # 1回目のAPIコールでstop sequenceが渡されていること
            first_call_args = mock_api.call_args_list[0]
            assert "Output:" in first_call_args[1].get("stop", [])


class TestV36ContinueGeneration:
    """Continue Generationのテスト（v3.6）

    Thoughtだけで止まった場合に "\nOutput:" を追記し、
    続きを生成させる。
    """

    def test_continue_generation_when_output_missing(self):
        """Output:がない場合に継続生成すること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        # Thoughtのみの応答をシミュレート
        thought_only = "面白そう！やってみたい。"

        # _needs_continue_generation メソッドのテスト
        assert adapter._needs_continue_generation(thought_only) is True

    def test_no_continue_generation_when_output_exists(self):
        """Output:がある場合は継続生成しないこと"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        # Output:を含む応答
        with_output = "面白そう！\nOutput: やな: 「いいじゃん！」"

        assert adapter._needs_continue_generation(with_output) is False

    def test_continue_generation_appends_output_marker(self):
        """継続生成時に "\nOutput:" が追記されること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        thought_content = "面白そう！やってみたい。"
        continued_content = adapter._prepare_continue_content(thought_content)

        assert continued_content.endswith("\nOutput:")

    def test_full_v36_flow_produces_output(self):
        """v3.6フロー全体でOutput:が含まれる応答を生成すること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        # 2回のAPIコールをシミュレート
        # 1回目: Thoughtのみ
        # 2回目: Outputの内容
        with patch.object(adapter, '_call_ollama_api') as mock_api:
            mock_api.side_effect = [
                "面白そう！やってみたい。",  # 1st call: Thought only
                "やな: 「いいじゃん！やってみようよ！」",  # 2nd call: Output content
            ]

            result = adapter._generate_with_v36_flow("Test prompt")

            # 結果にThoughtとOutput両方が含まれること
            assert "Thought:" in result
            assert "Output:" in result
            # APIが2回呼ばれること（1回目+継続生成）
            assert mock_api.call_count == 2


class TestV36SimplifiedPrompt:
    """簡素化されたプロンプトのテスト（v3.6）

    v3.5の複雑な命令を削除し、シンプルなJSON構造を使用。
    実装側で担保するため、プロンプトは最小限に。
    """

    def test_v36_prompt_builder_exists(self):
        """v3.6用のプロンプトビルダーが存在すること"""
        from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder
        assert JSONV36PromptBuilder is not None

    def test_v36_prompt_is_simpler(self):
        """v3.6プロンプトがv3.5より簡素化されていること"""
        from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder
        from experiments.ab_test.prompts.json_prompt import JSONPromptBuilder

        v35_builder = JSONPromptBuilder(max_sentences=3, few_shot_count=3)
        v36_builder = JSONV36PromptBuilder(max_sentences=3, few_shot_count=3)

        v35_prompt = v35_builder.build_system_prompt("やな")
        v36_prompt = v36_builder.build_system_prompt("やな")

        # v3.6はv3.5より短い（CRITICAL INSTRUCTIONなど削除）
        assert len(v36_prompt) < len(v35_prompt)

    def test_v36_prompt_has_no_critical_instruction(self):
        """v3.6プロンプトにCRITICAL INSTRUCTIONがないこと"""
        from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder

        builder = JSONV36PromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")

        # v3.5で追加されたCRITICAL INSTRUCTIONは不要
        assert "CRITICAL INSTRUCTION" not in prompt

    def test_v36_prompt_has_simplified_json_structure(self):
        """v3.6プロンプトがシンプルなJSON構造を持つこと"""
        from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder

        builder = JSONV36PromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")

        # 必須要素のみ含む
        assert "instruction" in prompt or "characters" in prompt
        assert "world_context" in prompt or "project" in prompt
        assert "conversation_rule" in prompt or "Zero Distance" in prompt

    def test_v36_prompt_includes_both_characters(self):
        """v3.6プロンプトに両キャラクターの定義が含まれること"""
        from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder

        builder = JSONV36PromptBuilder(max_sentences=3, few_shot_count=3)

        # 両キャラのプロンプトで相手の情報も含む
        yana_prompt = builder.build_system_prompt("やな")
        ayu_prompt = builder.build_system_prompt("あゆ")

        assert "やな" in yana_prompt and "あゆ" in yana_prompt
        assert "やな" in ayu_prompt and "あゆ" in ayu_prompt

    def test_v36_prompt_has_thought_pattern(self):
        """v3.6プロンプトにthought_patternが含まれること"""
        from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder

        builder = JSONV36PromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")

        assert "thought_pattern" in prompt or "主観" in prompt


class TestV36FewShotFormat:
    """v3.6 Few-shot形式のテスト

    Thought + Output形式を維持。
    """

    def test_v36_fewshot_has_thought_and_output(self):
        """Few-shotサンプルがThoughtとOutput両方を含むこと"""
        from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder

        builder = JSONV36PromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")

        assert "Thought:" in prompt
        assert "Output:" in prompt

    def test_v36_fewshot_output_format(self):
        """Few-shotのOutput形式が正しいこと"""
        from experiments.ab_test.prompts.json_v36 import JSONV36PromptBuilder

        builder = JSONV36PromptBuilder(max_sentences=3, few_shot_count=3)
        prompt = builder.build_system_prompt("やな")

        # Output: キャラ名: 「発話」形式
        assert "「" in prompt and "」" in prompt


class TestV36BackwardsCompatibility:
    """v3.6後方互換性テスト"""

    def test_v36_adapter_can_fallback_to_v35(self):
        """v3.6アダプタがv3.5フォールバック可能であること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v36_flow=False,  # v3.6フローを無効化
        )
        adapter = V36ConfigurableAdapter(variation)

        # v3.6フロー無効時は通常の生成を使用
        assert adapter._should_use_v36_flow() is False

    def test_v36_config_has_use_v36_flow_option(self):
        """VariationConfigにuse_v36_flowオプションがあること"""
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v36_flow=True,
        )

        assert hasattr(variation, 'use_v36_flow')
        assert variation.use_v36_flow is True


class TestV36Integration:
    """v3.6統合テスト"""

    def test_v36_generates_complete_response(self):
        """v3.6が完全な応答（Thought + Output）を生成すること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
            use_v36_flow=True,
        )
        adapter = V36ConfigurableAdapter(variation)

        with patch.object(adapter, '_call_ollama_api') as mock_api:
            # 正常な応答をシミュレート
            mock_api.return_value = "面白そう！やってみたい。"

            result = adapter._generate_with_v36_flow("Test prompt")

            # 結果にThoughtとOutput両方が含まれること
            assert "Thought:" in result
            assert "Output:" in result

    def test_v36_result_parsing(self):
        """v3.6の結果をThought/Outputに分離できること"""
        from experiments.ab_test.adapters.v36_adapter import V36ConfigurableAdapter
        from experiments.ab_test.config import VariationConfig, LLMBackend, PromptStructure

        variation = VariationConfig(
            name="test",
            llm_backend=LLMBackend.OLLAMA,
            prompt_structure=PromptStructure.JSON,
        )
        adapter = V36ConfigurableAdapter(variation)

        response = "Thought: 面白そう！\nOutput: やな: 「いいじゃん！」"
        thought, output = adapter._parse_v36_response(response)

        assert "面白そう" in thought
        assert "いいじゃん" in output
