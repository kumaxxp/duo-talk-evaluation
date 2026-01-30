# Step1 実装指示（Claude Code 宛）

目的: Step1（レイアウトの枠組み作成）を実装し、ローカルで起動確認できる状態にする。

必須作業
1. `gui_nicegui/main.py` を編集（既存をリファクタ可）。変更点:
   - AppState に次を追加:
     - dialogue_log: list（ダミー会話を複数含める）
     - director_status: dict
     - world_state_summary: dict
     - action_logs: list
   - 画面を 3 ペイン表示に変更（左: Control Panel / 中央: Main Stage / 右: God View）
   - 各ペインにダミーデータを表示する（Main Stage は会話カードを3件以上表示）

2. 起動確認手順（必ず実行して出力を含めて報告）
   - コマンド: `make gui` または `python -m gui_nicegui.main`
   - 起動成功時は UI が `http://localhost:8080` で開き、左/中/右ペインが確認できること
   - 返信報告に以下を含める:
     - ステップ: Step1
     - 編集したファイル一覧（相対パス）
     - 実行コマンドと主要出力行（起動ログの主要テキスト。例: "Ready", "Listening on port 8080"）
     - Main Stage に表示された最初の会話カードのテキスト（例: "T1 やな: こんにちは..."）
     - 未解決事項（あれば）

制約
- PRは作成しない。コミットは可（コミットメッセージに "Phase4: Step1 completed" を含める）。
- 仕様書 `docs/specs/PHASE4_GUI_SPEC.md` を遵守すること。
- 実装は非破壊で行い、既存機能を壊さないこと。

報告形式（必須）
- ステップ番号: Step1
- 編集ファイル:
  - - path/to/file.py
- 実行コマンド:
  - make gui
- 起動ログ抜粋:
  - [例] "Running on http://0.0.0.0:8080"
- Main Stage サンプル表示:
  - T1 | やな | 思考: "..." | 発話: "..."
- 未解決事項:
  - なし（または内容を列挙）

すぐに Step1 を開始し、上記フォーマットで完了報告を返せ。