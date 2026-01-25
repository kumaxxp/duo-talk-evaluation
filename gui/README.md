# HAKONIWA GUI

NiceGUIベースの最小GUI（将来作り直し前提）。

## 起動方法

```bash
# conda環境をアクティベート
source ~/miniconda3/etc/profile.d/conda.sh && conda activate duo-talk

# GUI起動
python -m gui.main
```

ブラウザで http://localhost:8080 にアクセス。

## 機能

### Phase A: Scenario Editor (`/`)

- registry.yamlからシナリオ一覧を読み込み
- scenario.jsonを編集（locations/exits/objects/characters）
- バリデーション結果をリアルタイム表示
- world_summary/hashを右ペイン表示

### Phase B: Run Launcher (`/run`)

- profile (dev/gate/full)、condition、seeds、turnsを指定して実行
- 実行後にresultsのパスを表示
- run_meta/artifacts/turns_log.jsonへジャンプ

### Phase C: Log Viewer (`/logs`)

- turn一覧（speaker, trigger, repaired, retry_steps, give_up等）
- クリックでTurn詳細表示
- format_break発生時はraw/repaired/finalを並べて表示

## 設計方針

- **疎結合**: GUIコードにGMの中核ロジックを書かない。Runnerを呼ぶだけ。
- **最小実装**: まずは "dev profile + condition D + 1 scenario" で動けばOK。
- **将来作り直し前提**: Streamlitではなく、NiceGUIでPython完結の暫定GUI。

## ファイル構成

```
gui/
├── __init__.py
├── main.py              # エントリーポイント
├── README.md            # このファイル
└── pages/
    ├── __init__.py
    ├── scenario_editor.py  # Phase A
    ├── run_launcher.py     # Phase B
    └── log_viewer.py       # Phase C
```

## 依存関係

- nicegui >= 1.4.0
- PyYAML (scenario registry読み込み)
- experiments/ モジュール（scenario_registry, gm_2x2_runner）
