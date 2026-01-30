# HAKONIWA Console v0.1.0 Release Notes

**Release Date**: 2026-01-30
**Phase**: Phase 4 - GUI Implementation

## Overview

HAKONIWA Console は duo-talk-ecosystem の対話評価・デバッグ用 GUI です。
AI 姉妹キャラクター「やな」と「あゆ」の対話生成、品質チェック、ワールド状態管理を可視化します。

## Features

### Core Features

- **3ペインレイアウト**: Control Panel / Main Stage / God View
- **One-Step 実行**: Thought → Director Check → Utterance → Director Check → GM Step の統合フロー
- **リアルサービス統合**: duo-talk-core / duo-talk-director / duo-talk-gm と連携
- **自動フォールバック**: サービス不可時は mock モードで動作

### Main Stage

- **ダイアログカード**: ターン番号、話者、ステータスバッジ
- **Thought 折りたたみ**: 内省表示のデフォルト非表示
- **Repair Diff**: Director 修正の前後比較

### Control Panel

- **接続ステータス**: Core / Director / GM の可用性表示
- **Speaker 選択**: やな / あゆ の切替
- **One-Step ボタン**: 統合フロー実行

### God View

- **World State**: 現在位置、時刻、キャラクター状態
- **Recent Changes**: 直近の変更ハイライト
- **Action Log**: アクション履歴（最新5件）

## Technical Specifications

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  HAKONIWA Console (NiceGUI)             │
├─────────────┬─────────────────────┬─────────────────────┤
│ Control     │ Main Stage          │ God View            │
│ Panel       │ (Dialogue Cards)    │ (World State)       │
└─────┬───────┴──────────┬──────────┴──────────┬──────────┘
      │                  │                     │
      ▼                  ▼                     ▼
┌─────────────┐  ┌─────────────┐       ┌─────────────┐
│ CoreAdapter │  │ Director    │       │ GM Client   │
│ (async)     │  │ Adapter     │       │ (httpx)     │
└─────┬───────┘  └──────┬──────┘       └──────┬──────┘
      │                 │                     │
      ▼                 ▼                     ▼
┌─────────────┐  ┌─────────────┐       ┌─────────────┐
│duo-talk-core│  │duo-talk-    │       │duo-talk-gm  │
│ (Ollama)    │  │director     │       │ :8001       │
└─────────────┘  └─────────────┘       └─────────────┘
```

### Timeout Configuration

| Component | Timeout | Retries |
|-----------|---------|---------|
| Core (Thought) | 5s | - |
| Core (Utterance) | 5s | - |
| Director | 5s | max 2 |
| GM | 3s | - |

### Dependencies

- Python 3.11+
- NiceGUI 1.x
- httpx
- duo-talk-core (オプション)
- duo-talk-director (オプション)
- duo-talk-gm (オプション)

## Installation

```bash
# 1. Clone repository
git clone <repo-url>
cd duo-talk-evaluation

# 2. Create conda environment
conda create -n duo-talk python=3.11
conda activate duo-talk

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run GUI
make gui
# または
python -m gui_nicegui.main
```

## Usage

### Basic Usage

1. ブラウザで http://localhost:8080 にアクセス
2. Console タブを選択
3. Control Panel で Speaker を選択
4. "One-Step" ボタンをクリック
5. Main Stage にダイアログが追加される

### With Real Services

```bash
# 1. Start Ollama (for Core)
ollama serve

# 2. Start GM Service (optional)
cd ../duo-talk-gm
uvicorn duo_talk_gm.main:app --port 8001

# 3. Start GUI
make gui
```

## Known Issues

1. **初回 Thought 生成の遅延**: Ollama モデルロードにより 20-30秒かかる場合がある
2. **GM 未接続時の mock**: GM サービス未起動時は mock 応答を返す

## Migration Notes

- Phase 3 からの移行: Legacy タブに旧 UI を残存
- API 変更なし

## Changelog

### v0.1.0 (2026-01-30)

#### Added
- 3ペインレイアウト (Control Panel / Main Stage / God View)
- One-Step 統合フロー
- duo-talk-core 統合 (TwoPhaseEngine + OllamaClient)
- duo-talk-director 統合 (DirectorMinimal)
- duo-talk-gm HTTP 統合
- 統合テスト (tests/integration/)
- 負荷試験スクリプト (scripts/load_test_one_step.py)
- 指数バックオフ付き health-check

#### Fixed
- N/A (初回リリース)

#### Deprecated
- N/A

## Support

- Issue Tracker: GitHub Issues
- Documentation: docs/specs/PHASE4_GUI_IMPL_NOTES.md

---
**Contributors**: Claude Code, Cline
**License**: MIT
