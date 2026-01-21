"""SystemAdapterテスト"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.adapters.types import (
    ConnectionMethod,
    DialogueResult,
    DialogueTurn,
    EvaluationScenario,
)
from evaluation.adapters.base import SystemAdapter
from evaluation.adapters.duo_talk_adapter import DuoTalkAdapter
from evaluation.adapters.duo_talk_simple_adapter import DuoTalkSimpleAdapter
from evaluation.adapters.duo_talk_silly_adapter import DuoTalkSillyAdapter


class TestDialogueTurn:
    """DialogueTurnのテスト"""

    def test_creation(self):
        """基本的な作成テスト"""
        turn = DialogueTurn(speaker="やな", content="おはよう！")
        assert turn.speaker == "やな"
        assert turn.content == "おはよう！"
        assert turn.turn_number == 0

    def test_to_dict(self):
        """to_dict変換テスト"""
        turn = DialogueTurn(speaker="あゆ", content="おはよう！", turn_number=1)
        result = turn.to_dict()
        assert result == {"speaker": "あゆ", "content": "おはよう！"}


class TestDialogueResult:
    """DialogueResultのテスト"""

    def test_creation(self):
        """基本的な作成テスト"""
        turns = [
            DialogueTurn(speaker="やな", content="おはよう！"),
            DialogueTurn(speaker="あゆ", content="おはよう！"),
        ]
        result = DialogueResult(
            conversation=turns,
            success=True,
            system_name="test-system"
        )
        assert result.success is True
        assert len(result.conversation) == 2
        assert result.error is None

    def test_to_standard_format(self):
        """標準フォーマット変換テスト"""
        turns = [
            DialogueTurn(speaker="やな", content="おはよう！"),
            DialogueTurn(speaker="あゆ", content="おはようー！"),
        ]
        result = DialogueResult(
            conversation=turns,
            success=True,
            system_name="test"
        )
        standard = result.to_standard_format()
        assert standard == [
            {"speaker": "やな", "content": "おはよう！"},
            {"speaker": "あゆ", "content": "おはようー！"},
        ]


class TestEvaluationScenario:
    """EvaluationScenarioのテスト"""

    def test_creation(self):
        """基本的な作成テスト"""
        scenario = EvaluationScenario(
            name="casual_greeting",
            initial_prompt="おはよう、二人とも",
            turns=5
        )
        assert scenario.name == "casual_greeting"
        assert scenario.turns == 5


class TestDuoTalkAdapter:
    """DuoTalkAdapterのユニットテスト"""

    def test_initialization(self):
        """初期化テスト"""
        adapter = DuoTalkAdapter()
        assert adapter.system_name == "duo-talk"
        assert adapter.connection_method == ConnectionMethod.HTTP_API
        assert adapter.base_url == "http://localhost:5000"

    def test_custom_url(self):
        """カスタムURL指定テスト"""
        adapter = DuoTalkAdapter(base_url="http://custom:8000")
        assert adapter.base_url == "http://custom:8000"

    def test_get_system_info(self):
        """システム情報取得テスト"""
        adapter = DuoTalkAdapter()
        with patch.object(adapter, "is_available", return_value=False):
            info = adapter.get_system_info()
            assert info["name"] == "duo-talk"
            assert info["connection_method"] == "http_api"
            assert info["available"] is False

    def test_is_available_success(self):
        """ヘルスチェック成功テスト"""
        adapter = DuoTalkAdapter()
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            assert adapter.is_available() is True

    def test_is_available_failure(self):
        """ヘルスチェック失敗テスト"""
        import requests as req
        adapter = DuoTalkAdapter()
        with patch("evaluation.adapters.duo_talk_adapter.requests.get") as mock_get:
            mock_get.side_effect = req.RequestException("Connection refused")
            assert adapter.is_available() is False

    def test_generate_dialogue_success(self):
        """会話生成成功テスト"""
        adapter = DuoTalkAdapter()
        mock_response = {
            "status": "success",
            "run_id": "test_001",
            "dialogue": [
                {"speaker": "A", "speaker_name": "やな", "text": "おはよう！", "turn_number": 0},
                {"speaker": "B", "speaker_name": "あゆ", "text": "おはよー！", "turn_number": 1}
            ]
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = MagicMock()
            mock_post.return_value.json.return_value = mock_response

            result = adapter.generate_dialogue("おはよう", turns=2)

            assert result.success is True
            assert len(result.conversation) == 2
            assert result.conversation[0].speaker == "やな"
            assert result.conversation[1].speaker == "あゆ"
            assert result.metadata["run_id"] == "test_001"

    def test_generate_dialogue_timeout(self):
        """タイムアウトテスト"""
        import requests
        adapter = DuoTalkAdapter(timeout_seconds=1)

        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.Timeout()

            result = adapter.generate_dialogue("test", turns=5)

            assert result.success is False
            assert "Timeout" in result.error

    def test_run_scenario(self):
        """シナリオ実行テスト"""
        adapter = DuoTalkAdapter()
        scenario = EvaluationScenario(
            name="test",
            initial_prompt="テストお題",
            turns=3
        )

        with patch.object(adapter, "generate_dialogue") as mock_gen:
            mock_gen.return_value = DialogueResult(
                conversation=[],
                success=True,
                system_name="duo-talk"
            )
            adapter.run_scenario(scenario)
            mock_gen.assert_called_once_with(
                initial_prompt="テストお題",
                turns=3
            )


class TestDuoTalkSimpleAdapter:
    """DuoTalkSimpleAdapterのユニットテスト"""

    def test_initialization(self):
        """初期化テスト"""
        adapter = DuoTalkSimpleAdapter()
        assert adapter.system_name == "duo-talk-simple"
        assert adapter.connection_method == ConnectionMethod.LIBRARY
        assert adapter._initialized is False

    def test_custom_path(self):
        """カスタムパス指定テスト"""
        custom_path = Path("/custom/path")
        adapter = DuoTalkSimpleAdapter(project_path=custom_path)
        assert adapter.project_path == custom_path

    def test_get_system_info(self):
        """システム情報取得テスト"""
        adapter = DuoTalkSimpleAdapter()
        with patch.object(adapter, "is_available", return_value=False):
            info = adapter.get_system_info()
            assert info["name"] == "duo-talk-simple"
            assert info["connection_method"] == "library"

    def test_is_available_without_init(self):
        """初期化前のis_availableテスト"""
        adapter = DuoTalkSimpleAdapter()
        # 実際のduo-talk-simpleがない環境では失敗する
        with patch.object(adapter, "_lazy_init", return_value=False):
            assert adapter.is_available() is False


class TestDuoTalkSillyAdapter:
    """DuoTalkSillyAdapterのユニットテスト"""

    def test_initialization(self):
        """初期化テスト"""
        adapter = DuoTalkSillyAdapter()
        assert adapter.system_name == "duo-talk-silly"
        assert adapter.connection_method == ConnectionMethod.HTTP_API
        assert adapter.kobold_url == "http://localhost:5001"

    def test_custom_url(self):
        """カスタムURL指定テスト"""
        adapter = DuoTalkSillyAdapter(kobold_url="http://custom:8000")
        assert adapter.kobold_url == "http://custom:8000"

    def test_is_available_success(self):
        """KoboldCPP接続成功テスト"""
        adapter = DuoTalkSillyAdapter()
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            assert adapter.is_available() is True

    def test_is_available_failure(self):
        """KoboldCPP接続失敗テスト"""
        import requests as req
        adapter = DuoTalkSillyAdapter()
        with patch("evaluation.adapters.duo_talk_silly_adapter.requests.get") as mock_get:
            mock_get.side_effect = req.RequestException("Connection refused")
            assert adapter.is_available() is False

    def test_generate_dialogue_success(self):
        """会話生成成功テスト"""
        adapter = DuoTalkSillyAdapter()

        with patch.object(adapter, "is_available", return_value=True):
            with patch.object(adapter, "_generate_response", side_effect=[
                "おはようございます、あゆ！今日は何をしようかしら？",
                "おはよう、お姉ちゃん。うーん、今日は読書かな？"
            ]):
                result = adapter.generate_dialogue("おはよう", turns=2)

                assert result.success is True
                assert len(result.conversation) == 2
                assert result.conversation[0].speaker == "やな"
                assert result.conversation[1].speaker == "あゆ"

    def test_generate_dialogue_kobold_unavailable(self):
        """KoboldCPP利用不可時のテスト"""
        adapter = DuoTalkSillyAdapter()

        with patch.object(adapter, "is_available", return_value=False):
            result = adapter.generate_dialogue("test", turns=2)

            assert result.success is False
            assert "not available" in result.error

    def test_build_prompt(self):
        """プロンプト構築テスト"""
        adapter = DuoTalkSillyAdapter()
        from evaluation.adapters.duo_talk_silly_adapter import YANA_PERSONA

        prompt = adapter._build_prompt(
            persona=YANA_PERSONA,
            speaker="やな",
            topic="今日の予定",
            history=[
                {"speaker": "あゆ", "content": "何するの？"}
            ]
        )

        assert "やな" in prompt
        assert "今日の予定" in prompt
        assert "あゆ: 何するの？" in prompt


class TestAdapterIntegration:
    """アダプタ統合テスト（実際のサービス接続が必要）"""

    @pytest.mark.skipif(True, reason="Integration tests require running services")
    def test_duo_talk_real_connection(self):
        """duo-talk実接続テスト"""
        adapter = DuoTalkAdapter()
        if adapter.is_available():
            result = adapter.generate_dialogue("テスト", turns=2)
            assert result.success is True

    @pytest.mark.skipif(True, reason="Integration tests require running services")
    def test_duo_talk_silly_real_connection(self):
        """KoboldCPP実接続テスト"""
        adapter = DuoTalkSillyAdapter()
        if adapter.is_available():
            result = adapter.generate_dialogue("テスト", turns=2)
            assert result.success is True
