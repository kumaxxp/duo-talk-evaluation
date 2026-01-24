# Phase 3.1: RAG統合（裏方導入）仕様書

## 概要

RAGを「会話を賢くする」ではなく「設定逸脱を減らす裏方」として導入する。
会話生成には直接注入せず、まずFactカード生成と観測のみ行う。

## 原則

1. **会話生成にRAG文面を直入れしない**（Phase 3.1では）
2. RAGは**Director側**で使う（失敗検出役）
3. 情報は**Factカード形式**（最大3つ、各1文）に圧縮
4. 「参照できなかった」時は**推測しない**

## アーキテクチャ

```
[User発話 + 直近ログ + SceneState]
              ↓
        ┌─────────────┐
        │  RAG検索    │
        │ ┌─────────┐ │
        │ │Persona  │ │ ← キャラ設定・禁止事項・呼称・話法
        │ │Rules RAG│ │
        │ └─────────┘ │
        │ ┌─────────┐ │
        │ │Session  │ │ ← 直近の合意・場面設定・持ち物
        │ │Memory   │ │
        │ └─────────┘ │
        └──────┬──────┘
               ↓
        [Factカード生成]
        (最大3つ、各1文)
               ↓
        [ログに記録] ← Phase 3.1はここまで
               ↓
        (Phase 3.2で会話に注入)
```

## RAGコンポーネント

### 1. Persona/Rules RAG

**目的**: キャラクター設定の逸脱防止

**インデックス対象**:
- キャラクター設定（やな/あゆの性格、口調、一人称）
- 禁止事項（やなが「姉様」と言わない、あゆが「やなちゃん」と言わない）
- 呼称ルール（あゆ→姉様、やな→あゆ）
- 話法ルール（やな: カジュアル、あゆ: 丁寧語だが毒）

**検索トリガー**:
- 全ターン（常時参照）

**出力例**:
```
FACT: あゆは「姉様」、やなは「あゆ」と呼ぶ。
FACT: やなは敬語を使わない。あゆは丁寧語だが皮肉を言う。
```

### 2. Session Memory RAG

**目的**: 場面・持ち物の一貫性維持

**インデックス対象**:
- SceneState（場所、時間帯、雰囲気）
- 利用可能な小物（props）
- 直近の会話で決まった合意事項
- 現在の話題

**検索トリガー**:
- 全ターン（常時参照）

**出力例**:
```
FACT: Sceneにある物は「マグカップ」のみ。グラスは無い。
FACT: 現在の話題は「朝の挨拶」。
```

## Factカード仕様

### フォーマット

```
FACT: <1文で完結する事実>
```

### 制約

| 項目 | 制約 |
|------|------|
| 最大数 | 3つ |
| 最大文字数 | 各50文字以内 |
| 形式 | 断定形（「〜である」「〜する」） |
| 禁止 | 推測、曖昧表現、質問形 |

### 優先順位

1. **禁止事項**（最優先）
2. **Scene制約**（小物・場所）
3. **呼称・話法**
4. **現在の話題**

## ファイル構成

```
duo-talk-director/
├── src/duo_talk_director/
│   ├── rag/                       # 新規
│   │   ├── __init__.py
│   │   ├── fact_card.py           # Factカード生成
│   │   ├── persona_rag.py         # Persona/Rules RAG
│   │   ├── session_rag.py         # Session Memory RAG
│   │   └── rag_manager.py         # RAG統合管理
│   └── config/
│       └── persona_rules.yaml     # キャラ設定・ルール定義
└── tests/
    ├── test_fact_card.py
    ├── test_persona_rag.py
    └── test_session_rag.py
```

## データ構造

### FactCard

```python
@dataclass
class FactCard:
    content: str          # Fact内容（50文字以内）
    source: str           # "persona" | "session"
    priority: int         # 1-4（1が最優先）
    confidence: float     # 0.0-1.0
```

### RAGResult

```python
@dataclass
class RAGResult:
    facts: list[FactCard]  # 最大3つ
    query_time_ms: float
    sources_searched: list[str]
```

## 実装フェーズ

### Phase 3.1.1: 基盤構築

1. FactCard/RAGResult型定義
2. persona_rules.yaml作成（やな/あゆ設定）
3. PersonaRAG実装（YAMLからの検索）
4. SessionRAG実装（SceneStateからの検索）

### Phase 3.1.2: RAGManager統合

1. RAGManager実装（Persona + Session統合）
2. 優先順位に基づくFact選択（最大3つ）
3. DirectorHybridへの組み込み（ログ出力のみ）

### Phase 3.1.3: 観測・評価

1. ベンチマークでFactカード生成を観測
2. Factカードの有用性を手動評価
3. 会話品質への影響確認（format/thought/retry維持）

## テストケース

| テスト | 期待結果 |
|--------|---------|
| `test_fact_card_max_length` | 50文字超でエラー |
| `test_fact_card_max_count` | 4つ以上でエラー |
| `test_persona_rag_prohibited_term` | 禁止事項検出 |
| `test_session_rag_scene_props` | 小物制約検出 |
| `test_rag_manager_priority` | 優先順位どおりの選択 |
| `test_rag_no_hallucination` | 参照なしで推測しない |

## 成功基準

| 項目 | 目標 |
|------|------|
| Factカード生成 | 全ターンで生成可能 |
| 有用性（手動評価） | 80%以上のFactが有用 |
| format_success | 100%維持 |
| thought_missing | ≤1%維持 |
| avg_retries | ≤0.1維持 |

## 次フェーズへの移行条件

Phase 3.2への移行条件:
1. Factカードが手動評価で80%以上有用
2. 会話品質指標が維持されている
3. RAG検索時間が許容範囲内（<100ms/query）

---

*Created: 2026-01-24*
