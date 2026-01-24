# Phase 3.2: RAG Injection 完了レポート

**作成日**: 2026-01-25
**ステータス**: ✅ 完了

---

## 1. 概要

Phase 3.1で構築したRAG観察基盤を活用し、検出したFACTを会話生成プロンプトに注入する機能を実装。
A/Bテストにより、注入による効果を定量的に検証した。

## 2. 実装内容

### 2.1 DirectorHybrid拡張

**ファイル**: `duo-talk-director/src/duo_talk_director/director_hybrid.py`

```python
class DirectorHybrid(DirectorProtocol):
    def __init__(
        self,
        rag_enabled: bool = False,
        inject_enabled: bool = False,  # Phase 3.2で追加
        ...
    ):
        self.inject_enabled = inject_enabled
```

**主要メソッド**:
- `get_facts_for_injection()`: プロンプト注入用FACTを返却
- `_observe_and_detect()`: 違反パターン検出（常時実行）

### 2.2 検出ロジック

以下の違反パターンを検出:

| パターン | 検出条件 |
|---------|---------|
| prohibited_terms | 禁止用語（「姉様」をやなが使用など） |
| blocked_props | 存在しない小物の使用 |
| tone_violation | 口調違反（やなが敬語など） |
| addressing_violation | 呼称違反（あゆが「やなちゃん」など） |

### 2.3 InjectionDecision

```python
@dataclass
class InjectionDecision:
    would_inject: bool = False
    reasons: list[str] = field(default_factory=list)
    facts_injected: int = 0
    predicted_blocked_props: list[str] = field(default_factory=list)
    detected_tone_violation: bool = False
    detected_addressing_violation: bool = False
```

### 2.4 公平なA/B比較の実装

**重要な修正** (2026-01-25):

```python
# 検出ロジックは inject_enabled に関係なく実行
# Facts返却のみを inject_enabled で制御

def get_facts_for_injection(...):
    # Step 1: 常に検出を実行
    reasons = detect_violations(...)

    # Step 2: decision に記録（両条件で透明性確保）
    decision.reasons = reasons
    decision.would_inject = len(reasons) > 0

    # Step 3: inject_enabled で返却を制御
    if not self.inject_enabled:
        decision.facts_injected = 0  # 観察のみ
        return []

    # Step 4: facts を選択して返却
    return select_facts(reasons)
```

---

## 3. A/Bテスト結果

### 3.1 Phase 3.2シナリオ（違反誘発）

**実験ID**: `director_ab_20260125_005100`

| メトリクス | Observe (A) | Inject (B) | Delta |
|------------|:-----------:|:----------:|:-----:|
| 成功数 | 6 | 6 | - |
| 総リトライ数 | 4 | 2 | **-2** |
| 平均リトライ数 | 0.67 | 0.33 | - |
| Facts注入数 | 0 | 12 | - |

**RAGトリガー内訳**:
- prohibited_terms: 4回
- tone_violation: 4回
- addressing_violation: 4回

### 3.2 標準シナリオ（通常会話）

**実験ID**: `director_ab_20260125_005539`

| メトリクス | Observe (A) | Inject (B) | Delta |
|------------|:-----------:|:----------:|:-----:|
| 成功数 | 6 | 6 | - |
| 総リトライ数 | 1 | 1 | 0 |
| 平均リトライ数 | 0.17 | 0.17 | - |

**結論**: 通常会話では注入の有無で差なし（副作用なし）

---

## 4. 結論

### 4.1 効果

| 項目 | 結果 |
|------|------|
| リトライ削減 | ✅ 違反シナリオで50%削減（4→2回） |
| 副作用 | ✅ 通常会話への影響なし |
| 検出精度 | ✅ 違反パターンを正確に検出 |
| A/B公平性 | ✅ 検出ロジックは両条件で同一 |

### 4.2 課題

1. **addressing_violation** での効果が限定的（リトライ同数のケースあり）
2. LLMが注入FACTを無視するケースが存在
3. より多くのシナリオ・実行回数での検証が必要

### 4.3 推奨事項

- **本番適用**: `rag_enabled=True, inject_enabled=True` を推奨
- **段階的導入**: まず `inject_enabled=False` で観察、問題なければ有効化

---

## 5. 関連ファイル

| ファイル | 役割 |
|----------|------|
| [director_hybrid.py](../../../duo-talk-director/src/duo_talk_director/director_hybrid.py) | RAG注入実装 |
| [director_ab_test.py](../../experiments/director_ab_test.py) | A/Bテストフレームワーク |
| [PHASE3_1_RAG_SPEC.md](PHASE3_1_RAG_SPEC.md) | Phase 3.1仕様書 |

---

## 6. Git履歴

```
5781cc0 fix: A/B比較の公平性向上 - inject_enabled=Falseでも検出ロジックを実行
e960c8c feat: Phase 3.2 RAG injection基本実装
```

---

*Report generated: 2026-01-25*
