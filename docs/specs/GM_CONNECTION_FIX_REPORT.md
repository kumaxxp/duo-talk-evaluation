# 査察報告書: GM接続問題対策

**発信**: 情報参謀（Claude Desktop）  
**宛先**: 大本営参謀本部  
**Document ID**: INSPECTION-GM-FIX-001  
**査察日**: 2026年1月30日  

---

## 1. 問題概要

### 1.1 報告された問題

GUI起動時にGMバッジが緑色にならない。

### 1.2 根本原因（初回調査）

1. **GUI起動時にGM health checkが実行されていなかった**
2. **GMバッジがリアクティブ更新されていなかった**
3. **WorldStateスキーマの不一致**（gm_client.pyで修正済み）

---

## 2. 実施された対策

### 2.1 gm_client.py - WorldState変換修正

```python
# GUI形式からGM形式への変換ロジック追加
gm_request = {
    "world_state": {
        "version": "0.1",
        "time": {"label": time_label, "turn": turn_number},
        "location": {"current": current_loc},
        "locations": locations,
        "characters": characters,
        "props": props,
        "events": [],
    },
}
```

### 2.2 main.py - Health Check機構追加

```python
# 定数定義
GM_HEALTH_CHECK_INTERVAL = 5.0  # seconds

# Health check関数
async def _do_gm_health_check() -> None:
    try:
        result = await gm_get_health(use_mock=False)
        state.gm_connected = bool(result and result.get("status") == "ok")
    except Exception as e:
        state.gm_connected = False

# create_app()内のタイマー設定
ui.timer(GM_HEALTH_CHECK_INTERVAL, _do_gm_health_check)  # 5秒ごと定期実行
ui.timer(0.5, _do_gm_health_check, once=True)  # 起動時0.5秒後に初回実行
```

### 2.3 main.py - バッジリアクティブ更新

```python
# ヘッダーのGMバッジ
gm_badge = ui.badge("GM").props("color=grey outline")

def _update_gm_badge():
    if state.gm_connected:
        gm_badge.props("color=green outline")
    else:
        gm_badge.props("color=grey outline")

ui.timer(1.0, _update_gm_badge)  # 1秒ごとに更新

# Control PanelのGMバッジも同様に実装
```

---

## 3. 修正確認チェックリスト

| 項目 | 状態 | 備考 |
|:-----|:----:|:-----|
| WorldState変換ロジック | ✅ | gm_client.py |
| 起動時health check | ✅ | 0.5秒後に実行 |
| 定期health check | ✅ | 5秒間隔 |
| ヘッダーGMバッジ更新 | ✅ | 1秒間隔 |
| Control PanelのGMバッジ更新 | ✅ | 1秒間隔 |
| エラーログ抑制 | ✅ | 30秒に1回まで |

---

## 4. 動作確認手順

### Step 1: GMサービス起動

```bash
# ターミナル1
cd duo-talk-gm
set PYTHONPATH=src  # Windows
# export PYTHONPATH=src  # Linux/Mac
uvicorn duo_talk_gm.main:app --port 8001
```

### Step 2: Health Check確認

```bash
# ターミナル2
curl http://localhost:8001/health
# 期待: {"status":"ok","version":"0.1.0"}
```

### Step 3: GUI起動

```bash
# ターミナル3
cd duo-talk-evaluation
make gui
# または: python -m gui_nicegui.main
```

### Step 4: バッジ確認

1. ブラウザで `http://localhost:8080` にアクセス
2. 0.5秒後に初回health check実行
3. ヘッダーとControl PanelのGMバッジが緑色になることを確認

### 簡易起動（推奨）

```bash
make gui-with-gm  # GUI + GMを同時起動
```

---

## 5. トラブルシューティング

### バッジが緑にならない場合

| 確認項目 | 確認方法 |
|:---------|:---------|
| GMサービス起動確認 | `curl http://localhost:8001/health` |
| ポート競合確認 | `netstat -an | findstr 8001` (Windows) |
| Pythonパス確認 | `echo %PYTHONPATH%` (Windows) |
| ログ確認 | GMサービスのコンソール出力 |

### よくあるエラー

| エラー | 原因 | 対処 |
|:-------|:-----|:-----|
| Connection refused | GMサービス未起動 | `uvicorn duo_talk_gm.main:app --port 8001` |
| ModuleNotFoundError | PYTHONPATH未設定 | `set PYTHONPATH=src` |
| Address already in use | ポート競合 | 別プロセスを終了 |

---

## 6. 技術詳細

### 6.1 Health Check フロー

```
GUI起動
    │
    ├─ 0.5s後 ─→ _do_gm_health_check() [初回]
    │                │
    │                ├─ GET /health → 200 OK → state.gm_connected = True
    │                │
    │                └─ Exception → state.gm_connected = False
    │
    └─ 5s間隔 ─→ _do_gm_health_check() [定期]

バッジ更新
    │
    └─ 1s間隔 ─→ _update_gm_badge()
                     │
                     └─ state.gm_connected を参照してバッジ色を更新
```

### 6.2 WorldState変換マッピング

| GUI形式 | GM形式 |
|:--------|:-------|
| `current_location: str` | `location: {current: str}` |
| `time: "朝 7:00"` | `time: {label: "朝", turn: int}` |
| `characters: {name: {location, holding}}` | `characters: {name: {status, holding, location}}` |
| (なし) | `locations: {name: {description, exits}}` |
| (なし) | `props: {name: {location, state}}` |

---

## 7. 総合判定

| 項目 | 判定 |
|:-----|:----:|
| コード修正 | ✅ 完了 |
| WorldState変換 | ✅ 実装済 |
| 起動時health check | ✅ 実装済 |
| 定期health check | ✅ 実装済 |
| バッジリアクティブ更新 | ✅ 実装済 |

**結論**: GUI側の修正は完了。GMサービス起動後、正常動作を確認可能。

---

## 8. 関連ファイル

| ファイル | 修正内容 |
|:---------|:---------|
| `gui_nicegui/clients/gm_client.py` | WorldState変換ロジック追加 |
| `gui_nicegui/main.py` | Health check・バッジ更新追加 |

---

## 9. 次のアクション

1. **動作確認**: GMサービス起動 → GUI起動 → バッジ緑確認
2. **問題なければ**: Phase 4完了としてリリース承認
3. **v0.1.0-phase4タグ付け**

---

**修正完了を確認。動作確認後、Phase 4リリース可能。**

*情報参謀（Claude Desktop）*  
*2026年1月30日 於 旗艦司令部*
