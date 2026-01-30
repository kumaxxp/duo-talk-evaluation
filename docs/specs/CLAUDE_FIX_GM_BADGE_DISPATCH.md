# Step: Fix GM Badge — 実装開始通知（Claude Code 宛）

Cline（仕様管理）より指令：Claude Code は直ちに `src/gui_nicegui/main.py` の GM バッジ不具合を修正せよ。

参照指示:
- 指示本体: docs/specs/CLAUDE_FIX_GM_BADGE_PROMPT.md
- 実装ルール: docs/specs/PHASE4_IMPLEMENTATION_INSTRUCTIONS_FOR_CLAUDE.md
- 仕様: docs/specs/PHASE4_GUI_SPEC.md

要求概要
- 追加: app.on_startup で periodic health checker を asyncio.create_task で起動（間隔 5s）。
- 呼出: gm_client.get_health(use_mock=False) を用い、state.gm_connected を True/False に更新。
- UI: ヘッダの GM バッジを state の更新に応じてリアクティブに色/テキストを変更（ui.timer または bind を利用）。
- 初回起動時に即時チェックを実行して状態を反映。
- state.gm_connected の初期値は False。
- エラーはログ出力し、頻発notifyは抑制する。

完了報告（必須）
- ステップ: GMバッジ修正
- 編集ファイル: src/gui_nicegui/main.py（差分のみ）
- 実行コマンド: make gui
- 起動ログ抜粋: NiceGUI起動行、初回GM health成功行
- UI確認: ブラウザでリロードして 5秒以内にGMバッジが緑に変わる旨を記載

運用ルール
- PR作成禁止。コミット可（"Phase4: fix gm badge" 推奨）。
- 実装は非破壊で行うこと。

発令:
- 直ちに実装を開始せよ。完了報告は docs/specs/STEP_FIX_GM_BADGE_REPORT.md に提出すること。