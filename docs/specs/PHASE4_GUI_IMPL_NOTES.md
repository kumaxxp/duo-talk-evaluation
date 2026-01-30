# Phase 4 GUI 実装ノート

## 起動手順

```bash
# 方法1: Makefile
make gui

# 方法2: Python 直接実行
source ~/miniconda3/etc/profile.d/conda.sh
conda activate duo-talk
python -m gui_nicegui.main
```

起動後: http://localhost:8080

## 実装ステップ概要

| Step | 内容 | 主要ファイル |
|------|------|-------------|
| Step1 | 3ペインレイアウト + AppState | gui_nicegui/main.py |
| Step2 | CoreAdapter (Thought/Utterance) | gui_nicegui/adapters/core_adapter.py |
| Step3 | DirectorAdapter + GMClient | gui_nicegui/adapters/director_adapter.py, gui_nicegui/clients/gm_client.py |
| Step4 | One-Step 統合フロー | gui_nicegui/main.py |

## 実装差分 (Step4)

### 追加定数
```python
ONE_STEP_MAX_RETRIES = 2
ONE_STEP_TIMEOUT_CORE = 5.0
ONE_STEP_TIMEOUT_DIRECTOR = 5.0
ONE_STEP_TIMEOUT_GM = 3.0
```

### 新規関数
- `_apply_world_patch(patch)`: GM world_patch を state に適用
- `_handle_one_step()`: 6フェーズ非同期統合フロー

### フロー
```
Thought生成 → Director Check → Utterance生成 → Director Check → GM Step → UI更新
```

## テスト

```bash
pytest -q tests/test_gui_components.py tests/test_gui_data.py
# 62 passed
```

## UI 構成

### Console タブ (3ペインレイアウト)
- **Control Panel (左)**: Profile/Speaker選択、One-Stepボタン、Director状態
- **Main Stage (中央)**: ダイアログカード一覧
- **God View (右)**: World State、Recent Changes、Action Log

### Legacy タブ
- Scenario Selection、Execution、Results、Demo Pack

## モック実装

現時点では全アダプタがモック:
- `core_adapter.py`: ランダム遅延 + テンプレート応答
- `director_adapter.py`: コンテンツ長に応じた PASS/RETRY 判定
- `gm_client.py`: ランダム world_patch 生成

---
*Last Updated: 2026-01-30*
