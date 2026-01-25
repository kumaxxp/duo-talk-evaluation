# Gate Test 仕様 v1.0

## 0. 目的
Gate Test は、HAKONIWA-G3 を段階的に「味見」しながら、手戻りを最小化するための検証手順です。
仕様上の正式名称は **Gate Test** とし、Taste は俗称として扱います。

---

## P0 Feature Freeze 宣言

**GM Service P0 は凍結状態です。**

### Freeze条件（DoD）

| 項目 | 条件 | 状態 |
|------|------|------|
| Crash | = 0（例外で落ちない。SchemaValidationErrorでの即停止はOK） | ✅ |
| format_break | raw/repaired/final のアーティファクト保存・参照・レポート化 | ✅ |
| scenario/world整合性 | registry + mismatch停止 + canonical/hash + world_summary | ✅ |
| preflight | MISSING_OBJECT/NOT_OWNED/WRONG_LOCATION 検出 + fact/guidance出力 | ✅ |
| retry | max_repair_steps=2、2回失敗でPASS + [GIVE_UP]（無限ループ禁止） | ✅ |

### 変更ポリシー

| 変更種別 | 許可 | 例 |
|----------|------|-----|
| ログ改善 | ✅ | より詳細なメトリクス出力 |
| GUI参照性向上 | ✅ | レポート可視化改善 |
| 判定ロジック変更 | ❌ | allowed/denied判定の変更 |
| 介入挙動変更 | ❌ | fact_cards/guidance_cards生成ロジック |
| リトライ挙動変更 | ❌ | max_repair_steps, give_up条件 |

**GMロジックに触る場合は、変更理由と影響範囲を明記すること。**

---

## 1. Gate‑Nav（移動制約）
### 目的
`scenario.yaml` の `locations[].exits[]` に基づき、移動可能性が厳密に制御されることを確認します。

### 合格観点（例）
- 移動可能な場所へは自然に移動できる
- 移動不可能な場所は **Thought段階で自律的に断念**する（ログ観察）
  - 例：`"cannot go"`, `"no exit"`, `"only way is"`, `"blocked"`

---

## 2. Gate‑Retry（Preflight + Turn内Retry）
### 目的
「禁止する（Hard Deny）」ではなく「気づかせる（Guidance）」で、Actor が **自律的に誤りを訂正**できることを確認します。

### 安全策（必須）
- `max_repair_steps = 2`（無限ループ防止のため固定）
- 2回失敗したら `PASS` にフォールバックし、ログに `[GIVE_UP]` を残す

### 合格ライン（初期）
- GIVE_UP Rate < 10%（Green）
- 10%〜20%（Yellow）：Hint 文面の調整
- 20% 以上（Red）：注入位置や設計の見直し

※ GM-017 以降は `retry_steps_extra = total_generation_calls - 1` を正規指標とし、平均 < 0.5 を目標にする。

---

## 3. Gate-3A（P0必須：安全性検証）

### 目的
GM Service P0の「壊れない・観測できる・世界が真実」を保証する最低限の品質ゲート。

**Gate-3AはP0ブロッカー。FAILの場合はリリース不可。**

### 合格基準

| Metric | Target | Priority |
|--------|--------|----------|
| give_up_rate | < 10% | P0 |
| avg_retry_steps_extra | < 0.5 | P0 |
| hard_denied_count | = 0 | P0 |
| GM Crash | = 0 | P0 |

### メトリクス定義

| Metric | Definition |
|--------|------------|
| give_up_rate | リトライ上限に達した割合（GIVE_UP / total_turns） |
| avg_retry_steps_extra | 1ターンあたりの追加LLM呼び出し回数（(total_gen_calls - turns) / turns） |
| hard_denied_count | Preflightでhard_deny=Trueが返った回数（P0では0であるべき） |
| GM Crash | 例外によるクラッシュ回数 |

---

## 3. Gate-3B（P1改善：品質向上）

### 目的
リトライ成功率を向上させ、LLMの自律修正能力を高める。

**Gate-3BはP1 Backlog。FAILでもP0リリースはブロックしない。**

### 合格基準（参考値）

| Metric | Target | Priority |
|--------|--------|----------|
| retry_success_rate | > 80% | P1 |
| silent_correction_rate | > 50% | P1 |

### メトリクス定義

| Metric | Definition |
|--------|------------|
| retry_success_rate | リトライ後に allowed=True となった割合 |
| silent_correction_rate | 謝罪なしで行動が変わった割合 |

### 改善方針
- guidance_cards文面のチューニング（Level2中心）
- AVAILABLE_NOWに加えて「代替アクション提案」の追加
- シナリオ別の誘導強化

---

## 4. Gate-3 実行条件

### 実行コマンド
```bash
python -m experiments.gm_2x2_runner \
  --experiment_id gate3_test \
  --profile gate \
  --conditions D \
  --scenarios coffee_trap wrong_location locked_door \
  --seeds 5 \
  --max_turns 10 \
  --mode real
```

### Silent Correction 判定

```
silent_correction = (action_changed) AND (NOT apology_detected)
```

謝罪語リスト: すみません, ごめん, 間違え, 失礼, 申し訳

### 出力レポート

1. **REPORT.md**: Gate-3A/3B Summary セクション
2. **CONVERSATION_REPORT.md**: ターン単位の詳細分析
3. **artifacts/**: raw_output, repaired_output, parsed.json

---

## 5. Gate‑Resilience（フォーマット修復）
### 目的
軽微な JSON 崩れ（末尾ゴミ、引用符ミス、カンマ等）を GM が修復し、**クラッシュせずに会話を継続**できることを確認します。

### 方針（ポステルの法則）
- **受信側（GM）は寛容**：`json.loads` 等の文法エラーは Repair で吸う
- **構造（Schema）エラー**：フィールド欠損などはプロンプト側（System Instruction / Few-shot）で直す

### 合格ライン（初期）
- `repair_steps >= 2` 発生率 < 5%
- GM Crash = 0

---

## Gate判定フロー

```
Gate-3A (P0) PASS?
    ├── YES → Gate-3B (P1) 評価 → レポート出力
    │           ├── PASS → 完全合格
    │           └── FAIL → P0合格、P1要改善
    └── NO  → P0ブロック（リリース不可）
```

---

*Last Updated: 2026-01-25 (P0 Freeze宣言, Gate-3A/3B分割)*
