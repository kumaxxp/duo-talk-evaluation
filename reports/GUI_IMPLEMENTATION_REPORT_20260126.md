# GUI実装報告書

**作成日**: 2026-01-26
**プロジェクト**: duo-talk-evaluation
**対象コンポーネント**: NiceGUI ベースの評価GUI（HAKONIWA GUI）

---

## 1. 概要

duo-talk-evaluation の NiceGUI ベースの評価GUIの実装・修正を行いました。本報告書では、実装した機能、修正したバグ、テスト結果、および使用方法について記載します。

---

## 2. 実装機能一覧

### 2.1 Fast Triage Polish (Issue表示改善)

| 機能 | 説明 | 実装ファイル |
|------|------|--------------|
| Issue Summary Badge | `MISSING_OBJECT: <target>` 形式のバッジ表示 | `gui_nicegui/data/turns.py` |
| Auto-Open Issues | Demo Pack完了後、Issue turnがあれば自動でIssues Only viewを開く | `gui_nicegui/main.py` |
| Auto-Focus First Issue | 最初のissue turnの詳細セクションを自動展開 | `gui_nicegui/main.py` |

**新規TypedDict定義**:
```python
class IssueSummary(TypedDict, total=False):
    error_code: str       # MISSING_OBJECT, EMPTY_THOUGHT, etc.
    blocked_target: str   # Target that was blocked (if any)
    badge_text: str       # Human-readable badge text
```

**Issue種別と表示色**:
| Issue種別 | バッジ色 | 例 |
|-----------|----------|-----|
| MISSING_OBJECT | deep-orange | `MISSING_OBJECT: コーヒー豆` |
| GIVE_UP | red | `GIVE_UP` |
| RETRY | orange | `RETRY:MISSING_OBJECT` |
| その他 | amber | `EMPTY_THOUGHT` |

### 2.2 Interactive CLI Play Mode

| 機能 | 説明 | 実装ファイル |
|------|------|--------------|
| `make play s=<scenario_id>` | シナリオをインタラクティブに探索 | `scripts/play_mode.py` |
| コマンド対応 | look, move, take, status, help, quit | `scripts/play_mode.py` |

**対応コマンド**:
| コマンド | 別名 | 説明 |
|----------|------|------|
| `look` | `l`, `見る` | 現在地の情報を表示 |
| `move <場所>` | `go`, `移動` | 指定した場所に移動 |
| `take <物>` | `get`, `取る` | 物を拾う |
| `status` | `st`, `状態` | キャラクター状態を表示 |
| `help` | `h`, `?` | ヘルプを表示 |
| `quit` | `q`, `exit` | 終了 |

**使用例**:
```bash
$ make play s=coffee_trap

🎮 Play Mode: coffee_trap
'help' でコマンド一覧、'quit' で終了

=== coffee_trap ===

📍 現在地: キッチン

🎒 所持品: (なし)

📦 オブジェクト:
  - コーヒーメーカー
  - マグカップ
  - 冷蔵庫
  - トースター

🚪 出口:
  - リビング

>>> move リビング
📍 リビング に移動しました
```

### 2.3 Scenario Ops Extension

| 機能 | 説明 | 実装ファイル |
|------|------|--------------|
| containers フィールド | オブジェクト内のアイテム定義 | `scripts/scenario_tools.py` |
| hidden_objects フィールド | 隠しオブジェクト定義 | `scripts/scenario_tools.py` |
| Lint Rules | containers/hidden_objectsのバリデーション | `scripts/scenario_tools.py` |

**スキーマ拡張**:
```json
{
  "locations": {
    "リビング": {
      "props": ["ソファ", "本棚"],
      "exits": ["キッチン"],
      "containers": {"本棚": ["古い写真", "日記帳"]},
      "hidden_objects": ["ソファの下の鍵"]
    }
  }
}
```

**Lint Rules**:
| ルール | 種別 | 説明 |
|--------|------|------|
| containers親オブジェクト検証 | WARNING | コンテナ親がpropsに存在しない場合警告 |
| hidden_objects重複検証 | WARNING | hidden_objectsがpropsと重複する場合警告 |

---

## 3. バグ修正

### 3.1 Runner Command 修正（重大バグ）

**問題**: 実験実行時に0ターンで終了し、LLM呼び出しが行われない

**原因分析**:
| 原因 | 詳細 |
|------|------|
| `--experiment_id` 未指定 | gm_2x2_runner.py の必須パラメータが欠落 |
| `--mode sim` で実行 | シミュレーションモードで実行されLLM呼び出しなし |
| `PYTHONPATH` 未設定 | モジュールインポート失敗 |

**修正内容**:

新規モジュール `gui_nicegui/data/runner.py` を作成:

```python
def build_runner_command(
    scenario_id: str,
    profile: str,
    project_root: Path,
    max_turns: int | None = None,
    mode: str = "real",        # デフォルト: real (Ollama呼び出し)
    llm_model: str | None = None,
) -> RunnerCommand:
    """Build command to run experiment."""
    experiment_id = generate_experiment_id(scenario_id, profile)

    cmd = [
        sys.executable,
        "experiments/gm_2x2_runner.py",
        "--experiment_id", experiment_id,
        "--profile", profile,
        "--scenarios", scenario_id,
        "--mode", mode,
    ]

    # Environment must include PYTHONPATH for module imports
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    return RunnerCommand(cmd=cmd, env=env, cwd=project_root)
```

---

## 4. ファイル変更一覧

### 4.1 新規作成ファイル

| ファイル | 行数 | 説明 |
|----------|------|------|
| `gui_nicegui/data/runner.py` | 85 | Runner command生成モジュール |
| `scripts/play_mode.py` | 250 | Interactive play mode |
| `tests/test_play_mode.py` | 120 | Play mode テスト |

### 4.2 修正ファイル

| ファイル | 変更内容 |
|----------|----------|
| `gui_nicegui/main.py` | run_experiment/run_demo_pack を build_runner_command 使用に変更、Issue badge追加 |
| `gui_nicegui/data/turns.py` | IssueSummary TypedDict, extract_issue_summary() 関数追加 |
| `scripts/scenario_tools.py` | containers/hidden_objects lint rules 追加、LocationTemplate拡張 |
| `tests/test_gui_data.py` | TestIssueSummary (5件), TestRunnerCommand (8件) 追加 |
| `tests/test_scenario_tools.py` | containers/hidden_objects テスト (4件) 追加 |
| `Makefile` | `make play` コマンド追加 |

---

## 5. テスト結果

### 5.1 ユニットテスト

```
tests/test_gui_data.py          : 45 passed
tests/test_play_mode.py         : 11 passed
tests/test_scenario_tools.py    : 22 passed
────────────────────────────────────────────
Total                           : 78 passed
```

### 5.2 E2Eテスト（手動実行）

```
Experiment ID: test_real_mode
Mode: real
Model: gemma3:12b
Turns generated: 3
Avg LLM latency: 1373.4ms
P95 LLM latency: 1627.2ms
Throughput: 0.11 turns/sec
Result directory: results/gm_2x2_test_real_mode_20260126_080908
```

### 5.3 CI Gate

```
gm:          ✅ PASSED (195 tests)
evaluation:  ✅ PASSED (515 tests)
lint-scenarios: All OK
gui-smoke:   OK
=== CI Gate: PASSED ===
```

---

## 6. 使用方法

### 6.1 前提条件

1. **Ollama** が起動していること（port 11434）
2. **GMサーバー** が起動していること（port 8001）

```bash
# Ollamaの確認
curl http://localhost:11434/api/tags

# GMサーバー起動
cd ../duo-talk-gm && uvicorn duo_talk_gm.main:app --port 8001 &
```

### 6.2 GUI起動

```bash
make gui
# または
python -m gui_nicegui.main
```

**アクセスURL**: http://localhost:8080

### 6.3 GUI操作手順

#### 単一シナリオ実行
1. **Scenario Selection** パネルでシナリオ選択（例: `coffee_trap`）
2. **Execution** パネルで Profile 選択（dev/gate/full）
3. **Run** ボタンをクリック
4. 約30秒〜1分待機（LLM呼び出し中）
5. 完了後、**Results** パネルで結果確認
6. **View All** または **Issues Only** ボタンで詳細表示

#### Demo Pack実行
1. **Demo Pack** パネルで **Run Demo Pack** ボタンをクリック
2. 3シナリオ（coffee_trap, wrong_location, locked_door）が連続実行
3. **Auto-Open Issues** ON の場合、完了後に自動でIssues viewを表示

### 6.4 CLI Play Mode

```bash
make play s=coffee_trap
```

---

## 7. アーキテクチャ

```
gui_nicegui/
├── main.py              # NiceGUI アプリケーション (681行)
├── data/
│   ├── scenarios.py     # シナリオ読み込み
│   ├── registry.py      # レジストリ管理
│   ├── results.py       # 結果分析
│   ├── turns.py         # ターンViewModel + IssueSummary
│   ├── diff.py          # Diff生成
│   ├── guidance.py      # Guidance card解析
│   ├── pack.py          # Demo Pack管理
│   ├── latest.py        # Latest pointer管理
│   ├── compare.py       # 結果比較
│   ├── export.py        # ZIP出力
│   └── runner.py        # Runner command生成 [NEW]
```

---

## 8. 既知の制限

| 制限 | 説明 | 回避策 |
|------|------|--------|
| GMサーバー必須 | 実験実行にはGMサーバー（port 8001）が必要 | `uvicorn duo_talk_gm.main:app --port 8001` |
| Ollama必須 | real mode では Ollama が必要 | Ollama起動確認: `curl http://localhost:11434/api/tags` |
| ログストリーミング | 現在は最終行のみ表示 | リアルタイムログ表示は将来実装予定 |

---

## 9. 今後の改善案

1. **リアルタイムログ表示**: WebSocket経由でログをストリーミング
2. **進捗バー**: 実験実行中の進捗表示
3. **モデル選択UI**: GUIからLLMモデルを選択可能に
4. **結果比較機能**: 複数の実験結果を並べて比較

---

## 10. 関連ドキュメント

- [GUI_MVP.md](../docs/GUI_MVP.md) - GUI MVP仕様
- [P0_FREEZE_POLICY.md](../docs/P0_FREEZE_POLICY.md) - P0 Feature Freeze宣言
- [triage_playbook.md](../docs/triage_playbook.md) - Triage Playbook

---

*報告者: Claude Code*
*バージョン: 1.0*
