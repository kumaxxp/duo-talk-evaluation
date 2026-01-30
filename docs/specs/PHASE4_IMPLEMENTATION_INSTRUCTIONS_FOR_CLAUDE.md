# 実装指示書（Claude Code 宛） — Phase 4: HAKONIWA Console 実装

目的: Cline（仕様管理）が承認した `docs/specs/PHASE4_GUI_SPEC.md` に従い、Claude Code は GUI 実装（Step1〜Step4）を順次実装し、ローカルで稼働させること。PRは作成せず、変更はリポジトリ内に直接反映する（ただし必ず仕様と整合を取る）。

重要ルール
- まず仕様（docs/specs/PHASE4_GUI_SPEC.md）を全文熟読すること。仕様が絶対。
- 実装は段階的に行い、各ステップ完了ごとに短報（変更ファイル一覧・起動コマンド・確認手順）をClineに提示すること。
- PR作成禁止。コミットは可（必要ならコミットメッセージに「Phase4: Step X completed」と明記）。
- テストと手順は必須。起動確認はローカルで行う（make gui または python -m gui_nicegui.main）。

成果物（各ステップで期待する最小限）
- Step1: 3ペインのレイアウト雛形、AppState の基本プロパティとダミーデータ表示
  - ファイル: gui_nicegui/main.py（既存をリファクタ）、必要なら gui_nicegui/components/* を追加
  - 起動確認: UI が http://localhost:8080 で開き、左/中/右ペインが確認できること
- Step2: CoreAdapter の薄ラップ（モックを含む）、Generate Thought / Utterance ボタン動作
  - ファイル: gui_nicegui/adapters/core_adapter.py
  - 起動確認: Generate Thought を押すとダミー Thought が Main Stage に表示されること
- Step3: DirectorAdapter と GM クライアントの実装、判定バッジと world_patch 表示
  - ファイル: gui_nicegui/adapters/director_adapter.py, gui_nicegui/clients/gm_client.py
  - 起動確認: One-Step 実行で Director 判定（PASS/RETRY）が表示され、GM があれば world_state が更新されること
- Step4: 完全な One-Step フロー、エラー処理、タイムアウト、再試行（N=2）
  - 起動確認: 実際の Core/Director/GM 接続（実機/モック）で End-to-End が動くこと
- ドキュメント: 実装差分と起動手順を docs/specs/PHASE4_GUI_IMPL_NOTES.md に記載

実装手順（Claude 用短手順）
1. 準備
   - リポジトリを最新化し、ローカルでテスト環境を準備する。
   - 依存が増える場合は pyproject.toml に追記し、pip install -e . を行う旨を報告。

2. Step1 — レイアウト雛形
   - 既存 `gui_nicegui/main.py` をバックアップしつつ編集。
   - AppState に以下最小プロパティを追加:
     - dialogue_log: list
     - director_status: dict
     - world_state_summary: dict
     - action_logs: list
   - 左: Control Panel（Profile, Speaker, Buttons）
   - 中央: Main Stage（dialogue_log をカード表示）
   - 右: God View（world_state_summary と action_logs）
   - ダミーデータを用いて UI 表示を確認できるようにする。

   例（変更後の起動確認コマンド）:
   ```bash
   make gui
   # または
   python -m gui_nicegui.main
   ```
   確認ポイント:
   - 3ペインが表示される
   - ダミー会話が中央に表示される

3. Step2 — CoreAdapter 実装
   - 新規ファイル: `gui_nicegui/adapters/core_adapter.py`
   - API:
     ```python
     # python
     async def generate_thought(session_id: str, speaker: str, topic: str) -> dict:
         return {"thought": "...", "tokens": 0, "latency_ms": 10}
     async def generate_utterance(session_id: str, speaker: str, thought: str) -> dict:
         return {"speech": "...", "tokens": 0, "latency_ms": 10}
     ```
   - まずは内部でモックを返す形で実装し、UIから呼べることを確認する。
   - 例外・タイムアウトを捕捉し、UIに通知するロジックを追加。

4. Step3 — DirectorAdapter と GMClient
   - `gui_nicegui/adapters/director_adapter.py`
     - `async def check(stage: str, content: str, context: dict) -> dict` を実装（最初はモックで PASS/RETRY を返す）。
   - `gui_nicegui/clients/gm_client.py`
     - `async def post_step(payload: dict) -> dict` を実装（GM サーバーがない場合はモック world_patch を返す）。
     - 実装時には `httpx` 等を使い timeout を設定。
   - UI 表示: Director の判定をバッジ化、raw→repaired 差分表示、God View に world_patch を適用して要約を更新。

5. Step4 — 統合フローと運用機能
   - One-Step 実装: Core → Director(check) → Core → Director(check) → GM(post_step)
   - Director が `RETRY` を返したら最大 N=2 回まで再試行（repaired_output があれば優先）。
   - タイムアウト値: Core/Director 3~10s、GM 3s（仕様に準拠）。
   - エラーハンドリング: UI に notify、state を一貫性のある状態に戻す。
   - 設定 UI（Profile, RAG on/off）を実装し、CoreAdapter/DirectorAdapter 呼出時に反映する。

6. テストと確認
   - 主要フローの手動テスト手順をClineに提示する（起動コマンド、ボタン操作手順、期待されるUI表示）。
   - `tests/test_gui_components.py` を必要に応じて更新してユニットテストを追加。
   - 実装報告には「編集ファイル一覧」「起動コマンド」「確認手順」「未解決事項」を含めること。

出力フォーマット（各ステップ完了報告で必須）
- ステップ番号
- 編集したファイル一覧（パス）
- 実行したコマンドと出力要約
- 起動確認のスクリーンショットの代替として、UI 上の主要テキスト出力（例: "Ready", "Thought: ..."）を貼る
- 未解決事項（あれば）

短い例プロンプト（Claude に送る際のテンプレート）
- 「Step1 実施開始。`gui_nicegui/main.py` を編集して 3 ペイン雛形を追加し、AppState に dialogue_log/director_status/world_state_summary/action_logs を追加せよ。ダミーデータを用意して make gui で左/中/右ペインが見えることを確認して報告せよ。変更ファイルを一覧で出し、起動時の主要UIテキストを貼れ。」

最後に
- 実装中は都度短報を出すこと（完了報告→次指示をClineが出す流れ）。
- まずは Step1 の実装指示を受けて着手せよ。完了後、Cline が次の実装指示を出す。