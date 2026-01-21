"""Gemini APIを使った対話品質評価（google-genai SDK使用）"""

import os
import json
import re
from typing import List, Dict, Optional
from google import genai

from .metrics import DialogueQualityMetrics

# 利用可能な安定版モデル（2025年以降）
# gemini-2.0-flash は rate limit が厳しいため gemini-2.5-flash を使用
DEFAULT_MODEL_NAME = "gemini-2.5-flash"


EVALUATION_PROMPT_TEMPLATE = """
あなたは対話品質の評価専門家です。
以下の姉妹AI「やな」と「あゆ」の会話を、5つの観点から評価してください。

## キャラクター設定
やな（姉）: 一人称「私」、直感的、行動派、口調「〜わ」「〜かしら」
あゆ（妹）: 一人称「あたし」、分析的、慎重、口調「〜だよ」「〜じゃん」

## 評価対象の会話
{conversation_history}

## 評価観点（各0.0-1.0でスコア）

1. character_consistency: キャラクター設定との一貫性
   - 一人称は正しいか
   - 口調は維持されているか
   - 性格（直感 vs 分析）が表現されているか

2. topic_novelty: 話題の新規性
   - 同じ話題の繰り返しがないか
   - 新しい視点・情報が加わっているか

3. relationship_quality: 姉妹らしい関係性
   - やながあゆをからかう場面があるか
   - あゆがやなを心配する場面があるか
   - 対立と協調のバランスが良いか

4. naturalness: 対話の自然さ
   - 会話のテンポは良いか
   - 話題転換は滑らかか
   - 相手の発言に適切に応答しているか

5. concreteness: 情報の具体性
   - 一般論だけで終わっていないか
   - 具体例・数値・固有名詞が出ているか

## 出力形式（JSON）
{{
  "character_consistency": 0.0-1.0の数値,
  "topic_novelty": 0.0-1.0の数値,
  "relationship_quality": 0.0-1.0の数値,
  "naturalness": 0.0-1.0の数値,
  "concreteness": 0.0-1.0の数値,
  "overall_score": 0.0-1.0の数値,
  "issues": ["具体的な問題点1", "問題点2", ...],
  "strengths": ["良かった点1", "良かった点2", ...],
  "suggestions": ["改善提案1", "改善提案2", ...]
}}

必ずJSON形式のみで出力してください。説明文は不要です。
"""


class DialogueEvaluator:
    """Gemini APIを使った対話品質評価システム"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL_NAME
    ):
        """
        Args:
            api_key: Gemini API key (未指定時は環境変数GEMINI_API_KEYから取得)
            model_name: 使用するGeminiモデル名
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
    
    def evaluate_conversation(
        self, 
        conversation: List[Dict[str, str]]
    ) -> DialogueQualityMetrics:
        """
        会話を評価してメトリクスを返す
        
        Args:
            conversation: [{"speaker": "やな", "content": "..."}] 形式の会話履歴
            
        Returns:
            DialogueQualityMetrics: 評価結果
        """
        # 会話履歴をフォーマット
        conv_text = self._format_conversation(conversation)
        
        # Geminiで評価
        prompt = EVALUATION_PROMPT_TEMPLATE.format(
            conversation_history=conv_text
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            result = self._parse_response(response.text)
            
            return DialogueQualityMetrics(
                character_consistency=result["character_consistency"],
                topic_novelty=result["topic_novelty"],
                relationship_quality=result["relationship_quality"],
                naturalness=result["naturalness"],
                concreteness=result["concreteness"],
                overall_score=result.get("overall_score", 0.0),
                issues=result.get("issues", []),
                strengths=result.get("strengths", []),
                suggestions=result.get("suggestions", [])
            )
        
        except Exception as e:
            print(f"評価エラー: {e}")
            # エラー時はデフォルト値
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
        """会話履歴をテキスト形式にフォーマット"""
        return "\n".join([
            f"{msg['speaker']}: {msg['content']}"
            for msg in conversation
        ])
    
    def _parse_response(self, response_text: str) -> dict:
        """Geminiレスポンスからjsonを抽出・パース"""
        # ```json ... ``` を削除
        text = response_text.strip()
        
        # コードブロック除去
        if text.startswith("```"):
            # 最初の```を除去
            text = re.sub(r'^```(?:json)?\s*', '', text)
            # 最後の```を除去
            text = re.sub(r'\s*```$', '', text)
        
        return json.loads(text)
