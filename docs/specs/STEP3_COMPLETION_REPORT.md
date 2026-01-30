# Step3 完了報告

## ステップ番号
**Step3: DirectorAdapter と GMClient 実装**

## 編集ファイル
- `gui_nicegui/adapters/director_adapter.py` (新規作成)
- `gui_nicegui/adapters/__init__.py` (更新)
- `gui_nicegui/clients/__init__.py` (新規作成)
- `gui_nicegui/clients/gm_client.py` (新規作成)
- `gui_nicegui/main.py` (UI連携追加)

## 実施内容

### 1. gui_nicegui/adapters/director_adapter.py (新規作成)
DirectorAdapter モジュールを実装:

```python
async def check(stage: str, content: str, context: dict, timeout: float = 5.0) -> DirectorCheckResponse
# Returns:
#   status: "PASS" | "RETRY"
#   reasons: list[str]
#   repaired_output: Optional[str]
#   injected_facts: Optional[list[dict]]
#   latency_ms: int
```

実装詳細:
- モック実装（短いコンテンツ → RETRY、長いコンテンツ → PASS傾向）
- RETRY時の修復パターン（やな/あゆ用テンプレート）
- `asyncio.wait_for` によるタイムアウト（5秒）
- 理由リストとファクト注入をモック生成

### 2. gui_nicegui/clients/gm_client.py (新規作成)
GMClient モジュールを実装:

```python
async def post_step(payload: dict, timeout: float = 3.0, use_mock: bool = True) -> GMResponse
async def get_health(timeout: float = 3.0, use_mock: bool = True) -> HealthResponse
```

実装詳細:
- モック実装（world_patch、actions、logsをランダム生成）
- httpx による実HTTP実装（use_mock=False時）
- タイムアウト3秒
- GM_BASE_URL = "http://localhost:8001"

### 3. main.py UI連携追加

新規ハンドラ関数:
- `_handle_director_check()` - 最新ダイアログエントリをDirectorでチェック
- `_handle_gm_step()` - GMにステップを適用、world_stateを更新

新規UI要素:
- Control Panel に「Check (Director)」ボタン追加
- Control Panel に「Apply Step (GM)」ボタン追加
- God View をリフレッシュ可能に変更（`_refresh_god_view()`）

状態更新:
- Director判定結果を `dialogue_log` エントリに保存
- `director_status.retry_count` をインクリメント
- `world_state_summary` に `world_patch` を適用
- `action_logs` に新規アクションを追加

## 実行コマンド
```bash
make gui
# または
python -m gui_nicegui.main
```

## 起動ログ抜粋
```
NiceGUI ready to go on http://localhost:8080, ...
```

## アダプタ動作確認

### Director Check (短いコンテンツ → RETRY)
```
status: RETRY
reasons: ['キャラクター口調の逸脱を検出']
repaired_output: あゆの寝癖、可愛いよ？
latency_ms: 213
```

### Director Check (長いコンテンツ → PASS)
```
status: PASS
latency_ms: 72
```

### GM Post Step
```
actions: [{'action': 'MOVE', 'actor': 'やな', 'target': 'リビング', 'result': 'SUCCESS'}]
world_patch: {'characters': {'やな': {'holding': ['コーヒーカップ']}}, 'changes': ['やながコーヒーカップを手に取った']}
latency_ms: 94
```

### GM Health
```
status: ok
```

## UI 表示サンプル

### Director判定後（RETRY表示）
| 項目 | 内容 |
|------|------|
| Turn | T3 |
| Speaker | やな |
| Status | RETRY (オレンジバッジ、オレンジ枠線) |
| Raw | 可愛い |
| Repaired | あゆの寝癖、可愛いよ？ |

### God View 更新後
```
World State:
  Location: リビング
  Time: 朝 7:30
  やな: 寝室 [holding: コーヒーカップ]
  あゆ: 寝室 [holding: (none)]

Recent Changes:
  • やながコーヒーカップを手に取った
  • やなが起床した

Action Log:
  T3 | MOVE | やな: やな → リビング
  T2 | WAKE_UP | あゆ: あゆが起床しました
  T1 | WAKE_UP | やな: やなが起床しました
```

## フロー確認

1. **Check (Director) ボタン押下**
   - 最新ダイアログエントリの speech/thought を Director に送信
   - PASS → 緑バッジ、ステータス更新
   - RETRY → オレンジバッジ、raw/repaired差分表示、retry_count増加
   - God View の Director Status 欄を更新

2. **Apply Step (GM) ボタン押下**
   - 最新発話を GM /step に送信
   - world_patch を world_state_summary に適用
   - action_logs に新規アクション追加
   - God View の World State と Action Log を再描画
   - gm_connected を true に更新

3. **エラーハンドリング**
   - タイムアウト → エラー通知
   - 生成中ロック → 警告表示

## 未解決事項
- なし

## 次のステップ
Step4: One-Step 統合フロー実装

---
**実施日時**: 2026-01-30
**実施者**: Claude Code
