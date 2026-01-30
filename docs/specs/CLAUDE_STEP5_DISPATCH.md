# Step5 実施開始通知 — Claude Code 宛

Cline（仕様管理）より指令：Claude Code は直ちに Step5（Real Integration：Core/Director/GMの実接続）を開始せよ。

参照指示:
- 指示本体: docs/specs/CLAUDE_STEP5_PROMPT.md
- 実装ルール: docs/specs/PHASE4_IMPLEMENTATION_INSTRUCTIONS_FOR_CLAUDE.md
- 仕様: docs/specs/PHASE4_GUI_SPEC.md

要求概要（要点）
- 編集対象:
  - src/gui_nicegui/adapters/core_adapter.py
  - src/gui_nicegui/adapters/director_adapter.py
  - src/gui_nicegui/clients/gm_client.py
- Core/Director: duo-talk-core / duo-talk-director の実クラスをインポートして利用。ImportError時は既存Mockへフォールバックすること。
- GM: httpx.AsyncClient で `http://localhost:8001` に対し非同期で GET /health, POST /step を実装（timeout=3s）。
- 非同期化: 同期APIの呼出は asyncio.to_thread でラップ。
- タイムアウト/リトライ/エラーハンドリングは docs/specs/PHASE4_GUI_SPEC.md の方針に従う。
- E2E検証手順を実行し、結果を docs/specs/STEP5_COMPLETION_REPORT.md に提出すること。

運用ルール（厳守）
- PR禁止。コミットは可（推奨メッセージ: \"Phase4: Step5 completed\"）。
- 実装前に duo-talk-gm が起動可能であることを確認し、起動手順を報告すること。
- 完了報告は指定フォーマットに沿って短報で行うこと。

発令:
- Step5 を直ちに開始せよ。完了報告提出まで次のステップには移行するな。