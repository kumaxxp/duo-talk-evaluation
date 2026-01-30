# duo-talk-ecosystem ⚓

> AIキャラクター姉妹「やな」と「あゆ」の対話エコシステム

[![Phase](https://img.shields.io/badge/Phase-4%20Complete-brightgreen)](docs/strategy/STRATEGY.md)
[![Coverage](https://img.shields.io/badge/Coverage-96%25-brightgreen)]()
[![Python](https://img.shields.io/badge/Python-3.11+-blue)]()

---

## 🎯 What is duo-talk-ecosystem?

**duo-talk-ecosystem** は、AIキャラクター対話の品質を**測定可能**かつ**再現可能**な形で評価・改善するためのマイクロサービス群です。

キャラクターの一貫性を保ちながら、自然で魅力的な対話を生成することを目指しています。

---

## 🏛️ このリポジトリについて

**このリポジトリ (`duo-talk-evaluation`) は、duo-talk-ecosystem の「旗艦（Flagship）」です。**

- 📋 **戦略文書・開発ルール・設計図の格納場所**
- 🧪 **統合評価フレームワーク**
- 📊 **実験結果の蓄積**
- 🖥️ **GUIダッシュボード**

エコシステム全体の方針を知りたい場合は、まずこのリポジトリのドキュメントを参照してください。

---

## 🗂️ Ecosystem Structure

```
duo-talk-ecosystem/
├── duo-talk-core/        # 対話生成エンジン
├── duo-talk-director/    # 監視・演出・RAG
├── duo-talk-gm/          # ワールド管理
└── duo-talk-evaluation/  # 統合評価・司令部 ⚓ (YOU ARE HERE)
```

| Repository | Version | Role |
|:-----------|:-------:|:-----|
| [duo-talk-core](https://github.com/kumaxxp/duo-talk-core) | v1.0.0 | キャラクター設定、プロンプト生成、Two-Phase対話生成 |
| [duo-talk-director](https://github.com/kumaxxp/duo-talk-director) | v1.0.0 | 品質チェック、RAG Injection、状態抽出 |
| [duo-talk-gm](https://github.com/kumaxxp/duo-talk-gm) | v0.1.0 | 世界状態管理、アクション判定、ファクト生成 |
| **duo-talk-evaluation** | v0.4.0-hakoniwa-alpha | 評価フレームワーク、A/Bテスト、HAKONIWA、**ドキュメントHQ** |

---

## 📚 Documentation

### 司令部ドキュメント

| Document | Description |
|:---------|:------------|
| [STRATEGY.md](docs/strategy/STRATEGY.md) | 戦略文書 - Mission, Phase, 構造 |
| [RULES.md](docs/rules/RULES.md) | 開発ルール - コーディング規約, ブランチ戦略 |
| [ECOSYSTEM.md](docs/architecture/ECOSYSTEM.md) | アーキテクチャ図 - 4リポジトリの関係 |

### 技術ドキュメント

| Document | Description |
|:---------|:------------|
| [duo-talkマイクロサービス化詳細設計書.md](docs/duo-talkマイクロサービス化詳細設計書.md) | Phase設計の詳細 |
| [specs/phases/](specs/phases/) | 各Phaseの仕様書 |
| [results/](results/) | 実験結果（130+レポート） |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) with `gemma3:12b` model
- Git

### Installation

```bash
# 1. Clone all repositories
git clone https://github.com/kumaxxp/duo-talk-core.git
git clone https://github.com/kumaxxp/duo-talk-director.git
git clone https://github.com/kumaxxp/duo-talk-gm.git
git clone https://github.com/kumaxxp/duo-talk-evaluation.git

# 2. Setup evaluation (flagship)
cd duo-talk-evaluation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
pip install -e ../duo-talk-core
pip install -e ../duo-talk-director
```

### Running the System

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start GM Server
cd duo-talk-gm
uvicorn duo_talk_gm.main:app --port 8001

# Terminal 3: Start GUI
cd duo-talk-evaluation
make gui
# → Open http://localhost:8080
```

### CLI Play Mode

```bash
# Interactive scenario exploration
make play s=coffee_trap
```

---

## 🧪 Evaluation Framework

### A/B Testing

```bash
# Run A/B comparison (Director ON vs OFF)
python -m experiments.director_ab_test --scenario standard
```

### HAKONIWA Engine

HAKONIWAは、シナリオベースの対話評価エンジンです。

```bash
# Run scenario
python -m hakoniwa.runner --scenario mystery_mansion
```

---

## 📊 Current Achievements

| Metric | Before | After | Improvement |
|:-------|:------:|:-----:|:-----------:|
| Test Coverage | - | 96% | - |
| Tone Marker (Yana) | 70% | 90% | **+29%** |
| Excessive Praise (Ayu) | 15% | 5% | **-67%** |
| Setting Violation | 5% | 0% | **-100%** |
| Retry Count (RAG Injection) | 4 | 2 | **-50%** |

---

## 📁 Directory Structure

```
duo-talk-evaluation/
├── docs/                      # 📋 HQ Documents
│   ├── strategy/              #    戦略文書
│   ├── rules/                 #    開発ルール
│   └── architecture/          #    アーキテクチャ
├── specs/                     # 機能仕様書
│   └── phases/                #    Phase別仕様
├── experiments/               # 実験スクリプト
├── results/                   # 実験結果
├── scenarios/                 # HAKONIWAシナリオ
├── src/                       # ソースコード
│   ├── evaluators/           #    評価エンジン
│   ├── adapters/             #    システムアダプタ
│   └── ...
├── gui_nicegui/              # NiceGUI実装
├── tests/                    # テスト
├── pyproject.toml
└── README.md                 # ← YOU ARE HERE
```

---

## 🛤️ Roadmap

### Completed Phases

- [x] **Phase 0**: Evaluation Framework
- [x] **Phase 1**: Core Extraction
- [x] **Phase 2**: Director Separation
- [x] **Phase 2.2**: LLM Scoring
- [x] **Phase 2.3**: NoveltyGuard
- [x] **Phase 3.1**: RAG Observation
- [x] **Phase 3.2**: RAG Injection

### Upcoming

- [x] **Phase 4**: GUI Implementation & System Integration
- [ ] **Phase 5**: Optimal Configuration

See [STRATEGY.md](docs/strategy/STRATEGY.md) for details.

---

## 🤝 Contributing

1. Read [RULES.md](docs/rules/RULES.md) first
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Ensure all tests pass: `make test`
4. Submit a Pull Request

---

## 📜 License

MIT License - See each repository for details.

---

## 🔗 Links

- [duo-talk-core](https://github.com/kumaxxp/duo-talk-core)
- [duo-talk-director](https://github.com/kumaxxp/duo-talk-director)
- [duo-talk-gm](https://github.com/kumaxxp/duo-talk-gm)

---

<div align="center">

**⚓ duo-talk-evaluation - Flagship of the Ecosystem ⚓**

*Measure. Improve. Ship.*

</div>
