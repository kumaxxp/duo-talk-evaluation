# Step4 完了報告

## ステップ番号
**Step4: One-Step 統合フロー実装**

## 編集ファイル
- `gui_nicegui/main.py` (One-Step 統合フロー追加)

## 実施内容

### 1. One-Step 設定定数の追加

```python
ONE_STEP_MAX_RETRIES = 2
ONE_STEP_TIMEOUT_CORE = 5.0
ONE_STEP_TIMEOUT_DIRECTOR = 5.0
ONE_STEP_TIMEOUT_GM = 3.0
```

仕様に基づくタイムアウト・リトライ設定:
- Core (Thought/Utterance): 5秒
- Director (Check): 5秒
- GM (Step): 3秒
- 最大リトライ: N=2

### 2. ヘルパー関数の追加

```python
def _apply_world_patch(patch: dict) -> None:
    """Apply GM world_patch to state.world_state_summary."""
    # current_location, time, characters, changes を適用
```

### 3. `_handle_one_step()` 非同期統合フロー実装

全6フェーズの非同期処理:

```
Phase 1: Generate Thought (Core)
    ↓
Phase 2: Director Check (Thought) → RETRY時は repaired_output または再生成
    ↓
Phase 3: Generate Utterance (Core)
    ↓
Phase 4: Director Check (Speech) → RETRY時は repaired_output または再生成
    ↓
Phase 5: GM Step → world_patch 適用
    ↓
Phase 6: Update State & UI
```

実装詳細:
- `asyncio.wait_for` による各フェーズのタイムアウト制御
- Thought/Speech それぞれで最大2回のリトライ
- `repaired_output` がある場合は採用、なければ再生成
- リトライ毎に `director_status.retry_count` をインクリメント
- 最終ステータスは最後のDirector Check結果で決定
- 全フェーズ完了後に `_refresh_main_stage()` と `_refresh_god_view()` を呼び出し

### 4. UI 進行表示

`state.log_output` に各フェーズの進行状況を表示:
```
[One-Step] Starting for やな...
[One-Step] Generating thought for やな...
[One-Step] Thought generated (XXms)
[One-Step] Checking thought...
[One-Step] Thought PASS (XXms)
[One-Step] Generating utterance...
[One-Step] Utterance generated (XXms)
[One-Step] Checking speech...
[One-Step] Speech PASS (XXms)
[One-Step] Applying GM step...
[One-Step] GM step applied (XXms)
[One-Step] Complete! TX やな (PASS)
```

### 5. エラーハンドリング

```python
try:
    # 6フェーズの処理
except asyncio.TimeoutError as e:
    state.log_output = f"[One-Step] Timeout: {e}"
    ui.notify(f"One-Step timeout: {e}", type="negative")
except Exception as e:
    state.log_output = f"[One-Step] Error: {e}"
    ui.notify(f"One-Step error: {e}", type="negative")
finally:
    state.generating = False
```

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

## One-Step 実行フロー確認

### 1. One-Step ボタン押下時の処理

| フェーズ | 処理 | タイムアウト | リトライ |
|---------|------|-------------|----------|
| Phase 1 | Thought 生成 | 5秒 | - |
| Phase 2 | Director Check (Thought) | 5秒 | 最大2回 |
| Phase 3 | Utterance 生成 | 5秒 | - |
| Phase 4 | Director Check (Speech) | 5秒 | 最大2回 |
| Phase 5 | GM Step 適用 | 3秒 | - |
| Phase 6 | UI 更新 | - | - |

### 2. RETRY 時の挙動

1. Director が `status: "RETRY"` を返却
2. `repaired_output` があれば採用
3. なければ Core で再生成
4. `director_status.retry_count` をインクリメント
5. 最大2回まで繰り返し

### 3. UI 更新

One-Step 完了時:
- Main Stage: 新しいダイアログエントリが追加される
- God View: World State と Action Log が更新される
- Footer: 進行状況ログが表示される
- 通知: 成功/警告/エラーに応じた通知が表示される

### 4. 完了通知パターン

| 条件 | 通知タイプ | メッセージ例 |
|------|-----------|-------------|
| PASS (リトライなし) | positive | "One-Step complete: T4 やな - PASS" |
| PASS (リトライあり) | positive | "One-Step complete (T4, 1 retries)" |
| RETRY (最大リトライ後) | warning | "One-Step complete (T4, 2 retries)" |
| Timeout | negative | "One-Step timeout: ..." |
| Error | negative | "One-Step error: ..." |

## Main Stage 表示サンプル

One-Step 実行後:
```
┌─────────────────────────────────────────────────┐
│ [T4] [やな] [PASS]                              │
│                                                  │
│ ▸ Thought                                        │
│   今日も妹と過ごせて幸せだな。                  │
│                                                  │
│ 「今日は何をしようか、あゆ〜」                  │
└─────────────────────────────────────────────────┘
```

## God View 更新サンプル

One-Step 実行後:
```
World State:
  Location: リビング
  Time: 朝 7:30
  やな: 寝室 [holding: コーヒーカップ]
  あゆ: 寝室 [holding: (none)]

Recent Changes:
  • やながコーヒーカップを手に取った
  • やなとあゆがリビングに移動した

Action Log:
  T4 | MOVE | やな: やな → リビング
  T3 | MOVE | やな: やな → リビング
  T2 | WAKE_UP | あゆ: あゆが起床しました
  T1 | WAKE_UP | やな: やなが起床しました
```

## 設定定数一覧

| 定数名 | 値 | 説明 |
|--------|-----|------|
| ONE_STEP_MAX_RETRIES | 2 | Director RETRY 時の最大再試行回数 |
| ONE_STEP_TIMEOUT_CORE | 5.0 | Core (Thought/Utterance) タイムアウト秒 |
| ONE_STEP_TIMEOUT_DIRECTOR | 5.0 | Director Check タイムアウト秒 |
| ONE_STEP_TIMEOUT_GM | 3.0 | GM Step タイムアウト秒 |

## 未解決事項
- なし

## 次のステップ
Step5 以降の実装（Cline 仕様管理による指示待ち）

---
**実施日時**: 2026-01-30
**実施者**: Claude Code
