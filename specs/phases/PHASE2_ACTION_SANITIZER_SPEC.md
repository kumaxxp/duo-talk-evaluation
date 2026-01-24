# 仕様書: ActionSanitizer軽量版

**文書ID**: 20260124_004
**作成日**: 2026-01-24
**フェーズ**: Phase 2.2.1
**ステータス**: Approved
**情報源**: ChatGPT詳細仕様

---

## 概要

Action内の不正props（眼鏡、コーヒー等）を検出し、Sceneに存在しない場合は削除または汎用動作に置換するサニタイザー。RETRYではなく後処理で対応することで、生成フローへの影響を最小化。

---

## 設計原則

| 原則 | 内容 |
|------|------|
| 軽量 | 形態素解析なし、辞書マッチのみ |
| 非破壊 | RETRYせず、削除/置換で対応 |
| ログ重視 | 頻度計測で将来判断の材料収集 |

---

## 1. Action形式の正規化

### 1.1 許可形式（Phase2出力の正規形）

```
（行動）「台詞」
「台詞」（行動なし）
```

### 1.2 禁止形式

```
*行動*  ← 今後禁止、見つけたらサニタイズ対象
```

### 1.3 Phase2プロンプトへの追加

```yaml
# two_pass_generator.py の output_prompt に追加
output_format:
  action: "（...）形式のみ。*...*は使用禁止"
  dialogue: "「...」形式"
  order: "（行動）「台詞」の順"
```

---

## 2. NG物品辞書（初期セット）

### 2.1 物品NG辞書

```python
PROPS_NG_DICT = {
    # 飲み物
    "コーヒー", "珈琲", "カップ", "グラス", "ワイン", "ビール", "お茶", "紅茶",
    # アクセサリー
    "眼鏡", "メガネ", "めがね", "サングラス", "指輪", "ネックレス", "イヤリング",
    # 電子機器
    "スマホ", "携帯", "パソコン", "PC", "タブレット",
    # 喫煙
    "タバコ", "煙草", "たばこ", "ライター",
    # その他小物
    "本", "雑誌", "新聞", "ペン", "ノート", "バッグ", "傘",
}
```

### 2.2 身体動作（セーフリスト）

```python
BODY_ACTIONS_SAFE = {
    # 表情
    "微笑む", "笑う", "目を細める", "眉をひそめる", "首をかしげる",
    # 呼吸
    "ため息", "深呼吸", "一息つく",
    # 動作
    "頷く", "首を振る", "肩をすくめる", "手を振る",
}
```

---

## 3. インターフェース

### 3.1 入力

```python
@dataclass
class SanitizerInput:
    output_text: str  # Phase2の出力（1行想定）
    scene_items: list[str]  # inventory + nearby + temporary を連結
```

### 3.2 出力

```python
@dataclass
class SanitizerResult:
    sanitized_text: str
    action_removed: bool
    action_replaced: bool
    blocked_props: list[str]
    original_action: str | None
```

---

## 4. 処理ロジック

### 4.1 フローチャート

```
1. Action抽出
   └─ 先頭 （...） or *...* があればAction

2. Action内のNG物品語を辞書で検出
   └─ PROPS_NG_DICT との一致チェック

3. 検出語がScene itemに含まれるか確認
   └─ scene_items を正規化（lower化、記号除去）してマッチ

4. ブロック時の処理（優先順）
   ├─ 置換可能 → 汎用動作に置換
   └─ 無理 → 削除（台詞のみ残す）

5. ログ記録
```

### 4.2 実装コード

```python
import re
from dataclasses import dataclass


@dataclass
class SanitizerResult:
    sanitized_text: str
    action_removed: bool = False
    action_replaced: bool = False
    blocked_props: list[str] = None
    original_action: str | None = None

    def __post_init__(self):
        if self.blocked_props is None:
            self.blocked_props = []


class ActionSanitizer:
    """Action内の不正propsを検出し、削除または置換する（軽量版）"""

    # Action抽出パターン
    ACTION_PATTERN = re.compile(r"^（([^）]+)）")
    ACTION_ASTERISK_PATTERN = re.compile(r"^\*([^*]+)\*")

    # NG物品辞書
    PROPS_NG_DICT = {
        "コーヒー", "珈琲", "カップ", "グラス", "ワイン", "ビール", "お茶", "紅茶",
        "眼鏡", "メガネ", "めがね", "サングラス", "指輪", "ネックレス", "イヤリング",
        "スマホ", "携帯", "パソコン", "PC", "タブレット",
        "タバコ", "煙草", "たばこ", "ライター",
        "本", "雑誌", "新聞", "ペン", "ノート", "バッグ", "傘",
    }

    # 汎用置換アクション
    FALLBACK_ACTIONS = {
        "飲む": "一息つく",
        "コーヒー": "一息つく",
        "眼鏡": "目を細める",
        "スマホ": "考え込む",
        "本": "考え込む",
        "タバコ": "一息つく",
    }
    DEFAULT_FALLBACK = "小さく頷く"

    def sanitize(
        self,
        output_text: str,
        scene_items: list[str],
    ) -> SanitizerResult:
        """Actionをサニタイズする

        Args:
            output_text: Phase2の出力テキスト
            scene_items: Sceneに存在するアイテム一覧

        Returns:
            SanitizerResult
        """
        if not output_text:
            return SanitizerResult(sanitized_text="")

        # Scene itemsを正規化
        normalized_scene = self._normalize_scene_items(scene_items)

        # Action抽出
        action, action_type = self._extract_action(output_text)
        if not action:
            return SanitizerResult(sanitized_text=output_text)

        # NG物品検出
        blocked = self._detect_blocked_props(action, normalized_scene)
        if not blocked:
            return SanitizerResult(
                sanitized_text=output_text,
                original_action=action,
            )

        # ブロック発生 → 置換または削除
        return self._handle_blocked_action(
            output_text=output_text,
            action=action,
            action_type=action_type,
            blocked_props=blocked,
        )

    def _extract_action(self, text: str) -> tuple[str | None, str | None]:
        """Actionを抽出"""
        # （...）形式
        match = self.ACTION_PATTERN.match(text)
        if match:
            return match.group(1), "parentheses"

        # *...*形式（禁止形式だが検出）
        match = self.ACTION_ASTERISK_PATTERN.match(text)
        if match:
            return match.group(1), "asterisk"

        return None, None

    def _normalize_scene_items(self, items: list[str]) -> set[str]:
        """Scene itemsを正規化"""
        normalized = set()
        for item in items:
            # lower化、記号除去
            clean = re.sub(r"[^\w\s]", "", item.lower())
            normalized.add(clean)
            # 元の形も追加
            normalized.add(item)
        return normalized

    def _detect_blocked_props(
        self,
        action: str,
        normalized_scene: set[str],
    ) -> list[str]:
        """Action内のNG物品を検出"""
        blocked = []
        for prop in self.PROPS_NG_DICT:
            if prop in action:
                # Sceneに存在するかチェック
                if prop not in normalized_scene and prop.lower() not in normalized_scene:
                    blocked.append(prop)
        return blocked

    def _handle_blocked_action(
        self,
        output_text: str,
        action: str,
        action_type: str,
        blocked_props: list[str],
    ) -> SanitizerResult:
        """ブロックされたActionを処理"""
        # 置換を試みる
        fallback = self._get_fallback_action(blocked_props)

        if fallback:
            # 置換
            if action_type == "parentheses":
                sanitized = re.sub(
                    r"^（[^）]+）",
                    f"（{fallback}）",
                    output_text,
                )
            else:  # asterisk
                sanitized = re.sub(
                    r"^\*[^*]+\*",
                    f"（{fallback}）",  # 正規形に変換
                    output_text,
                )
            return SanitizerResult(
                sanitized_text=sanitized,
                action_replaced=True,
                blocked_props=blocked_props,
                original_action=action,
            )
        else:
            # 削除
            if action_type == "parentheses":
                sanitized = re.sub(r"^（[^）]+）\s*", "", output_text)
            else:
                sanitized = re.sub(r"^\*[^*]+\*\s*", "", output_text)
            return SanitizerResult(
                sanitized_text=sanitized,
                action_removed=True,
                blocked_props=blocked_props,
                original_action=action,
            )

    def _get_fallback_action(self, blocked_props: list[str]) -> str | None:
        """ブロックされたpropsから置換アクションを決定"""
        for prop in blocked_props:
            if prop in self.FALLBACK_ACTIONS:
                return self.FALLBACK_ACTIONS[prop]
        return self.DEFAULT_FALLBACK
```

---

## 5. 評価ログ指標

### 5.1 必須指標

| 指標 | 説明 |
|------|------|
| `action_sanitized_rate` | Action削除/置換された割合 |
| `blocked_props_topN` | 頻出ブロックprops |
| `action_removed_count` | 削除回数 |
| `action_replaced_count` | 置換回数 |

### 5.2 ログ形式

```python
{
    "turn": 3,
    "speaker": "やな",
    "sanitizer": {
        "triggered": True,
        "action_removed": False,
        "action_replaced": True,
        "blocked_props": ["コーヒー"],
        "original_action": "コーヒーを飲みながら",
        "replacement": "一息つく",
    }
}
```

---

## 6. 統合位置

### 6.1 Director内での位置

```
[Response生成]
    ↓
[ActionSanitizer] ← ここ（静的チェック前）
    ↓
[DirectorMinimal/Hybrid]
    ↓
[最終出力]
```

### 6.2 理由

- 静的チェック前にサニタイズすることで、ToneChecker等が正常に動作
- Director判定には影響なし（サニタイズ後のテキストを評価）

---

## 7. 成功基準

| 項目 | 目標 |
|------|------|
| 実装完了 | ActionSanitizer クラス |
| テストカバレッジ | 80%以上 |
| ログ出力 | サニタイズ発生時に記録 |
| 体感 | propsハルシネーションによる没入感低下なし |

---

## 8. 関連文書

- [ARCH_CHATGPT_REVIEW_FEEDBACK_20260124.md](../architecture/ARCH_CHATGPT_REVIEW_FEEDBACK_20260124.md)
- [機能一覧.md](../../docs/機能一覧.md)

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-01-24 | 1.0 | 初版作成（ChatGPT詳細仕様に基づく） |

---

*Source: ChatGPT詳細仕様（2026-01-24）*
