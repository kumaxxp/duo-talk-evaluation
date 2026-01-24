# GM Service P0 仕様書

**作成日**: 2026-01-25
**ステータス**: 🔵 設計確定
**参照**: [箱庭TRPG構想](../geminiの将来構想/箱庭TRPG構想.md)

---

## 1. 概要

### 1.1 目的

duo-talk-ecosystemに「ゲームマスター（GM）」レイヤーを追加し、キャラクターの行動を世界状態と照合して整合性を担保する。

### 1.2 設計原則

| 原則 | 説明 |
|------|------|
| **GM外部化** | GMはduo-talk-core/directorの外部サービス |
| **1エンドポイント** | `/v1/gm/step` で parse/judge/update を一括処理 |
| **Phase 3.2再利用** | `get_facts_for_injection()` APIを活用 |
| **変化時のみ注入** | `world_delta`がある or deny/stall/format_break の場合のみ |

### 1.3 アーキテクチャ

```
[DialogueManager]
      │
      ▼
[DirectorHybrid] ──► get_facts_for_injection()
      │                       │
      │                       ▼
      │              [GM Service]
      │              /v1/gm/step
      │                       │
      ▼                       ▼
[Response]           [fact_cards + world_delta]
```

---

## 2. API仕様

### 2.1 エンドポイント

```
POST /v1/gm/step
Content-Type: application/json
```

### 2.2 リクエストスキーマ

```json
{
  "session_id": "string",
  "turn_number": 0,
  "speaker": "やな" | "あゆ",
  "raw_output": "Thought: (朝のキッチン)\nOutput: おはよう、あゆ。今日のごはん何にする？",
  "world_state": { /* WorldState object */ }
}
```

### 2.3 レスポンススキーマ

```json
{
  "parsed": {
    "thought": "(朝のキッチン)",
    "speech": "おはよう、あゆ。今日のごはん何にする？",
    "action_intents": [
      { "intent": "SAY", "target": "あゆ", "detail": "挨拶" },
      { "intent": "ASK", "target": "あゆ", "detail": "朝食の提案を求める" }
    ]
  },
  "allowed": true,
  "denied_reason": null,
  "world_delta": [
    { "op": "replace", "path": "/events/-", "value": "やながあゆに朝食について尋ねた" }
  ],
  "stall_score": 0.0,
  "fact_cards": [
    "FACT: キッチンにはマグカップがある。"
  ]
}
```

---

## 3. 型定義

### 3.1 denied_reason Enum

| 値 | 説明 | 例 |
|----|------|-----|
| `MISSING_OBJECT` | 存在しない小物を使用 | 「グラスを取る」（グラスがない） |
| `WRONG_LOCATION` | 現在地にないものを操作 | リビングからキッチンの物を取る |
| `INVALID_STATE` | 状態が矛盾 | 閉じたドアを通過 |
| `NOT_OWNED` | 所有していないものを使用 | 持っていない本を読む |
| `CONTRADICTS_WORLD` | 世界設定に反する | 夜に「朝日が眩しい」 |
| `OUT_OF_SCOPE` | P0スコープ外の行動 | 外出、新キャラ登場 |
| `AMBIGUOUS_ACTION` | 解釈不能な行動 | 主語/対象が不明 |
| `RATE_LIMITED` | 同一行動の過剰繰り返し | 3回連続で同じ質問 |

### 3.2 intent Type Enum

| 値 | 説明 | 例 |
|----|------|-----|
| `SAY` | 一般的な発話 | 「おはよう」 |
| `ASK` | 質問・依頼 | 「何にする？」 |
| `ANSWER` | 質問への回答 | 「パンがいいな」 |
| `EMOTE` | 感情表現・リアクション | 笑う、驚く |
| `MOVE` | 場所移動 | キッチンからリビングへ |
| `GET` | 物を取る | マグカップを取る |
| `PUT` | 物を置く | マグカップを置く |
| `USE` | 物を使う | コーヒーメーカーを使う |
| `EAT_DRINK` | 飲食 | コーヒーを飲む |

### 3.3 ActionIntent

```python
@dataclass
class ActionIntent:
    intent: str       # intent type enum
    target: str | None  # 対象（キャラ名 or 小物名）
    detail: str | None  # 補足説明
```

### 3.4 GMStepResponse

```python
@dataclass
class GMStepResponse:
    parsed: ParsedOutput
    allowed: bool
    denied_reason: str | None  # denied_reason enum
    world_delta: list[dict]    # JSON Patch format
    stall_score: float         # 0.0-1.0
    fact_cards: list[str]      # 注入用FACT
```

---

## 4. WorldState スキーマ

### 4.1 P0最小構成

```json
{
  "version": "0.1",
  "time": {
    "label": "朝",
    "turn": 0
  },
  "location": {
    "current": "キッチン"
  },
  "characters": {
    "やな": {
      "status": ["起床済み"],
      "holding": [],
      "location": "キッチン"
    },
    "あゆ": {
      "status": ["起床済み"],
      "holding": [],
      "location": "キッチン"
    }
  },
  "props": {
    "マグカップ": {
      "location": "キッチン",
      "state": ["clean"]
    },
    "コーヒーメーカー": {
      "location": "キッチン",
      "state": ["off"]
    }
  },
  "events": []
}
```

### 4.2 JSON Patch例

```json
[
  { "op": "add", "path": "/events/-", "value": "やながコーヒーを淹れた" },
  { "op": "replace", "path": "/props/コーヒーメーカー/state", "value": ["on", "brewing"] },
  { "op": "add", "path": "/characters/やな/holding/-", "value": "マグカップ" },
  { "op": "remove", "path": "/props/マグカップ" }
]
```

---

## 5. 注入条件

### 5.1 判定ロジック

```python
def should_inject(gm_response: GMStepResponse) -> tuple[bool, bool]:
    """
    Returns:
        (inject_world_state, inject_gm_feedback)
    """
    # 世界状態の注入: deltaがあれば注入
    inject_world_state = (
        gm_response.world_delta is not None
        and len(gm_response.world_delta) > 0
    )

    # GMフィードバックの注入: 問題があれば注入
    inject_gm_feedback = (
        (not gm_response.allowed)                    # 拒否された
        or (gm_response.stall_score > 0.5)          # 停滞検出
        or (gm_response.parsed.speech is None)      # 発話なし
    )

    return inject_world_state, inject_gm_feedback
```

### 5.2 fact_cards生成

```python
def generate_fact_cards(
    gm_response: GMStepResponse,
    world_state: dict
) -> list[str]:
    facts = []

    # 1. 拒否理由があれば最優先
    if not gm_response.allowed and gm_response.denied_reason:
        reason_map = {
            "MISSING_OBJECT": lambda: f"FACT: {extract_object(gm_response)}は存在しない。",
            "WRONG_LOCATION": lambda: f"FACT: {extract_object(gm_response)}は現在地にない。",
            "INVALID_STATE": lambda: f"FACT: その行動は現在の状態では不可能。",
            # ... 他のreason
        }
        facts.append(reason_map.get(gm_response.denied_reason, lambda: "")())

    # 2. 停滞警告
    if gm_response.stall_score > 0.5:
        facts.append("FACT: 会話が停滞気味。新しい話題や行動を。")

    # 3. 世界状態の変化サマリ（最大1つ）
    if gm_response.world_delta:
        summary = summarize_delta(gm_response.world_delta)
        facts.append(f"FACT: {summary}")

    return facts[:3]  # 最大3つ
```

---

## 6. stall_score 計算

### 6.1 ルールベース算出

```python
def calculate_stall_score(
    history: list[dict],
    current_delta: list[dict],
    window: int = 5
) -> float:
    """
    stall_score: 0.0 (活発) ~ 1.0 (停滞)
    """
    recent = history[-window:] if len(history) >= window else history

    # 重み付け指標
    weights = {
        "no_world_delta_run": 0.50,   # Δなしターン連続
        "topic_repeat": 0.25,          # 同一話題繰り返し
        "short_response": 0.15,        # 短い応答連続
        "no_action": 0.10,             # 発話のみ（行動なし）
    }

    score = 0.0

    # no_world_delta_run: 直近でΔがないターン数
    delta_empty_count = sum(
        1 for turn in recent
        if not turn.get("world_delta")
    )
    if not current_delta:
        delta_empty_count += 1
    score += weights["no_world_delta_run"] * (delta_empty_count / (window + 1))

    # topic_repeat: 同一キーワード出現率
    # (簡易実装: 直近の発話から名詞抽出して重複率)
    # ...

    # short_response: 20文字未満の応答率
    # ...

    # no_action: SAY/EMOTE以外のintentがない率
    # ...

    return min(1.0, score)
```

### 6.2 閾値

| 閾値 | アクション |
|------|----------|
| < 0.3 | 何もしない |
| 0.3 - 0.5 | ログに記録のみ |
| > 0.5 | fact_cardsに警告を追加 |
| > 0.8 | GMから話題提案を注入 |

---

## 7. 実験計画

### 7.1 2×2実験デザイン

| 条件 | Inject | GM | 説明 |
|------|--------|-----|------|
| A | OFF | OFF | ベースライン（現状） |
| B | ON | OFF | Phase 3.2相当（RAG注入のみ） |
| C | OFF | ON | GM観察のみ（ログ記録） |
| D | ON | ON | フル機能（本番想定） |

### 7.2 評価指標

| 指標 | 測定方法 |
|------|---------|
| **世界整合性** | 存在しない小物の使用率 |
| **リトライ削減** | 平均リトライ回数 |
| **会話品質** | 5軸評価スコア |
| **停滞検出** | stall_score > 0.5 の発生率 |

### 7.3 シナリオ

| シナリオ | 目的 | ターン数 |
|----------|------|---------|
| kitchen_morning | 標準会話 | 10 |
| violation_induced | 違反誘発（存在しない小物） | 6 |
| stall_induced | 停滞誘発（同一話題ループ） | 8 |

---

## 8. 実装チケット

### 8.1 Phase 1: 基盤（duo-talk-gm作成）

| チケット | 内容 | 依存 |
|----------|------|------|
| GM-001 | リポジトリ作成、FastAPI雛形 | なし |
| GM-002 | WorldState型定義 | GM-001 |
| GM-003 | `/v1/gm/step` エンドポイント（スタブ） | GM-002 |

### 8.2 Phase 2: パース＆判定

| チケット | 内容 | 依存 |
|----------|------|------|
| GM-004 | OutputParser実装（Thought/Speech/Intent抽出） | GM-003 |
| GM-005 | ActionJudge実装（allowed/denied_reason判定） | GM-004 |
| GM-006 | WorldUpdater実装（JSON Patch生成） | GM-005 |

### 8.3 Phase 3: 統合

| チケット | 内容 | 依存 |
|----------|------|------|
| GM-007 | StallDetector実装 | GM-006 |
| GM-008 | FactCardGenerator実装 | GM-007 |
| GM-009 | DirectorHybrid連携（get_facts_for_injection拡張） | GM-008 |

### 8.4 Phase 4: 実験

| チケット | 内容 | 依存 |
|----------|------|------|
| GM-010 | 2×2実験スクリプト作成 | GM-009 |
| GM-011 | 実験実行＆レポート | GM-010 |

---

## 9. ファイル構成（予定）

```
duo-talk-gm/
├── pyproject.toml
├── src/duo_talk_gm/
│   ├── __init__.py
│   ├── main.py                 # FastAPIエントリポイント
│   ├── api/
│   │   ├── __init__.py
│   │   └── gm_step.py          # /v1/gm/step
│   ├── core/
│   │   ├── __init__.py
│   │   ├── output_parser.py    # Thought/Speech/Intent抽出
│   │   ├── action_judge.py     # allowed/denied_reason判定
│   │   ├── world_updater.py    # JSON Patch生成
│   │   ├── stall_detector.py   # stall_score計算
│   │   └── fact_generator.py   # fact_cards生成
│   ├── models/
│   │   ├── __init__.py
│   │   ├── world_state.py      # WorldState型
│   │   ├── gm_response.py      # GMStepResponse型
│   │   └── enums.py            # denied_reason, intent
│   └── config/
│       └── settings.py
├── tests/
│   ├── test_output_parser.py
│   ├── test_action_judge.py
│   ├── test_world_updater.py
│   └── test_stall_detector.py
└── scenarios/
    └── kitchen_morning.yaml    # 初期WorldState
```

---

## 10. 関連ドキュメント

| ドキュメント | 役割 |
|-------------|------|
| [箱庭TRPG構想](../geminiの将来構想/箱庭TRPG構想.md) | 全体ビジョン |
| [PHASE3_2_COMPLETION](../phases/PHASE3_2_COMPLETION_20260125.md) | RAG Injection実装 |
| [PHASE3_1_RAG_SPEC](../phases/PHASE3_1_RAG_SPEC.md) | RAG基盤仕様 |

---

*Created: 2026-01-25*
*Source: ChatGPT P0設計レビュー (2026-01-25)*
