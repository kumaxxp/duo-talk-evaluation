# Step2 実装指示（Claude Code 宛） — CoreAdapter 実装

目的: Step1 の UI に接続する形で CoreAdapter を実装し、Generate Thought / Generate Utterance の動作を可能にする。まずはモック実装で良いが、実運用を見据えたタイムアウト／例外ハンドリングを必須とする。

必須作業
1. 新規ファイル: `gui_nicegui/adapters/core_adapter.py`
   - API:
     ```python
     async def generate_thought(session_id: str, speaker: str, topic: str) -> dict:
         # returns {"thought": str, "tokens": int, "latency_ms": int}
     async def generate_utterance(session_id: str, speaker: str, thought: str) -> dict:
         # returns {"speech": str, "tokens": int, "latency_ms": int}
     ```
   - 実装はまずモックで良い（硬coded /ランダム文）。将来の実配備時は duo-talk-core の該当呼び出しをラップすること。

2. タイムアウト／例外処理
   - 内部で `asyncio.wait_for(..., timeout=5)` などを使いタイムアウトを設定（初期値: 5s）。
   - 例外発生時は適切な辞書を返すか例外を上位に伝搬させず、UIに通知できる形にする。

3. UI 連携
   - `gui_nicegui/main.py` の Control Panel のボタン `Generate Thought` / `Generate Utterance` を core_adapter の関数に接続すること。
   - 呼出時の処理:
     - ボタン押下 → 非同期タスク作成で呼出（ui側はブロッキングしない）
     - 成功時: AppState.dialogue_log に新しいターン / thought / speech を追加し `_refresh_main_stage()` を呼ぶ
     - 失敗時: ui.notify でエラーメッセージを表示し状態を壊さない

4. 出力フォーマット（UIへ反映する最小構造）
   - For Thought:
     ```
     {"turn": "T<n>", "speaker": speaker, "thought": "<text>", "status": "THOUGHT"}
     ```
   - For Utterance:
     ```
     {"turn": "T<n>", "speaker": speaker, "speech": "<text>", "status": "SPEECH"}
     ```

5. テスト/起動確認
   - コマンド: `make gui` または `python -m gui_nicegui.main`
   - 操作: Control Panel で Speaker を選び「Generate Thought」を押す
   - 期待表示: Main Stage に新しい Thought カードが追加され、Footer に短いログ（例: "Thought generated for やな"）が表示される

完了報告フォーマット（必須）
- ステップ番号: Step2
- 編集ファイル:
  - gui_nicegui/adapters/core_adapter.py
  - gui_nicegui/main.py（変更箇所のみ）
- 実行コマンド:
  - make gui
- 起動ログ抜粋:
  - 主要行を2〜3行
- UI 表示サンプル:
  - 生成された Thought / Utterance のテキスト（Main Stage に表示された最初の1件）
- 未解決事項（あれば）

注意
- PRは作成しない。コミットは可（メッセージに "Phase4: Step2 completed" を含めること推奨）。
- 仕様（docs/specs/PHASE4_GUI_SPEC.md）に従うこと。
- 実装報告は必ず上記フォーマットで返すこと。