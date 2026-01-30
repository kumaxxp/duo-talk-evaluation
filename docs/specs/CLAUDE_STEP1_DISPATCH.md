# Step1 実施開始通知 — Claude Code 宛

Cline（仕様管理）は仕様書の承認を受領したため、Claude Code は直ちに Step1（レイアウト枠組み作成）を開始せよ。

参照指示:
- 指示本体: docs/specs/CLAUDE_STEP1_PROMPT.md
- 実装ルール: docs/specs/PHASE4_IMPLEMENTATION_INSTRUCTIONS_FOR_CLAUDE.md
- 仕様: docs/specs/PHASE4_GUI_SPEC.md

要求事項（要約）
- gui_nicegui/main.py を編集し、3ペイン（Control Panel / Main Stage / God View）を表示する雛形を実装すること。
- AppState に dialogue_log, director_status, world_state_summary, action_logs を追加し、ダミーデータで起動確認できること。
- 起動確認コマンド: `make gui` または `python -m gui_nicegui.main`
- 完了報告には必ず以下を含めること:
  - ステップ番号: Step1
  - 編集したファイル一覧（相対パス）
  - 実行コマンドと起動ログ抜粋
  - Main Stage に表示された最初の会話カードのテキスト
  - 未解決事項（あれば）

運用ルール（厳守）
- PRは作成せず、コミットは可（コミットメッセージに "Phase4: Step1 completed" を含めることを推奨）。
- 実装完了報告は上記フォーマットでこのリポジトリ内のドキュメントに追記し、Clineに通知すること。

発令:
- Step1 の実装を開始せよ。完了報告を提出するまで次のステップには移行しないこと。