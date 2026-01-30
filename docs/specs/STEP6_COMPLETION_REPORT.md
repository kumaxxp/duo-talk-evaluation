# Step6 完了報告

## ステップ番号
**Step6: Integration Test Suite & Hardening**

## 編集ファイル一覧

### 新規作成
- `tests/integration/__init__.py`
- `tests/integration/test_one_step_e2e.py` (統合テスト)
- `scripts/ci/run_integration.sh` (CI スクリプト)
- `scripts/load_test_one_step.py` (負荷試験)
- `gui_nicegui/utils/__init__.py`
- `gui_nicegui/utils/logging_utils.py` (ログユーティリティ)

### 更新
- `Makefile` (test-integration, load-test ターゲット追加)
- `gui_nicegui/clients/gm_client.py` (指数バックオフ追加)
- `docs/specs/PHASE4_GUI_IMPL_NOTES.md` (運用手順追記)

## 実施内容

### 1. 統合テスト (`tests/integration/test_one_step_e2e.py`)

```python
# テストクラス
- TestOneStepE2EWithMocks: モック使用の完全フローテスト
- TestOneStepE2EWithRealServices: 実サービス使用テスト (環境変数で制御)
- TestServiceAvailability: サービス可用性確認
- TestLatencyMetrics: レイテンシ追跡テスト
```

主要テストケース:
- `test_one_step_complete_flow_all_pass`: 全 PASS の完全フロー
- `test_one_step_with_director_retry`: Director RETRY ハンドリング
- `test_one_step_timeout_handling`: タイムアウト処理
- `test_real_*`: 実サービステスト (USE_REAL_* 環境変数)

### 2. CI スクリプト (`scripts/ci/run_integration.sh`)

```bash
# オプション
--with-services  # GM サービス自動起動
--real-core      # 実 Core 使用
--real-director  # 実 Director 使用
--real-gm        # 実 GM 使用
```

機能:
- GM サービスの自動起動・待機
- 環境変数による実サービス切替
- カラー出力によるステータス表示
- クリーンアップ (trap)

### 3. Makefile ターゲット

```makefile
test-integration:
    $(PYTHON) -m pytest tests/integration/ -v --tb=short

test-integration-real:
    ./scripts/ci/run_integration.sh --with-services

load-test:
    $(PYTHON) scripts/load_test_one_step.py --concurrent 5 --iterations 3
```

### 4. ログ出力強化 (`gui_nicegui/utils/logging_utils.py`)

```python
class TraceContext:
    """トレースID付きコンテキスト"""
    trace_id: str  # 8文字の一意ID
    def log_event(phase, message, latency_ms) -> str

class LogBuffer:
    """ログバッファ (最大行数制限付き)"""
    def append(line)
    def get_all() -> str
    def get_last(n) -> str

def format_log_line(phase, message, trace_id=None) -> str
# 出力例: [12:34:56.789] [a1b2c3d4] [THOUGHT] Generated in 150ms
```

### 5. 指数バックオフ (`gui_nicegui/clients/gm_client.py`)

```python
BACKOFF_BASE = 1.0      # 初期遅延
BACKOFF_MAX_RETRIES = 3 # 最大リトライ
BACKOFF_MULTIPLIER = 2.0  # 倍率

async def _check_gm_availability_with_backoff():
    """リトライ: 1s → 2s → 4s"""
```

### 6. 負荷試験 (`scripts/load_test_one_step.py`)

```bash
# 使用例
python scripts/load_test_one_step.py -n 5 -i 3

# 出力
- CSV: reports/load_test_{timestamp}.csv
- MD: reports/load_test_{timestamp}.md
```

計測項目:
- 成功率
- レイテンシ (min/max/avg/p95)
- フェーズ別レイテンシ
- エラー集計

## 実行コマンド

### ローカル統合テスト

```bash
# モックのみ
make test-integration

# 実サービス付き
./scripts/ci/run_integration.sh --with-services

# 環境変数で個別制御
USE_REAL_CORE=1 USE_REAL_DIRECTOR=1 python -m pytest tests/integration/ -v
```

### 負荷試験

```bash
make load-test
# または
python scripts/load_test_one_step.py -n 10 -i 5
```

## テスト結果

### 統合テスト

```
tests/integration/test_one_step_e2e.py::TestOneStepE2EWithMocks::test_one_step_complete_flow_all_pass PASSED
tests/integration/test_one_step_e2e.py::TestOneStepE2EWithMocks::test_one_step_with_director_retry PASSED
tests/integration/test_one_step_e2e.py::TestOneStepE2EWithMocks::test_one_step_timeout_handling PASSED
tests/integration/test_one_step_e2e.py::TestOneStepE2EWithRealServices::test_real_core_thought_generation SKIPPED
tests/integration/test_one_step_e2e.py::TestOneStepE2EWithRealServices::test_real_director_check SKIPPED
tests/integration/test_one_step_e2e.py::TestOneStepE2EWithRealServices::test_real_gm_step SKIPPED
tests/integration/test_one_step_e2e.py::TestServiceAvailability::test_core_availability_flag PASSED
tests/integration/test_one_step_e2e.py::TestServiceAvailability::test_director_availability_flag PASSED
tests/integration/test_one_step_e2e.py::TestServiceAvailability::test_gm_health_check PASSED
tests/integration/test_one_step_e2e.py::TestLatencyMetrics::test_core_latency_tracking PASSED
tests/integration/test_one_step_e2e.py::TestLatencyMetrics::test_director_latency_tracking PASSED
tests/integration/test_one_step_e2e.py::TestLatencyMetrics::test_gm_latency_tracking PASSED

========================= 9 passed, 3 skipped in 0.87s =========================
```

### 全テスト

```
======================= 741 passed, 15 skipped in 3.12s ========================
```

## 性能試験の主要指標

### 負荷試験結果 (2 concurrent x 1 iteration)

| Metric | Value |
|--------|-------|
| Total Runs | 2 |
| Success Rate | 100.0% |
| Min Latency | 5042ms |
| Max Latency | 5264ms |
| Avg Latency | 5153ms |
| P95 Latency | 5264ms |

※ Ollama (gemma3:12b) でのモデルロード時間含む

### フェーズ別平均レイテンシ

| Phase | Avg Latency |
|-------|-------------|
| Thought Generation | ~5000ms |
| Director (Thought) | ~1ms |
| Utterance Generation | ~100ms (mock) |
| Director (Speech) | ~1ms |
| GM Step | ~100ms (mock) |

## 起動ログ抜粋

```
=== HAKONIWA Console Integration Tests ===
Project root: /home/owner/work/duo-talk-ecosystem/duo-talk-evaluation
[INFO] Running integration tests...
tests/integration/test_one_step_e2e.py ... 9 passed, 3 skipped

=== Integration tests PASSED ===
```

## 未解決事項

1. **Thought 生成の高レイテンシ**: Ollama + gemma3:12b で初回 20-30 秒かかる場合がある。モデルのウォームアップまたは軽量モデルへの切替を検討。

2. **実サービステストの自動化**: CI 環境で Ollama/GM を自動起動する仕組みが必要。現状は手動起動が前提。

3. **フレイキーテストの監視**: 実サービステストはネットワーク/負荷に依存するため、CI での安定性監視が必要。

## 設計上の選択

1. **環境変数による切替**: `USE_REAL_*` 環境変数で実サービステストを制御。CI ではモックのみ、ローカルで実サービステスト可能。

2. **指数バックオフのデフォルト値**: 1s→2s→4s (最大3回) は一般的なベストプラクティスに基づく。

3. **ログユーティリティの分離**: main.py から独立したモジュールとして実装。将来的に他のコンポーネントでも利用可能。

---
**実施日時**: 2026-01-30
**実施者**: Claude Code
