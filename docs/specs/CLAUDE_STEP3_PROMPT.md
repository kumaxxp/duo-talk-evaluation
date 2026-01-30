# Step3 実装指示（Claude Code 宛） — DirectorAdapter と GMClient 実装

目的: Step2 の CoreAdapter と UI を踏まえ、Director（判定）と GM（ワールド管理）との接続を実装して One-Step フローの中盤を機能させる。まずはモック実装で良いが、将来の実配備を見据えた API 仕様・タイムアウト・エラーハンドリングを必須とする。

必須作業
1. 新規ファイル
   - `gui_nicegui/adapters/director_adapter.py`
   - `gui_nicegui/clients/gm_client.py`

2. DirectorAdapter API（モック実装可）
   ```python
   async def check(stage: str, content: str, context: dict) -> dict:
       # returns {
       #   "status": "PASS" | "RETRY",
       #   "reasons": list[str],
       #   "repaired_output": Optional[str],
       #   "injected_facts": Optional[list[dict]],
       #   "latency_ms": int
       # }
   ```
   - タイムアウト: asyncio.wait_for(..., timeout=5)
   - RETRY の場合は `repaired_output` を返すモックパターンを用意すること（UIで差分を確認できるように）。

3. GMClient API（HTTP クライアント）
   ```python
   async def post_step(payload: dict) -> dict:
       # POST /step に相当。returns {"actions": [...], "world_patch": {...}, "logs": [...]}
   async def get_health() -> dict:
       # GET /health -> {"status":"ok"}
   ```
   - 実装に httpx を推奨。timeout=3s を適用。
   - GM サーバが無い場合はモックで world_patch と logs を返すこと。

4. UI 連携
   - Director 判定を Main Stage の各会話カードにバッジ表示（PASS=緑、RETRY=オレンジ）。
   - RETRY の場合はカードに Raw / Repaired 差分を表示する UI を用意（既存差分コンポーネントを利用）。
   - God View にて world_state_summary を `world_patch` から更新し、Action Log を先頭に追加する。
   - Control Panel の One-Step（Step4で統合）呼出の事前条件として Director.check と GMClient.post_step が機能すること。

5. 再試行方針（Director 指示への対応）
   - Director が RETRY を返した場合、Step4 実行時は最大 N=2 回まで再試行する仕様を満たす形で、ここでは UI に retry_count の増減が反映されるようにする。

6. テスト / 起動確認
   - コマンド: `make gui` または `python -m gui_nicegui.main`
   - 操作:
     - Main Stage の既存ダミーカードを選択し、Director.check を手動トリガ（UI上の「Check」ボタンを追加して呼べるようにする）して判定結果が表示されること。
     - God View の「Apply Patch」操作または自動反映により world_state_summary が更新され、Action Log にエントリが追加されること。
   - 期待表示例:
     - Director 判定: "PASS"（緑バッジ）
     - Director 判定: "RETRY"（オレンジバッジ）→ 差分表示あり
     - GM world update: Location: "kitchen" → "living_room"（要約表示）

完了報告フォーマット（必須）
- ステップ番号: Step3
- 編集ファイル:
  - gui_nicegui/adapters/director_adapter.py
  - gui_nicegui/clients/gm_client.py
  - gui_nicegui/main.py（UI接続箇所）
- 実行コマンド:
  - make gui
- 起動ログ抜粋: 主要行2〜3行
- UI 表示サンプル:
  - 直近 Director 判定（例: T3 | やな | RETRY | repaired: "..."）
  - God View に反映された world_state 要約（例: Location: hall）
- 未解決事項（あれば）

注意事項
- PR作成禁止。コミットは可（メッセージに "Phase4: Step3 completed" を含めること推奨）。
- 既存コンポーネントを再利用し、UIの破壊を避けること。
- 実装後、完了報告を docs/specs/STEP3_COMPLETION_REPORT.md に記載して Cline に通知すること。