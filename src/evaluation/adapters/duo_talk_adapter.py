"""duo-talk (メインプロジェクト) 接続アダプタ

コンソールモード: UnifiedPipelineを直接インポートして使用。
Flaskサーバー不要。
"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional

from .base import SystemAdapter
from .types import ConnectionMethod, DialogueResult, DialogueTurn

logger = logging.getLogger(__name__)

# duo-talkのデフォルトパス
DUO_TALK_PATH = Path("/home/owner/work/duo-talk")


class DuoTalkAdapter(SystemAdapter):
    """
    duo-talk接続アダプタ（コンソールモード）

    接続先: /home/owner/work/duo-talk/
    方式: ライブラリインポート（UnifiedPipeline直接呼び出し）
    特徴: Director、ChromaDB RAG、UnifiedPipeline
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        timeout_seconds: int = 300,
        base_url: str = None,  # 後方互換性のため残す（未使用）
    ):
        """
        Args:
            project_path: duo-talkプロジェクトパス
            timeout_seconds: タイムアウト秒数
            base_url: 未使用（後方互換性のため）
        """
        super().__init__(
            system_name="duo-talk",
            connection_method=ConnectionMethod.LIBRARY,
            timeout_seconds=timeout_seconds
        )
        self.project_path = project_path or DUO_TALK_PATH
        self._pipeline = None
        self._initialized = False

    def _lazy_init(self) -> bool:
        """遅延初期化（必要時のみパイプラインをロード）"""
        if self._initialized:
            return self._pipeline is not None

        self._initialized = True

        import os
        original_cwd = os.getcwd()

        try:
            # duo-talkディレクトリに移動（設定ファイル読み込みのため）
            os.chdir(self.project_path)

            # duo-talkをパスに追加
            project_str = str(self.project_path)
            if project_str not in sys.path:
                sys.path.insert(0, project_str)

            # .envを読み込み
            from dotenv import load_dotenv
            env_path = self.project_path / ".env"
            if env_path.exists():
                load_dotenv(env_path, override=True)
                logger.info(f"Loaded .env from {env_path}")

            # LLMクライアントをリセット（設定を再読み込み）
            from src.llm_client import reset_llm_client
            reset_llm_client()

            # LLMプロバイダの状態を確認・更新
            from src.llm_provider import get_llm_provider
            provider = get_llm_provider()
            status = provider.get_status()
            logger.info(f"LLM Backend: {status.get('current_backend')}")
            logger.info(f"LLM Model: {status.get('current_model')}")

            # Ollama接続確認
            if status.get('current_backend') == 'ollama':
                ollama_status = status.get('ollama', {})
                if not ollama_status.get('available'):
                    logger.error(f"Ollama not available: {ollama_status.get('error')}")
                    return False

            # UnifiedPipelineをインポート
            from src.unified_pipeline import UnifiedPipeline

            # パイプライン初期化（JetRacerなし、評価用に高速化）
            self._pipeline = UnifiedPipeline(
                jetracer_client=None,
                enable_fact_check=False,  # 評価用に無効化（高速化）
                jetracer_mode=False,
                enable_florence2=False,  # VLM不要
            )

            logger.info("duo-talk UnifiedPipeline initialized successfully")
            return True

        except ImportError as e:
            logger.error(f"Failed to import duo-talk modules: {e}")
            self._pipeline = None
            return False
        except Exception as e:
            logger.error(f"Failed to initialize duo-talk: {e}")
            self._pipeline = None
            return False
        finally:
            # 元のディレクトリに戻る
            os.chdir(original_cwd)

    def is_available(self) -> bool:
        """システムが利用可能かチェック"""
        return self._lazy_init()

    def generate_dialogue(
        self,
        initial_prompt: str,
        turns: int,
        temperature: float = 0.7
    ) -> DialogueResult:
        """
        UnifiedPipeline経由で会話を生成

        Args:
            initial_prompt: 初期プロンプト（お題）
            turns: 会話ターン数
            temperature: 未使用（パイプライン内で制御）

        Returns:
            DialogueResult: 会話生成結果
        """
        start_time = time.time()

        if not self._lazy_init():
            return DialogueResult(
                conversation=[],
                success=False,
                system_name=self.system_name,
                error="Pipeline initialization failed",
                execution_time_seconds=time.time() - start_time
            )

        try:
            # 入力バンドル作成
            from src.input_source import InputBundle, InputSource, SourceType
            input_bundle = InputBundle(
                sources=[InputSource(source_type=SourceType.TEXT, content=initial_prompt)]
            )

            # パイプライン実行
            result = self._pipeline.run(
                initial_input=input_bundle,
                max_turns=turns,
            )

            # 結果変換
            conversation = []
            for turn in result.dialogue:
                speaker_name = turn.speaker_name or (
                    "やな" if turn.speaker == "A" else "あゆ"
                )
                conversation.append(DialogueTurn(
                    speaker=speaker_name,
                    content=turn.text,
                    turn_number=turn.turn_number,
                    metadata={
                        "evaluation_status": turn.evaluation.status.name if turn.evaluation else None,
                        "rag_hints": turn.rag_hints or [],
                    }
                ))

            success = result.status == "success"
            error_msg = result.error if result.status == "error" else None

            return DialogueResult(
                conversation=conversation,
                success=success,
                system_name=self.system_name,
                error=error_msg,
                execution_time_seconds=time.time() - start_time,
                metadata={"run_id": result.run_id}
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
