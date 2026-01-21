"""duo-talk-simple 接続アダプタ"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional

from .base import SystemAdapter
from .types import ConnectionMethod, DialogueResult, DialogueTurn

logger = logging.getLogger(__name__)

# duo-talk-simpleのデフォルトパス
DUO_TALK_SIMPLE_PATH = Path("/home/owner/work/duo-talk-simple")


class DuoTalkSimpleAdapter(SystemAdapter):
    """
    duo-talk-simple接続アダプタ

    接続先: /home/owner/work/duo-talk-simple/
    方式: ライブラリインポート
    特徴: CLI特化、Ollama、シンプル構成
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        config_path: str = "config.yaml",
        timeout_seconds: int = 300
    ):
        """
        Args:
            project_path: duo-talk-simpleプロジェクトパス
            config_path: 設定ファイルの相対パス
            timeout_seconds: タイムアウト秒数
        """
        super().__init__(
            system_name="duo-talk-simple",
            connection_method=ConnectionMethod.LIBRARY,
            timeout_seconds=timeout_seconds
        )
        self.project_path = project_path or DUO_TALK_SIMPLE_PATH
        self.config_path = config_path
        self._system = None
        self._initialized = False

    def _lazy_init(self) -> bool:
        """遅延初期化（必要時のみシステムをロード）"""
        if self._initialized:
            return self._system is not None

        self._initialized = True

        try:
            # duo-talk-simpleをパスに追加
            project_str = str(self.project_path)
            if project_str not in sys.path:
                sys.path.insert(0, project_str)

            # 必要なモジュールをインポート
            import yaml
            from core.ollama_client import OllamaClient
            from core.rag_engine import RAGEngine
            from core.character import Character

            # 設定ファイル読み込み
            config_file = self.project_path / self.config_path
            if not config_file.exists():
                logger.error(f"Config file not found: {config_file}")
                return False

            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # OllamaClient初期化
            ollama_config = config.get("ollama", {})
            client = OllamaClient(
                base_url=ollama_config.get("base_url", "http://localhost:11434/v1"),
                model=ollama_config.get("llm_model", "gemma3:12b"),
                timeout=ollama_config.get("timeout", 30.0),
                max_retries=ollama_config.get("max_retries", 3)
            )

            # Ollama接続確認
            if not client.is_healthy():
                logger.error("Ollama not available")
                return False

            # RAGEngine初期化
            rag_config = config.get("rag", {})
            rag = RAGEngine(
                ollama_client=client,
                chroma_path=str(self.project_path / rag_config.get("chroma_db_path", "./data/chroma_db")),
                collection_name=rag_config.get("collection_name", "duo_knowledge")
            )

            # キャラクター初期化
            char_configs = config.get("characters", {})
            characters = {}

            for char_name, char_config in char_configs.items():
                if char_config.get("enabled", True):
                    config_file_path = self.project_path / char_config.get("config", f"personas/{char_name}.yaml")
                    characters[char_name] = Character(
                        name=char_name,
                        config_path=str(config_file_path),
                        ollama_client=client,
                        rag_engine=rag,
                        generation_defaults=char_config.get("generation", {}),
                        max_history=char_config.get("max_history", 10)
                    )

            self._system = {
                "client": client,
                "rag": rag,
                "characters": characters,
                "config": config
            }

            logger.info("duo-talk-simple initialized successfully")
            return True

        except ImportError as e:
            logger.error(f"Failed to import duo-talk-simple modules: {e}")
            self._system = None
            return False
        except Exception as e:
            logger.error(f"Failed to initialize duo-talk-simple: {e}")
            self._system = None
            return False

    def is_available(self) -> bool:
        """Ollamaが起動しているかチェック"""
        if not self._lazy_init():
            return False

        try:
            return self._system["client"].is_healthy()
        except Exception:
            return False

    def generate_dialogue(
        self,
        initial_prompt: str,
        turns: int,
        temperature: float = 0.7
    ) -> DialogueResult:
        """
        DuoDialogueManagerを使用して会話を生成

        Args:
            initial_prompt: 初期プロンプト（お題）
            turns: 会話ターン数
            temperature: 未使用（キャラクター設定で固定）

        Returns:
            DialogueResult: 会話生成結果
        """
        start_time = time.time()

        if not self._lazy_init():
            return DialogueResult(
                conversation=[],
                success=False,
                system_name=self.system_name,
                error="System initialization failed",
                execution_time_seconds=time.time() - start_time
            )

        try:
            from core.duo_dialogue import DuoDialogueManager

            characters = self._system["characters"]
            config = self._system["config"]

            # やなとあゆの両方が必要
            if "yana" not in characters or "ayu" not in characters:
                return DialogueResult(
                    conversation=[],
                    success=False,
                    system_name=self.system_name,
                    error="Both yana and ayu characters required",
                    execution_time_seconds=time.time() - start_time
                )

            # DuoDialogueManager設定
            duo_config = config.get("duo_dialogue", {}).copy()
            duo_config["max_turns"] = turns

            manager = DuoDialogueManager(
                yana=characters["yana"],
                ayu=characters["ayu"],
                config=duo_config
            )

            # 対話開始
            manager.start_dialogue(initial_prompt)

            # 対話ループ
            while manager.should_continue():
                manager.next_turn()

            # 結果変換
            conversation = []
            # dialogue_historyから会話を取得
            history = getattr(manager, "dialogue_history", [])
            for i, entry in enumerate(history):
                speaker = entry.get("speaker", "unknown")
                # speaker名の正規化（yana -> やな, ayu -> あゆ）
                if speaker.lower() == "yana":
                    speaker = "やな"
                elif speaker.lower() == "ayu":
                    speaker = "あゆ"

                conversation.append(DialogueTurn(
                    speaker=speaker,
                    content=entry.get("content", ""),
                    turn_number=i
                ))

            # 履歴クリア（次回の実行に影響しないように）
            characters["yana"].clear_history()
            characters["ayu"].clear_history()

            # 品質レポート取得
            quality_report = {}
            if hasattr(manager, "get_quality_report"):
                quality_report = manager.get_quality_report()

            return DialogueResult(
                conversation=conversation,
                success=True,
                system_name=self.system_name,
                execution_time_seconds=time.time() - start_time,
                metadata={
                    "quality_score": quality_report.get("quality_score", 0),
                    "summary": manager.get_summary() if hasattr(manager, "get_summary") else None
                }
            )

        except Exception as e:
            logger.exception("Dialogue generation failed")
            return DialogueResult(
                conversation=[],
                success=False,
                system_name=self.system_name,
                error=str(e),
                execution_time_seconds=time.time() - start_time
            )
