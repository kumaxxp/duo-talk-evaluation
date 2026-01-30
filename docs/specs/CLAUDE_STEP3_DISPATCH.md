# Step3 実施開始通知 — Claude Code 宛

Cline（仕様管理）より指令：Claude Code は直ちに Step3（DirectorAdapter と GMClient 実装）を開始せよ。

参照指示:
- 指示本体: docs/specs/CLAUDE_STEP3_PROMPT.md
- 実装ルール: docs/specs/PHASE4_IMPLEMENTATION_INSTRUCTIONS_FOR_CLAUDE.md
- 仕様: docs/specs/PHASE4_GUI_SPEC.md

要求事項（要約）
- 新規ファイル: `gui_nicegui/adapters/director_adapter.py` と `gui_nicegui/clients/gm_client.py` を作成すること（まずはモック実装）。
- DirectorAdapter API: async def check(stage, content, context) -> dict（PASS/RETRY 等を返す）。
- GMClient API: async def post_step(payload) -> dict / async def get_health() -> dict（httpx と timeout=3s を推奨）。
- UI連携: Main Stage に判定バッジ表示、RETRY は差分表示、God View に world_patch を反映し Action Log を追加すること。
- 再試行表示: retry_count が UI に反映されること。

テスト／報告
- 起動コマンド: `make gui` または `python -m gui_nicegui.main`
- 完了報告は `docs/specs/STEP3_COMPLETION_REPORT.md` に所定フォーマットで記載すること。

運用ルール（厳守）
- PR作成禁止。コミットは可（コミットメッセージに "Phase4: Step3 completed" を含めること推奨）。
- 実装中は都度短報を出すこと。完了報告提出後に Cline が Step4 を指示する。

発令:
- Step3 を直ちに開始せよ。完了報告提出まで次のステップには移行するな。