# 仕様書: ChatGPT提案レビューへのフィードバック

**文書ID**: 20260124_003
**作成日**: 2026-01-24
**フェーズ**: Phase 2.2.1 / 最適化
**ステータス**: Review
**情報源**: ChatGPT（レビュー結果へのフィードバック）

---

## 概要

ARCH_CHATGPT_RECOMMENDATIONS_20260124.md の判断に対するChatGPTからの追加フィードバック。1点の修正提案と2点の先回り提案を含む。

---

## フィードバック一覧

| # | 内容 | 種類 | 判定 |
|---|------|------|------|
| 1 | ActionWhitelistChecker軽量版先行導入 | 修正 | 🟢 採用 |
| 2 | Thought再利用性を比較実験の評価軸に追加 | 追加 | 🟢 採用 |
| 3 | DirectorHybridを「失敗収集役」として明文化 | 追加 | 🟢 採用 |

---

## フィードバック1: ActionWhitelistChecker軽量版先行導入

### ChatGPTの意見

> 「propsハルシネーション頻度」は、
> - ユーザー体験上は **1回でも違和感が強い**
> - 数字で測ると **頻度は低く出やすい**
> - しかし **印象としては致命的**
>
> 眼鏡・コーヒー・アクセサリー → *「あ、作り物だ」* と一瞬で没入が切れる
>
> これは **5%ルールが合わない不具合**。

### 修正提案

| 元の判断 | 修正後 |
|---------|--------|
| 🟡検討（頻度計測後） | 🟢採用（軽量版を先行導入） |

### 軽量版の仕様

```python
# ActionSanitizer（軽量版）
class ActionSanitizer:
    """Action内の不正propsを検出し、Actionを削除する（RETRYではない）"""

    def sanitize(self, response: str, scene_context: dict) -> str:
        action = self._extract_action(response)
        if not action:
            return response

        # Action内の名詞を1個だけ抽出
        noun = self._extract_main_noun(action)

        # Sceneに存在しない場合
        if noun and noun not in scene_context.get("available_props", []):
            # Actionを削除、台詞のみ通す
            return self._remove_action(response)

        return response
```

### 妥当性評価

| 観点 | 評価 | 理由 |
|------|------|------|
| 効果 | ⭐⭐⭐ | 体感改善大（没入感維持） |
| リスク | 低 | RETRYではなく削除なので生成フロー影響なし |
| 実装コスト | 低 | 名詞抽出+条件削除のみ |
| 現行との整合性 | 問題なし | Directorチェックと独立 |

### 判定: 🟢 採用

**理由**:
- 5%ルールが適用できない「印象問題」への対処
- 軽量実装で体感改善と計測を両立
- ログ収集で将来の本格版判断材料になる

**実装方針**:
1. `ActionSanitizer` クラスを `duo-talk-director/checks/` に追加
2. DirectorMinimalに組み込み（オプション）
3. サニタイズ発生時はログ出力（頻度計測用）

---

## フィードバック2: Thought再利用性を評価軸に追加

### ChatGPTの意見

> TWO_PASS vs Two-Phase 比較実験に「**Thoughtの再利用性**」を追加すべき
>
> - Two-Phase: Thoughtが *そのまま次ターンに意味を持つか*
> - TWO_PASS: Thoughtが *そのターン限りの内部メモで終わっていないか*
>
> これは将来、State Updater / 感情持続 / キャラの一貫性 に直結する。

### 現状確認

| 項目 | 状態 |
|------|------|
| 比較実験計画 | ✅ 採用済み（ARCH_CHATGPT_RECOMMENDATIONS） |
| 評価軸 | フォーマット成功率、リトライ回数、品質スコア |
| Thought再利用性 | ❌ 未計測 |

### 追加評価軸

```python
# 比較実験の評価軸（追加）
evaluation_metrics = {
    # 既存
    "format_success_rate": float,
    "retry_count": int,
    "quality_score": float,

    # 追加
    "thought_reusability": {
        "cross_turn_coherence": float,  # 前ターンThoughtとの関連度
        "state_extractability": float,   # 状態情報の抽出可能性
        "emotion_continuity": float,     # 感情の持続性
    }
}
```

### 妥当性評価

| 観点 | 評価 | 理由 |
|------|------|------|
| 効果 | ⭐⭐ | 将来のState Updater判断材料 |
| リスク | 低 | ログ追加のみ |
| 実装コスト | 低 | 評価項目追加のみ |
| 現行との整合性 | 問題なし | 既存実験に追加 |

### 判定: 🟢 採用

**理由**: 将来のアーキテクチャ判断に必要な情報を今から収集

**実装方針**:
1. 比較実験スクリプトに評価軸追加
2. 今は手動評価でも可（自動化は後）
3. ログにThought内容を保存

---

## フィードバック3: DirectorHybridの役割明文化

### ChatGPTの意見

> DirectorHybrid は
> **「生成を止める存在」ではなく「失敗例を集める存在」**
>
> - 本番では *決して前段に置かない*
> - バッチ評価・夜間実験・CI的チェック専用

### 現状確認

| 項目 | 状態 |
|------|------|
| 使い分け戦略 | ✅ 採用済み（本番:Minimal / 実験:Hybrid） |
| 役割の明文化 | △ 「評価・実験用」とのみ記載 |

### 明文化案

```markdown
## DirectorHybridの役割定義

DirectorHybridは**失敗例収集器**である。

### 用途
- バッチ評価（夜間実行）
- 実験・A/Bテスト
- CI/CDパイプライン品質チェック

### 禁止事項
- ❌ 本番環境のリアルタイム生成には使用しない
- ❌ ユーザー体験に直接影響する場所に配置しない

### 理由
- LLM呼び出しによるレイテンシ（1-3秒）
- 本番での役割はDirectorMinimalで十分
```

### 妥当性評価

| 観点 | 評価 | 理由 |
|------|------|------|
| 効果 | ⭐⭐ | 将来の誤用防止 |
| リスク | 低 | ドキュメント整備のみ |
| 実装コスト | 低 | 機能一覧.md更新のみ |
| 現行との整合性 | 問題なし | 既存方針の明確化 |

### 判定: 🟢 採用

**理由**: 将来の自分・他人による誤用を防止

**実装方針**:
1. 機能一覧.mdの「Directorタイプ」セクションに追記
2. README.mdにも注意書き追加

---

## 計画への反映

### 修正後のPhase 2.2.1

```
Phase 2.2.1 (最適化) - 修正版
  ├── [採用] TWO_PASSデフォルト化
  ├── [採用] Director使い分けドキュメント整備
  │     └── [追加] DirectorHybrid = 失敗収集役として明文化
  ├── [採用] TWO_PASS vs Two-Phase比較実験
  │     └── [追加] Thought再利用性を評価軸に追加
  └── [追加] ActionSanitizer軽量版導入
```

### 修正後のPhase 2.3

```
Phase 2.3 (品質向上) - 修正版
  ├── [既存] NoveltyGuard（話題ループ検出）
  └── [変更] ActionWhitelistChecker
        ↓
        Phase 2.2.1で軽量版を先行導入済み
        必要に応じて本格版に拡張
```

---

## 次のアクション

### 即座に実行（Phase 2.2.1）

| アクション | 担当 | 優先度 |
|-----------|------|--------|
| TWO_PASSデフォルト化 | duo-talk-core | 高 |
| ActionSanitizer軽量版実装 | duo-talk-director | 高 |
| DirectorHybrid役割明文化 | duo-talk-evaluation (docs) | 中 |
| 比較実験にThought再利用性追加 | duo-talk-evaluation | 中 |

### 成果物

| 成果物 | 内容 |
|--------|------|
| ActionSanitizer | `checks/action_sanitizer.py` |
| 比較実験スクリプト | `experiments/generation_mode_comparison.py` |
| 更新ドキュメント | `docs/機能一覧.md` |

---

## 関連文書

- [ARCH_CHATGPT_RECOMMENDATIONS_20260124.md](./ARCH_CHATGPT_RECOMMENDATIONS_20260124.md) - 元の提案
- [機能一覧.md](../../docs/機能一覧.md) - 機能一覧

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-01-24 | 1.0 | 初版作成（ChatGPTフィードバックに基づく） |

---

*Source: ChatGPT分析（2026-01-24）*
