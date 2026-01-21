"""評価システムのテスト"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.evaluator import DialogueEvaluator, DEFAULT_MODEL_NAME
from evaluation.metrics import DialogueQualityMetrics


@pytest.fixture
def sample_conversation():
    """テスト用サンプル会話"""
    return [
        {"speaker": "やな", "content": "おはよう、あゆ。今日は何する予定？"},
        {"speaker": "あゆ", "content": "おはよー！えっとね、勉強する予定だよ"},
        {"speaker": "やな", "content": "勉強偉いわね。私は散歩でも行こうかしら"},
        {"speaker": "あゆ", "content": "お姉ちゃんは気楽でいいなー"}
    ]


@pytest.fixture
def mock_gemini_response_json():
    """モックGeminiレスポンスJSON文字列"""
    return """{
  "character_consistency": 0.9,
  "topic_novelty": 0.7,
  "relationship_quality": 0.8,
  "naturalness": 0.85,
  "concreteness": 0.6,
  "overall_score": 0.77,
  "issues": ["具体的な予定がやや不明確"],
  "strengths": ["キャラクターの一人称が正確", "姉妹らしい掛け合い"],
  "suggestions": ["勉強の具体的内容に触れると良い"]
}"""


class TestDialogueQualityMetrics:
    """DialogueQualityMetricsのテスト"""

    def test_metrics_creation(self):
        """メトリクスの作成テスト"""
        metrics = DialogueQualityMetrics(
            character_consistency=0.9,
            topic_novelty=0.7,
            relationship_quality=0.8,
            naturalness=0.85,
            concreteness=0.6,
            issues=["テスト問題"]
        )

        assert metrics.character_consistency == 0.9
        assert 0.0 <= metrics.overall_score <= 1.0
        assert len(metrics.issues) > 0

    def test_overall_score_auto_calculation(self):
        """overall_score未指定時の自動計算テスト"""
        metrics = DialogueQualityMetrics(
            character_consistency=1.0,
            topic_novelty=1.0,
            relationship_quality=1.0,
            naturalness=1.0,
            concreteness=1.0,
            issues=[]
        )
        # 重み付け平均: 0.25 + 0.20 + 0.25 + 0.15 + 0.15 = 1.0
        assert metrics.overall_score == 1.0

    def test_to_dict(self):
        """to_dict変換テスト"""
        metrics = DialogueQualityMetrics(
            character_consistency=0.8,
            topic_novelty=0.7,
            relationship_quality=0.9,
            naturalness=0.6,
            concreteness=0.5,
            issues=["問題1"],
            strengths=["良い点1"],
            suggestions=["提案1"]
        )
        result = metrics.to_dict()

        assert result["character_consistency"] == 0.8
        assert result["issues"] == ["問題1"]
        assert result["strengths"] == ["良い点1"]


class TestDialogueEvaluatorInitialization:
    """DialogueEvaluatorの初期化テスト"""

    def test_initialization_without_api_key_raises_error(self):
        """API Key未設定でエラーを投げる"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                DialogueEvaluator()

    def test_initialization_with_env_api_key(self):
        """環境変数からAPI Keyを取得"""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key-123'}):
            with patch('evaluation.evaluator.genai.Client') as mock_client:
                evaluator = DialogueEvaluator()
                assert evaluator.api_key == 'test-key-123'
                mock_client.assert_called_once_with(api_key='test-key-123')

    def test_initialization_with_explicit_api_key(self):
        """明示的なAPI Keyで初期化"""
        with patch('evaluation.evaluator.genai.Client') as mock_client:
            evaluator = DialogueEvaluator(api_key='explicit-key')
            assert evaluator.api_key == 'explicit-key'
            mock_client.assert_called_once_with(api_key='explicit-key')

    def test_default_model_name_is_valid(self):
        """デフォルトモデル名が正しく設定されている"""
        # gemini-2.0-flash または gemini-2.5-flash が利用可能
        valid_models = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-2.0-flash-lite']
        assert DEFAULT_MODEL_NAME in valid_models

    def test_custom_model_name(self):
        """カスタムモデル名を指定可能"""
        with patch('evaluation.evaluator.genai.Client'):
            evaluator = DialogueEvaluator(api_key='test-key', model_name='gemini-2.5-pro')
            assert evaluator.model_name == 'gemini-2.5-pro'


class TestDialogueEvaluatorMocked:
    """DialogueEvaluatorのモックテスト"""

    def test_format_conversation(self, sample_conversation):
        """会話フォーマットテスト"""
        with patch('evaluation.evaluator.genai.Client'):
            evaluator = DialogueEvaluator(api_key='test-key')
            formatted = evaluator._format_conversation(sample_conversation)

            assert "やな:" in formatted
            assert "あゆ:" in formatted
            assert "おはよう" in formatted
            assert formatted.count("\n") == len(sample_conversation) - 1

    def test_parse_response_plain_json(self):
        """プレーンJSONのパースをテスト"""
        with patch('evaluation.evaluator.genai.Client'):
            evaluator = DialogueEvaluator(api_key='test-key')
            json_text = '{"character_consistency": 0.9, "topic_novelty": 0.8}'
            result = evaluator._parse_response(json_text)

            assert result["character_consistency"] == 0.9
            assert result["topic_novelty"] == 0.8

    def test_parse_response_with_code_block(self):
        """コードブロック付きJSONのパースをテスト"""
        with patch('evaluation.evaluator.genai.Client'):
            evaluator = DialogueEvaluator(api_key='test-key')
            json_text = '''```json
{"character_consistency": 0.85, "issues": ["test"]}
```'''
            result = evaluator._parse_response(json_text)

            assert result["character_consistency"] == 0.85
            assert result["issues"] == ["test"]

    def test_evaluate_conversation_with_mock(self, sample_conversation, mock_gemini_response_json):
        """モックAPIでの評価テスト"""
        mock_response = MagicMock()
        mock_response.text = mock_gemini_response_json

        with patch('evaluation.evaluator.genai.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            evaluator = DialogueEvaluator(api_key='test-key')
            metrics = evaluator.evaluate_conversation(sample_conversation)

            assert isinstance(metrics, DialogueQualityMetrics)
            assert metrics.character_consistency == 0.9
            assert metrics.topic_novelty == 0.7
            assert metrics.overall_score == 0.77

    def test_evaluate_conversation_api_error_returns_default(self, sample_conversation):
        """API エラー時にデフォルト値を返す"""
        with patch('evaluation.evaluator.genai.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client

            evaluator = DialogueEvaluator(api_key='test-key')
            metrics = evaluator.evaluate_conversation(sample_conversation)

            assert isinstance(metrics, DialogueQualityMetrics)
            assert metrics.character_consistency == 0.5
            assert "評価失敗" in metrics.issues[0]


@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set"
)
class TestDialogueEvaluatorIntegration:
    """実際のGemini APIでの統合テスト"""

    def test_evaluate_conversation_real(self, sample_conversation):
        """実際のGemini APIで評価が成功する"""
        evaluator = DialogueEvaluator()
        metrics = evaluator.evaluate_conversation(sample_conversation)

        assert isinstance(metrics, DialogueQualityMetrics)
        assert 0.0 <= metrics.character_consistency <= 1.0
        assert 0.0 <= metrics.topic_novelty <= 1.0
        assert 0.0 <= metrics.relationship_quality <= 1.0
        assert 0.0 <= metrics.naturalness <= 1.0
        assert 0.0 <= metrics.concreteness <= 1.0
        assert 0.0 <= metrics.overall_score <= 1.0

    def test_model_connection(self):
        """Geminiモデルへの接続確認"""
        import time
        from google.genai.errors import ClientError

        evaluator = DialogueEvaluator()

        # Rate Limitエラーはリトライ
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = evaluator.client.models.generate_content(
                    model=evaluator.model_name,
                    contents='Say "OK" if you can read this.'
                )
                assert response.text is not None
                assert len(response.text) > 0
                return
            except ClientError as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    time.sleep(10)
                    continue
                pytest.skip(f"API rate limit exceeded: {e}")
