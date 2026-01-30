# Step2 実施開始通知 — Claude Code 宛

Cline（仕様管理）より指令：Claude Code は直ちに Step2（CoreAdapter 実装）を開始せよ。

参照指示:
- 指示本体: docs/specs/CLAUDE_STEP2_PROMPT.md
- 実装ルール: docs/specs/PHASE4_IMPLEMENTATION_INSTRUCTIONS_FOR_CLAUDE.md
- 仕様: docs/specs/PHASE4_GUI_SPEC.md

要求事項（要約）
- 新規ファイル: `gui_nicegui/adapters/core_adapter.py` を作成し、まずはモック実装を行うこと。
- API: async generate_thought(session_id, speaker, topic) / async generate_utterance(session_id, speaker, thought)
- タイムアウト: 初期値 5s（asyncio.wait_for を使用）
- UI 連携: Control Panel の「Generate Thought」「Generate Utterance」を core_adapter に接続し、成功時は AppState.dialogue_log を更新して Main Stage を再描画すること。
- テスト: `make gui` / `python -m gui_nicegui.main` で操作確認。完了報告は docs/specs/STEP2_COMPLETION_REPORT.md に上記フォーマットで記載すること。

運用ルール（厳守）
- PR作成禁止。コミットは可（コミットメッセージに "Phase4: Step2 completed" を含めること推奨）。
- 実装中は都度短報を出すこと。完了報告後に Cline が Step3 を指示する。

発令:
- Step2 の実装を開始せよ。完了報告提出まで次のステップには移行するな。