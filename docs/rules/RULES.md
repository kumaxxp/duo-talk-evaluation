# duo-talk-ecosystem 開発ルール

**Document ID**: RULES-001  
**Version**: 1.0.0  
**Last Updated**: 2026-01-30  
**Status**: Active  

---

## 1. 憲法（不可侵原則）

以下のルールは例外なく遵守すること。

### 1.1 品質に関する原則

```
第1条: 測定なき改善なし
  - 「良くなった気がする」は禁止
  - 全ての変更はA/Bテストまたは定量評価で検証すること

第2条: テストなきマージなし
  - PRは全テスト通過を必須とする
  - カバレッジ90%以上を維持すること

第3条: ドキュメントなき機能なし
  - 新機能には必ずドキュメントを添付すること
  - 仕様変更時は関連ドキュメントを同時更新すること
```

### 1.2 安全に関する原則

```
第4条: P0 Safety First
  - GM判定: パース失敗 → 拒否しない（許可方向へフォールバック）
  - Director判定: 検出失敗 → ブロックしない
  - 誤検出より見逃しを許容する

第5条: 破壊的変更の禁止
  - 既存のAPIシグネチャを変更する場合は deprecation warning を1リリース挟むこと
  - 設定ファイルフォーマットの変更は migration script を提供すること
```

---

## 2. ブランチ戦略

### 2.1 ブランチ命名規則

| Prefix | Purpose | Example |
|:-------|:--------|:--------|
| `main` | 本番リリース可能な安定版 | `main` |
| `feature/` | 新機能開発 | `feature/phase32-rag-injection` |
| `fix/` | バグ修正 | `fix/tone-marker-detection` |
| `docs/` | ドキュメント更新 | `docs/update-strategy` |
| `exp/` | 実験的機能（マージ前提なし） | `exp/new-llm-backend` |

### 2.2 ブランチフロー

```
main ◄──────────────────────────────────────────
  │                    │                    │
  ├─► feature/xxx ─────┤                    │
  │         │          │                    │
  │         └─► PR ────┴─► merge ──────────►│
  │                                         │
  ├─► fix/yyy ─────────────────────────────►│
  │                                         │
  └─► docs/zzz ────────────────────────────►│
```

### 2.3 マージ条件

- [ ] 全テスト通過
- [ ] レビュー承認（セルフレビュー可）
- [ ] 関連ドキュメント更新済み
- [ ] CHANGELOG に変更内容記載

---

## 3. コーディング規約

### 3.1 Python

```python
# ✅ Good
class DirectorHybrid(DirectorProtocol):
    """Hybrid Director with RAG injection capability.
    
    Combines static checks with LLM-based evaluation.
    """
    
    def __init__(
        self,
        rag_enabled: bool = False,
        inject_enabled: bool = False,
    ) -> None:
        self.rag_enabled = rag_enabled
        self.inject_enabled = inject_enabled


# ❌ Bad
class director_hybrid:
    def __init__(self, rag=False, inject=False):
        self.rag = rag
        self.inject = inject
```

**必須事項**:
- Type hints を全ての関数・メソッドに付与
- Docstring を全ての公開クラス・関数に付与
- `ruff` によるリント通過

### 3.2 設定ファイル

```yaml
# ✅ Good: 明示的なキー名
character:
  name: "やな"
  tone_markers:
    - "じゃん"
    - "よね"

# ❌ Bad: 曖昧なキー名
c:
  n: "やな"
  t:
    - "じゃん"
```

---

## 4. テスト規約

### 4.1 テストファイル命名

| Type | Pattern | Example |
|:-----|:--------|:--------|
| Unit Test | `test_<module>.py` | `test_tone_check.py` |
| Integration Test | `test_<feature>_integration.py` | `test_rag_integration.py` |
| E2E Test | `e2e_<scenario>.py` | `e2e_coffee_trap.py` |

### 4.2 テスト構造

```python
class TestToneChecker:
    """ToneChecker unit tests."""
    
    def test_yana_markers_detected(self):
        """やなの口調マーカーが正しく検出されること"""
        # Arrange
        checker = ToneChecker(character="yana")
        text = "それって面白いじゃん！"
        
        # Act
        result = checker.check(text)
        
        # Assert
        assert result.status == CheckStatus.PASS
        assert result.score >= 2
    
    def test_empty_input_returns_warn(self):
        """空入力でWARNを返すこと"""
        # ...
```

### 4.3 カバレッジ要件

| Repository | Minimum Coverage |
|:-----------|:----------------:|
| duo-talk-core | 90% |
| duo-talk-director | 90% |
| duo-talk-gm | 85% |
| duo-talk-evaluation | 80% |

---

## 5. ドキュメント規約

### 5.1 ドキュメント種別

| Type | Location | Purpose |
|:-----|:---------|:--------|
| Strategy | `docs/strategy/` | 戦略・方針 |
| Rules | `docs/rules/` | 開発ルール |
| Architecture | `docs/architecture/` | 設計図・構成 |
| Specs | `specs/` | 機能仕様書 |
| Reports | `results/` | 実験結果レポート |

### 5.2 ドキュメントフォーマット

```markdown
# タイトル

**Document ID**: XXX-NNN  
**Version**: X.Y.Z  
**Last Updated**: YYYY-MM-DD  
**Status**: Draft | Active | Deprecated  

---

## 1. 概要

## 2. 詳細

## N. Document Control

| Version | Date | Author | Changes |
|:--------|:-----|:-------|:--------|
```

---

## 6. コミット規約

### 6.1 コミットメッセージ形式

```
<type>: <subject>

<body>

<footer>
```

### 6.2 Type一覧

| Type | Description |
|:-----|:------------|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `docs` | ドキュメント |
| `test` | テスト追加・修正 |
| `refactor` | リファクタリング |
| `perf` | パフォーマンス改善 |
| `chore` | その他（CI設定等） |

### 6.3 例

```
feat: Phase 3.2 RAG injection実装

- DirectorHybridにinject_enabled フラグ追加
- get_facts_for_injection() メソッド実装
- A/B比較の公平性向上

Closes #42
```

---

## 7. レビュー規約

### 7.1 レビュー観点

| Category | Check Items |
|:---------|:------------|
| 機能 | 要件を満たしているか |
| テスト | テストが十分か、エッジケースは網羅されているか |
| 可読性 | コードが理解しやすいか、命名は適切か |
| 安全性 | P0原則に違反していないか |
| ドキュメント | 必要なドキュメントが更新されているか |

### 7.2 レビューコメント形式

```
[MUST] 必ず修正が必要
[SHOULD] 修正を推奨
[NIT] 些細な指摘（任意）
[Q] 質問・確認
```

---

## 8. 実験規約

### 8.1 実験命名

```
<type>_<description>_<date>_<sequence>
```

例:
- `director_ab_20260125_001234`
- `gm_2x2_coffee_trap_20260125_145045`

### 8.2 実験結果の保存

```
results/
└── <experiment_id>/
    ├── config.json       # 実験設定
    ├── results.json      # 生データ
    ├── summary.md        # サマリーレポート
    └── logs/             # 詳細ログ
```

### 8.3 実験の再現性

全ての実験は以下を記録すること:
- 使用モデル（名前、バージョン）
- 設定パラメータ（temperature, max_tokens等）
- 入力データ（シナリオID、シード値）
- 環境情報（OS、Python版、依存ライブラリ版）

---

## 9. 違反時の対応

### 9.1 軽微な違反

- レビュー時に指摘
- 修正後マージ可

### 9.2 重大な違反

- PRリジェクト
- 是正計画の提出を要求

### 9.3 憲法違反

- 即時リバート
- インシデントレポート作成
- 再発防止策の策定

---

## 10. Document Control

| Version | Date | Author | Changes |
|:--------|:-----|:-------|:--------|
| 1.0.0 | 2026-01-30 | HQ Staff | Initial creation |

---

*このルールは全開発者に適用される。*  
*例外が必要な場合は、事前に HQ に相談すること。*
