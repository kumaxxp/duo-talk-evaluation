"""Ollama を使った対話品質評価"""

import json
import re
from typing import List, Dict
import requests

from .metrics import DialogueQualityMetrics


EVALUATION_PROMPT_TEMPLATE = """あなたは対話品質の評価専門家です。
以下の姉妹AI「やな」と「あゆ」の会話を、5つの観点から0.0-1.0でスコア評価してください。

## キャラクター設定
やな（姉）: 一人称「私」、直感的、行動派、砕けた口調
あゆ（妹）: 一人称「あたし」、分析的、慎重、丁寧語だが毒舌

## 評価対象の会話
{conversation_history}

## 評価観点
1. character_consistency: キャラクター一貫性（一人称、口調、性格）
2. topic_novelty: 話題の新規性（繰り返しがないか）
3. relationship_quality: 姉妹関係性（からかい、心配、協調）
4. naturalness: 対話の自然さ（テンポ、話題転換）
5. concreteness: 情報の具体性（具体例、数値）

必ずこの形式のJSONのみを出力してください：
{{
  "character_consistency": 数値,
  "topic_novelty": 数値,
  "relationship_quality": 数値,
  "naturalness": 数値,
  "concreteness": 数値,
  "overall_score": 数値,
  "issues": ["問題点"],
  "strengths": ["良い点"],
  "suggestions": ["改善案"]
}}
"""


class OllamaEvaluator:
    """Ollama を使った評価システム"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gemma3:12b"
    ):
        self.base_url = base_url
        self.model = model

    def evaluate_conversation(
        self,
        conversation: List[Dict[str, str]]
    ) -> DialogueQualityMetrics:
        """会話を評価"""
        conv_text = self._format_conversation(conversation)
        prompt = EVALUATION_PROMPT_TEMPLATE.format(
            conversation_history=conv_text
        )

        try:
            # Ollamaで生成
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # 低めで安定した評価
                        "num_predict": 800,
                    }
                },
                timeout=120
            )
            response.raise_for_status()

            generated_text = response.json()["response"]
            result = self._parse_response(generated_text)

            return DialogueQualityMetrics(
                character_consistency=result.get("character_consistency", 0.5),
                topic_novelty=result.get("topic_novelty", 0.5),
                relationship_quality=result.get("relationship_quality", 0.5),
                naturalness=result.get("naturalness", 0.5),
                concreteness=result.get("concreteness", 0.5),
                overall_score=result.get("overall_score", 0.5),
                issues=result.get("issues", []),
                strengths=result.get("strengths", []),
                suggestions=result.get("suggestions", [])
            )

        except Exception as e:
            print(f"Ollama評価エラー: {e}")
            return DialogueQualityMetrics(
                character_consistency=0.5,
                topic_novelty=0.5,
                relationship_quality=0.5,
                naturalness=0.5,
                concreteness=0.5,
                overall_score=0.5,
                issues=[f"評価失敗: {str(e)}"]
            )

    def _format_conversation(self, conversation: List[Dict[str, str]]) -> str:
        return "\n".join([
            f"{msg['speaker']}: {msg['content']}"
            for msg in conversation
        ])

    def _parse_response(self, response_text: str) -> dict:
        """生成テキストからJSONを抽出"""
        text = response_text.strip()

        # JSONブロックを探す（複数行対応）
        json_match = re.search(r'\{[\s\S]*?\}', text)
        if json_match:
            json_text = json_match.group(0)
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass

        # より緩いパターンで再試行
        try:
            # コードブロック内のJSONを探す
            code_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
            if code_match:
                return json.loads(code_match.group(1))
        except:
            pass

        # 見つからない場合はデフォルト
        return {
            "character_consistency": 0.5,
            "topic_novelty": 0.5,
            "relationship_quality": 0.5,
            "naturalness": 0.5,
            "concreteness": 0.5,
            "overall_score": 0.5,
            "issues": ["JSON解析失敗"],
            "strengths": [],
            "suggestions": []
        }

    def is_available(self) -> bool:
        """Ollamaが起動しているかチェック"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
