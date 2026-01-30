# Step4 実装指示（Claude Code 宛） — One-Step 統合フロー実装

目的: Step1〜Step3 の実装を統合し、UI上の操作で Thought→Director Check→Utterance→Director Check→GM /step までの One‑Step フローを動作させる。再試行・タイムアウト・エラーハンドリングを実装し、End-to-End の手動確認が可能な状態にする。

必須作業
1. 主要統合ロジック（`gui_nicegui/main.py`）
   - Control Panel に「One‑Step」ボタンを追加し、押下で非同期タスクを起動する。
   - One‑Step の非同期フロー:
     1. core_adapter.generate_thought(...)
     2. director_adapter.check("thought", thought, ctx)
        - status == "RETRY" → repaired_output があれば使用、なければ再生成（最大再試行 N=2）
     3. core_adapter.generate_utterance(...)
     4. director_adapter.check("speech", speech, ctx)
        - status == "RETRY" → repaired_output があれば使用、なければ再生成（最大再試行 N=2）
     5. gm_client.post_step({utterance, speaker, world_state?}) → gm_res
     6. AppState に dialogue_log/world_state_summary/action_logs を更新し UI を再描画

2. 再試行・タイムアウト方針（実装必須）
   - Director 指示の RETRY に対し最大再試行回数 N=2 を実施。
   - 各外部呼出（core, director, gm）にタイムアウトを設定（初期値: core 5s, director 5s, gm 3s）。
   - タイムアウト・例外発生時は UI に通知（ui.notify）し、AppState を一貫した状態に戻す。

3. UI 表示更新
   - One‑Step 実行中は Control Panel にスピナー/進行インジケータを表示。
   - 各ターンで Director 判定（PASS/RETRY）と retry_count を Main Stage のカードに反映。
   - GM の world_patch を要約表示（God View）し、Action Log に追加。
   - 成功/失敗のサマリ通知を表示。

4. ロギング & エラー報告
   - ローカルログ（state.log_output）に主要イベントを追記（例: "Thought generated (latency 120ms)", "Director RETRY (reason...)"）。
   - UI 上の Footer で最新行を表示。

5. テスト / 起動確認手順
   - コマンド: `make gui` または `python -m gui_nicegui.main`
   - 操作:
     - Control Panel で Speaker を選択し「One‑Step」を押す
     - 期待: Main Stage に新しいターンが追加され、Director 判定が反映、God View に world_state の更新がある
   - 失敗時の期待表示: ui.notify にエラーメッセージ、retry カウントの表示、state.rollback（不整合防止）

6. 完了報告フォーマット（必須）
   - ステップ番号: Step4
   - 編集ファイル:
     - gui_nicegui/main.py（One‑Step 統合フロー）
     - gui_nicegui/adapters/core_adapter.py（必要修正）
     - gui_nicegui/adapters/director_adapter.py（必要修正）
     - gui_nicegui/clients/gm_client.py（必要修正）
   - 実行コマンド:
     - make gui
   - 起動ログ抜粋: 主要行2〜3行
   - UI 表示サンプル:
     - One‑Step 実行の Main Stage 表示（最初の1件）
     - God View に反映された world_state 要約
   - 未解決事項（あれば）
   - 報告先: `docs/specs/STEP4_COMPLETION_REPORT.md`

注意事項
- PR作成禁止。コミットは可（コミットメッセージに "Phase4: Step4 completed" を含めること推奨）。
- 実装は仕様書 `docs/specs/PHASE4_GUI_SPEC.md` に厳密に従うこと。
- 実装完了報告を受領後、Cline が最終確認し「Definition of Done」を検証する。

すぐに Step4 を開始し、完了報告を上記フォーマットで提出せよ。