# 緊急指令：GM接続インジケータ修正（Claude Code 宛）

目的:
- GUI のヘッダにある GM バッジが常に灰色のままになる問題を修正する。起動時にヘルスチェックを行い、以後定期的に監視して UI をリアクティブに更新すること。

対象ファイル:
- src/gui_nicegui/main.py

必須実装（短命令）
1. app.on_startup でバックグラウンドタスクを開始
   - タスクは asyncio.create_task で起動する periodic health checker を回す
   - 間隔: 5秒
   - 呼び出し: await gm_client.get_health(use_mock=False) もしくは gm_client.get_health()
   - 成功時: `state.gm_connected = True`
   - 失敗時: `state.gm_connected = False`
   - タスクはエラーを swallow せずログを残す

2. UI のバッジを state に反応させる
   - ヘッダの GM バッジを次のいずれかでリアクティブ化
     - ui.timer（interval=1s）で badge の color を更新する方法（簡明）
     - あるいは NiceGUI の bind 機能で state.gm_connected に紐づける方法（推奨）
   - 色ルール: True → "green", False → "grey"

3. 追加要件
   - 起動直後に即時チェックを一回実行して状態を反映する
   - state.gm_connected の初期値は False
   - エラー時は ui.notify で短い警告を出す（頻発しないよう抑制）

例（テンプレート挿入案。main.py で適切箇所に差し替え）:

```python
# python
import asyncio
from nicegui import ui
from gui_nicegui.clients.gm_client import get_health  # adjust import path

# AppState に追加
class AppState:
    def __init__(self):
        ...
        self.gm_connected: bool = False

state = AppState()

async def _periodic_gm_health_check():
    try:
        while True:
            try:
                ok = await get_health()
                state.gm_connected = bool(ok and ok.get("status") == "ok")
            except Exception as e:
                state.gm_connected = False
                # ログ出力（既存のロガーを使うか ui.notify を出す）
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        return

# 起動時に開始
def create_app():
    ...
    # start background task on startup
    ui.run_safely(lambda: asyncio.create_task(_periodic_gm_health_check()))
    ...
    # ヘッダのバッジ生成例（reactive via ui.timer）
    with ui.header().classes("bg-blue-600"):
        ui.label("duo-talk Evaluation").classes("text-xl text-white font-bold")
        gm_badge = ui.badge("GM: Unknown").classes("ml-2 text-xs")
        # timer updates badge every 1s
        def _update_gm_badge():
            if state.gm_connected:
                gm_badge.set_props("color=green")
                gm_badge.set_text("GM: Online")
            else:
                gm_badge.set_props("color=grey")
                gm_badge.set_text("GM: Offline")
        ui.timer(1.0, _update_gm_badge)
```

完了報告（必須）
- ステップ: GMバッジ修正
- 編集ファイル: src/gui_nicegui/main.py (差分のみ)
- 実行コマンド: make gui
- 起動ログ抜粋: NiceGUI 起動行、初回 GM health 成功行
- UI確認: ブラウザでリロードして 5 秒以内に GM バッジが緑に変わる旨を記載

制約
- 実装は非破壊で行い、既存 Legacy タブ等を壊さないこと
- PR作成禁止。変更はコミット可能（"Phase4: fix gm badge" 推奨）

すぐに修正を開始して、上記完了報告を docs/specs/STEP_FIX_GM_BADGE_REPORT.md に提出せよ。