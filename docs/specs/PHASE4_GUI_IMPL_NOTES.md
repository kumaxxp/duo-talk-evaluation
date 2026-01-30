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
| Step5 | 魂の注入 (Real Integration) | adapters + clients |
| Step6 | 統合テスト + ハードニング | tests/integration/, scripts/ |

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
# 単体テスト
pytest -q tests/test_gui_components.py tests/test_gui_data.py
# 62 passed

# 統合テスト
make test-integration
# 9 passed, 3 skipped

# 全テスト
python -m pytest tests/ -v
# 729 passed, 12 skipped
```

## UI 構成

### Console タブ (3ペインレイアウト)
- **Control Panel (左)**: Profile/Speaker選択、One-Stepボタン、Director状態
- **Main Stage (中央)**: ダイアログカード一覧
- **God View (右)**: World State、Recent Changes、Action Log

### Legacy タブ
- Scenario Selection、Execution、Results、Demo Pack

## サービス統合 (Step5)

### Core Adapter
- duo-talk-core の TwoPhaseEngine + OllamaClient を使用
- Ollama 不可時は mock フォールバック
- asyncio.to_thread で同期→非同期化

### Director Adapter
- duo-talk-director の DirectorMinimal を使用
- 静的バリデーション（LLM 不要）
- PASS/WARN/RETRY/MODIFY をマッピング

### GM Client
- httpx.AsyncClient で localhost:8001 に接続
- /health エンドポイントで自動検出
- GM 不可時は mock フォールバック
- 指数バックオフ付き health-check (1s→2s→4s)

## 運用手順

### サービス起動順序

1. **Ollama 起動** (Core 用)
   ```bash
   # 既に起動している場合は不要
   ollama serve
   ```

2. **GM サービス起動** (オプション)
   ```bash
   cd ../duo-talk-gm
   uvicorn duo_talk_gm.main:app --port 8001
   ```

3. **GUI 起動**
   ```bash
   make gui
   # または
   python -m gui_nicegui.main
   ```

### サービス状態確認

```bash
# Core (Ollama) 確認
curl http://localhost:11434/api/tags

# GM 確認
curl http://localhost:8001/health

# Python での確認
python -c "
import sys; sys.path.insert(0, 'gui_nicegui')
from adapters.core_adapter import CORE_AVAILABLE
from adapters.director_adapter import DIRECTOR_AVAILABLE
print(f'Core: {CORE_AVAILABLE}')
print(f'Director: {DIRECTOR_AVAILABLE}')
"
```

### トラブルシュート

#### Thought 生成が遅い
- Ollama モデルのロード時間
- 初回は 30 秒以上かかる場合がある
- タイムアウトを延長: `ONE_STEP_TIMEOUT_CORE = 30.0`

#### GM 接続失敗
- GM サービスが起動しているか確認
- ポート 8001 が使用可能か確認
- mock フォールバックで動作継続

#### Director RETRY 多発
- DirectorMinimal の strict_thought_check が有効
- Thought/Speech のフォーマットを確認
- repaired_output がない場合は再生成

### 再起動手順

```bash
# 1. GUI を停止 (Ctrl+C)
# 2. プロセス確認
lsof -i :8080 | grep LISTEN

# 3. 強制終了（必要な場合）
kill -9 $(lsof -t -i :8080)

# 4. 再起動
make gui
```

### ログ確認

```bash
# GUI ログはコンソールに出力
# state.log_output で最新ステータス確認

# 詳細ログ有効化
export PYTHONPATH=.
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from gui_nicegui.main import create_app
"
```

## 負荷試験

```bash
# 同時 5 リクエスト x 3 イテレーション
make load-test

# カスタム設定
python scripts/load_test_one_step.py -n 10 -i 5

# 結果は reports/ に保存
```

## CI 統合

```bash
# 統合テスト実行
make test-integration

# 実サービス付きテスト
./scripts/ci/run_integration.sh --with-services

# 全テスト + 統合テスト
make test && make test-integration
```

---
*Last Updated: 2026-01-30*
