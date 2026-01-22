"""実験設定の定義"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class LLMBackend(Enum):
    """LLMバックエンドの種類"""
    OLLAMA = "ollama"
    KOBOLDCPP = "koboldcpp"


class PromptStructure(Enum):
    """プロンプト構造の種類"""
    LAYERED = "layered"      # duo-talk方式 (XML階層)
    SIMPLE = "simple"        # duo-talk-simple方式
    SILLYTAVERN = "sillytavern"  # SillyTavern形式
    JSON = "json"            # v3.3 JSON Schema形式


@dataclass
class VariationConfig:
    """バリエーション設定"""
    name: str
    llm_backend: LLMBackend = LLMBackend.OLLAMA
    llm_model: str = "swallow-8b"
    prompt_structure: PromptStructure = PromptStructure.SIMPLE
    rag_enabled: bool = False
    director_enabled: bool = False
    few_shot_count: int = 3
    max_sentences: int = 3
    temperature: float = 0.7

    # KoboldCPP固有設定
    kobold_url: str = "http://localhost:5001"

    # Ollama固有設定
    ollama_url: str = "http://localhost:11434/v1"
    ollama_model: str = "hf.co/mmnga/tokyotech-llm-Llama-3.1-Swallow-8B-Instruct-v0.3-gguf:Q4_K_M"

    # v3.6 System-Assisted Output Enforcement
    use_v36_flow: bool = False  # Prefill + Continue Generation を有効化

    # v3.7 Direct Dialogue Enforcement
    use_v37_flow: bool = False  # Output: 「 までPrefill、名前を書かせない


@dataclass
class ScenarioConfig:
    """シナリオ設定"""
    name: str
    initial_prompt: str
    turns: int
    evaluation_focus: list[str] = field(default_factory=list)


@dataclass
class ExperimentConfig:
    """実験全体の設定"""
    experiment_id: str
    name: str
    description: str
    base_config: dict = field(default_factory=dict)
    variations: list[VariationConfig] = field(default_factory=list)
    scenarios: list[ScenarioConfig] = field(default_factory=list)
    metrics: list[str] = field(default_factory=lambda: [
        "naturalness",
        "character_consistency",
        "concreteness",
        "relationship_quality",
        "topic_novelty",
    ])

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "ExperimentConfig":
        """YAMLファイルから設定を読み込み"""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        experiment = data.get("experiment", {})
        base_config = data.get("base_config", {})

        # バリエーション設定の変換
        variations = []
        for var_data in data.get("variations", []):
            var_config = VariationConfig(
                name=var_data.get("name", "unnamed"),
                llm_backend=LLMBackend(var_data.get("llm_backend", "ollama")),
                llm_model=var_data.get("llm_model", "swallow-8b"),
                prompt_structure=PromptStructure(
                    var_data.get("prompt_structure", base_config.get("prompt_structure", "simple"))
                ),
                rag_enabled=var_data.get("rag_enabled", base_config.get("rag_enabled", False)),
                director_enabled=var_data.get("director_enabled", base_config.get("director_enabled", False)),
                few_shot_count=var_data.get("few_shot_count", base_config.get("few_shot_count", 3)),
                temperature=var_data.get("temperature", 0.7),
                # Ollama固有設定
                ollama_model=var_data.get("ollama_model", base_config.get("ollama_model", "hf.co/mmnga/tokyotech-llm-Llama-3.1-Swallow-8B-Instruct-v0.3-gguf:Q4_K_M")),
                ollama_url=var_data.get("ollama_url", base_config.get("ollama_url", "http://localhost:11434/v1")),
                # KoboldCPP固有設定
                kobold_url=var_data.get("kobold_url", base_config.get("kobold_url", "http://localhost:5001")),
                # v3.6 System-Assisted Output Enforcement
                use_v36_flow=var_data.get("use_v36_flow", base_config.get("use_v36_flow", False)),
                # v3.7 Direct Dialogue Enforcement
                use_v37_flow=var_data.get("use_v37_flow", base_config.get("use_v37_flow", False)),
            )
            variations.append(var_config)

        # シナリオ設定の変換
        scenarios = []
        scenario_names = base_config.get("scenarios", [])
        scenario_defs = data.get("scenario_definitions", {})

        # デフォルトシナリオ定義
        default_scenarios = {
            "casual_greeting": ScenarioConfig(
                name="casual_greeting",
                initial_prompt="おはよう、二人とも",
                turns=5,
                evaluation_focus=["character_consistency", "naturalness"]
            ),
            "emotional_support": ScenarioConfig(
                name="emotional_support",
                initial_prompt="最近疲れてるんだ...",
                turns=6,
                evaluation_focus=["relationship_quality", "naturalness"]
            ),
            "topic_exploration": ScenarioConfig(
                name="topic_exploration",
                initial_prompt="最近のAI技術について話して",
                turns=8,
                evaluation_focus=["topic_novelty", "concreteness"]
            ),
            "disagreement_resolution": ScenarioConfig(
                name="disagreement_resolution",
                initial_prompt="直感とデータ、どっちが大事？",
                turns=10,
                evaluation_focus=["relationship_quality", "naturalness"]
            ),
            # v3.4追加: ゼロ距離テスト（感情・関係性の純粋なテスト）
            "zero_distance_test": ScenarioConfig(
                name="zero_distance_test",
                initial_prompt="今夜は飲みに行こうか！",
                turns=6,
                evaluation_focus=["direct_addressing_rate", "naturalness", "relationship_quality"]
            ),
        }

        for scenario_name in scenario_names:
            if scenario_name in scenario_defs:
                sd = scenario_defs[scenario_name]
                scenarios.append(ScenarioConfig(
                    name=scenario_name,
                    initial_prompt=sd.get("prompt", ""),
                    turns=sd.get("turns", 5),
                    evaluation_focus=sd.get("evaluation_focus", [])
                ))
            elif scenario_name in default_scenarios:
                scenarios.append(default_scenarios[scenario_name])

        return cls(
            experiment_id=experiment.get("id", "unnamed"),
            name=experiment.get("name", "Unnamed Experiment"),
            description=experiment.get("description", ""),
            base_config=base_config,
            variations=variations,
            scenarios=scenarios,
            metrics=data.get("metrics", [
                "naturalness",
                "character_consistency",
                "concreteness",
                "relationship_quality",
                "topic_novelty",
            ]),
        )
