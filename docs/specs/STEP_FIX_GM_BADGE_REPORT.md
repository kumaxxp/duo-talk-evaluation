# GM バッジ修正 完了報告

## ステップ
**GMバッジ修正** (緊急指令)

## 編集ファイル

### gui_nicegui/main.py

#### 変更1: GM ヘルスチェック関数追加 (L150-185)

```python
# GM health check configuration
GM_HEALTH_CHECK_INTERVAL = 5.0  # seconds
_last_gm_error_notify: float = 0  # Suppress frequent error notifications


async def _do_gm_health_check() -> None:
    """Perform a single GM health check (called by ui.timer)."""
    global _last_gm_error_notify
    import logging
    import time
    logger = logging.getLogger(__name__)

    try:
        result = await gm_get_health(use_mock=False)
        was_connected = state.gm_connected
        state.gm_connected = bool(result and result.get("status") == "ok")

        # Log state changes
        if state.gm_connected and not was_connected:
            logger.info("GM service: CONNECTED")
        elif not state.gm_connected and was_connected:
            logger.warning("GM service: DISCONNECTED")

    except Exception as e:
        state.gm_connected = False
        # Suppress frequent error notifications (max once per 30s)
        now = time.time()
        if now - _last_gm_error_notify > 30:
            _last_gm_error_notify = now
            logger.warning(f"GM health check failed: {e}")
```

#### 変更2: create_app() に GM ヘルスチェックタイマー追加

```python
def create_app():
    """Create the main application."""
    ui.page_title("HAKONIWA Console")

    # GM health check timer (runs every 5 seconds)
    ui.timer(GM_HEALTH_CHECK_INTERVAL, _do_gm_health_check)
    # Also do an immediate check on startup (after 0.5s to let UI initialize)
    ui.timer(0.5, _do_gm_health_check, once=True)
```

#### 変更3: ヘッダーの GM バッジをリアクティブ化

```python
# GM badge - reactive via ui.timer
gm_badge = ui.badge("GM").props("color=grey outline")

def _update_gm_badge():
    """Update GM badge color based on connection status."""
    if state.gm_connected:
        gm_badge.props("color=green outline")
    else:
        gm_badge.props("color=grey outline")

# Update badge display every 1 second
ui.timer(1.0, _update_gm_badge)
```

#### 変更4: Control Panel の GM バッジもリアクティブ化

```python
# GM badge - reactive via ui.timer
gm_badge_panel = ui.badge("GM").props("color=grey")

def _update_gm_badge_panel():
    """Update GM badge color based on connection status."""
    if state.gm_connected:
        gm_badge_panel.props("color=green")
    else:
        gm_badge_panel.props("color=grey")

ui.timer(1.0, _update_gm_badge_panel)
```

## 実行コマンド

```bash
# GUI 起動
make gui

# または直接実行
NICEGUI_PORT=8080 python -m gui_nicegui.main
```

## 起動ログ抜粋

```
NiceGUI ready to go on http://localhost:8080, http://172.17.0.1:8080, ...
```

## 実装内容

1. **定期ヘルスチェック**: `ui.timer(5.0, _do_gm_health_check)` で5秒ごとにGMサービスの `/health` エンドポイントをチェック

2. **初回即時チェック**: `ui.timer(0.5, _do_gm_health_check, once=True)` でUI初期化後0.5秒で初回チェック実行

3. **バッジリアクティブ更新**: `ui.timer(1.0, _update_gm_badge)` で1秒ごとにバッジ色を `state.gm_connected` に基づいて更新

4. **エラー抑制**: エラー通知は30秒に1回に制限（ログ爆発防止）

5. **状態変化ログ**: 接続/切断時にログ出力

## UI 確認

1. ブラウザで http://localhost:8080 にアクセス
2. GM サービスが起動している場合（`curl http://localhost:8001/health` で `{"status":"ok"}` を返す場合）
3. 起動後 5 秒以内に GM バッジが灰色から **緑色** に変化
4. GM サービスを停止すると 5 秒以内にバッジが **灰色** に戻る

## 技術的決定

- **`app.on_startup` 不使用**: NiceGUI のスクリプトモードでは `app.on_startup` が使用不可のため、`ui.timer` で代替実装
- **非同期関数対応**: NiceGUI の `ui.timer` は async 関数をネイティブサポート
- **2箇所のバッジ更新**: ヘッダーと Control Panel の両方で GM バッジをリアクティブに更新

---
**実施日時**: 2026-01-30
**実施者**: Claude Code
