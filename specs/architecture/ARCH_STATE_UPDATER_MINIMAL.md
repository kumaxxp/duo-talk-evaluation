# State Updater 最小設計仕様書

**文書ID**: 20260124_003
**作成日**: 2026-01-24
**フェーズ**: Phase 2.3準備
**ステータス**: Draft
**情報源**: 内部設計 + ChatGPT提案

---

## 概要

Thoughtから感情・トピック・関係性の状態を抽出し、JSON差分形式で管理する最小実装。

---

## 設計方針

### 最小MVP原則

1. **シグナル検出型から開始** - 正規表現ベース、LLMは後回し
2. **ターンレベルのみ** - セッションレベルは後のフェーズ
3. **既存構造に影響なし** - 新規モジュールとして追加

### 配置場所

**duo-talk-director/src/duo_talk_director/state/**

理由:
- Director評価スコアと共存可能
- LLMクライアント既存で将来の拡張が容易
- 品質制御フローに自然に統合

---

## データ構造

### ExtractedState（最小版）

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class EmotionType(Enum):
    JOY = "joy"           # 喜び
    WORRY = "worry"       # 心配
    ANNOYANCE = "annoyance"  # 苛立ち
    AFFECTION = "affection"  # 愛情
    NEUTRAL = "neutral"   # 中立

class RelationshipTone(Enum):
    WARM = "warm"         # 温かい
    TEASING = "teasing"   # からかい
    CONCERNED = "concerned"  # 心配
    DISTANT = "distant"   # 距離感
    NEUTRAL = "neutral"   # 中立

@dataclass
class ExtractedState:
    """Thoughtから抽出した状態（最小版）"""

    # 感情状態
    emotion: EmotionType = EmotionType.NEUTRAL
    emotion_intensity: float = 0.5  # 0.0-1.0
    emotion_target: Optional[str] = None  # "あゆ", "やな", "話題" など

    # 関係性状態
    relationship_tone: RelationshipTone = RelationshipTone.NEUTRAL

    # トピック状態
    topic_keywords: list[str] = field(default_factory=list)
    topic_interest: float = 0.5  # 0.0-1.0

    # メタデータ
    confidence: float = 0.0  # 抽出信頼度
    extraction_method: str = "signal"  # "signal" or "llm"
```

### StateDiff（差分形式）

```python
@dataclass
class StateDiff:
    """ターン間の状態差分"""

    turn_number: int
    speaker: str

    # 前ターンからの変化
    emotion_changed: bool = False
    emotion_from: Optional[EmotionType] = None
    emotion_to: Optional[EmotionType] = None

    relationship_changed: bool = False
    relationship_from: Optional[RelationshipTone] = None
    relationship_to: Optional[RelationshipTone] = None

    # 新規トピック
    new_topics: list[str] = field(default_factory=list)
```

---

## 抽出ロジック（シグナル検出型）

### 感情シグナル辞書

```python
EMOTION_SIGNALS = {
    EmotionType.JOY: [
        "嬉しい", "楽しい", "ワクワク", "最高", "素敵",
        "よかった", "面白い", "幸せ",
    ],
    EmotionType.WORRY: [
        "心配", "不安", "大丈夫かな", "困る", "どうしよう",
        "気になる",
    ],
    EmotionType.ANNOYANCE: [
        "また", "いつも", "面倒", "うんざり", "やれやれ",
        "はぁ", "ため息",
    ],
    EmotionType.AFFECTION: [
        "可愛い", "大切", "守りたい", "姉様", "あゆ",
        "妹思い", "愛おしい",
    ],
}
```

### 関係性シグナル辞書

```python
RELATIONSHIP_SIGNALS = {
    RelationshipTone.WARM: [
        "嬉しそう", "笑顔", "一緒に", "仲良し",
    ],
    RelationshipTone.TEASING: [
        "からかう", "いじわる", "ツンツン", "素直じゃない",
    ],
    RelationshipTone.CONCERNED: [
        "心配", "大丈夫", "無理しないで", "体調",
    ],
    RelationshipTone.DISTANT: [
        "距離", "冷たい", "無視", "そっけない",
    ],
}
```

---

## API設計

### StateExtractor

```python
class StateExtractor:
    """Thoughtから状態を抽出"""

    def extract(self, thought: str, speaker: str) -> ExtractedState:
        """単一Thoughtから状態を抽出"""
        pass

    def extract_diff(
        self,
        current: ExtractedState,
        previous: Optional[ExtractedState],
        turn_number: int,
        speaker: str,
    ) -> StateDiff:
        """前ターンとの差分を計算"""
        pass
```

### 使用例

```python
from duo_talk_director.state import StateExtractor, ExtractedState

extractor = StateExtractor()

# Turn 1: やな
thought1 = "あゆも起きてるかな？朝から何して遊ぶか、もうワクワクしてる！"
state1 = extractor.extract(thought1, "やな")
# state1.emotion = EmotionType.JOY
# state1.emotion_intensity = 0.8
# state1.emotion_target = "あゆ"

# Turn 2: あゆ
thought2 = "また始まった…姉様のハイテンションは、一体いつまで続くんだろう。"
state2 = extractor.extract(thought2, "あゆ")
# state2.emotion = EmotionType.ANNOYANCE
# state2.relationship_tone = RelationshipTone.TEASING

# 差分計算
diff = extractor.extract_diff(state2, state1, turn_number=2, speaker="あゆ")
# diff.emotion_changed = True
# diff.emotion_from = EmotionType.JOY
# diff.emotion_to = EmotionType.ANNOYANCE
```

---

## JSON出力形式

```json
{
  "turn": 2,
  "speaker": "あゆ",
  "state": {
    "emotion": "annoyance",
    "emotion_intensity": 0.6,
    "emotion_target": "姉様",
    "relationship_tone": "teasing",
    "topic_keywords": ["朝", "ハイテンション"],
    "topic_interest": 0.4,
    "confidence": 0.7,
    "extraction_method": "signal"
  },
  "diff": {
    "emotion_changed": true,
    "emotion_from": "joy",
    "emotion_to": "annoyance",
    "relationship_changed": false,
    "new_topics": []
  }
}
```

---

## ファイル構成

```
duo-talk-director/src/duo_talk_director/
├── state/
│   ├── __init__.py
│   ├── models.py          # ExtractedState, StateDiff
│   ├── signals.py         # EMOTION_SIGNALS, RELATIONSHIP_SIGNALS
│   └── extractor.py       # StateExtractor
└── tests/
    └── test_state_extractor.py
```

---

## テストケース（TDD）

| テスト | 入力 | 期待出力 |
|--------|------|---------|
| `test_extract_joy_emotion` | "ワクワクしてる！" | emotion=JOY |
| `test_extract_worry_emotion` | "大丈夫かな…心配" | emotion=WORRY |
| `test_extract_annoyance` | "また始まった…" | emotion=ANNOYANCE |
| `test_extract_affection` | "あゆが可愛い" | emotion=AFFECTION, target="あゆ" |
| `test_extract_relationship_teasing` | "素直じゃないなぁ" | relationship=TEASING |
| `test_extract_multiple_signals` | "嬉しいけど心配" | 強い方を採用 |
| `test_extract_no_signal` | "そうですね" | emotion=NEUTRAL |
| `test_diff_emotion_changed` | state1→state2 | emotion_changed=True |
| `test_diff_no_change` | state1→state1 | emotion_changed=False |

---

## 実装フェーズ

### Phase 2.3.1: 最小実装（今回）

- [ ] models.py - データ構造定義
- [ ] signals.py - シグナル辞書
- [ ] extractor.py - StateExtractor
- [ ] テスト - 80%以上カバレッジ

### Phase 2.3.2: 拡張（次回）

- [ ] LLM統合（Fallback機構）
- [ ] セッションレベル状態管理
- [ ] Director統合

---

## 成功基準

| 項目 | 目標 |
|------|------|
| テストカバレッジ | 80%以上 |
| シグナル検出精度 | 70%以上（手動評価） |
| 処理速度 | <10ms/turn |
| 既存テスト | 全てパス |

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-01-24 | 1.0 | 初版作成 |

---

*Source: Internal Design + ChatGPT Proposal*
