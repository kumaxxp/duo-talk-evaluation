# Step4 実施開始通知 — Claude Code 宛

Cline（仕様管理）より指令：Claude Code は直ちに Step4（One‑Step 統合フロー実装）を開始せよ。

参照指示:
- 指示本体: docs/specs/CLAUDE_STEP4_PROMPT.md
- 実装ルール: docs/specs/PHASE4_IMPLEMENTATION_INSTRUCTIONS_FOR_CLAUDE.md
- 仕様: docs/specs/PHASE4_GUI_SPEC.md

要求事項（要約）
- One‑Step の非同期統合フローを `gui_nicegui/main.py` に実装すること。
- 再試行 N=2、タイムアウト core=5s director=5s gm=3s を実装すること。
- UI 進行表示、ログ、エラー通知、world_patch の適用を実装すること。
- 起動確認: `make gui` / `python -m gui_nicegui.main`、One‑Step 実行により Main Stage と God View に反映があること。

テスト／報告
- 完了報告は `docs/specs/STEP4_COMPLETION_REPORT.md` に上記フォーマットで記載すること。

運用ルール（厳守）
- PR作成禁止。コミットは可（コミットメッセージに "Phase4: Step4 completed" を含めること推奨）。
- 実装中は都度短報を出すこと。完了報告提出後に Cline が最終確認を行う。

発令:
- Step4 を直ちに開始せよ。完了報告提出まで次のステップには移行するな。