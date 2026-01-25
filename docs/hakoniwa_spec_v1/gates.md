# Gate Test 仕様 v1.0

## 0. 目的
Gate Test は、HAKONIWA-G3 を段階的に「味見」しながら、手戻りを最小化するための検証手順です。  
仕様上の正式名称は **Gate Test** とし、Taste は俗称として扱います。

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

## 3. Gate-3（Preflight+Retry 総合検証）

### 目的
GM-015の「Preflight+RetryでHard Denyを回避」できる状態を、**gateプロファイル（seeds=5）×複数シナリオ**で再現し、品質を検証する。

### 実行条件
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

### 合格基準

| Metric | Target | Status |
|--------|--------|--------|
| retry_success_rate | > 80% | ✅/❌ |
| avg_retry_steps_extra | < 0.5 | ✅/❌ |
| give_up_rate | < 10% | ✅/❌ |
| GM Crash | = 0 | ✅/❌ |

### 主要メトリクス

| Metric | Definition |
|--------|------------|
| retry_success_rate | リトライ後に allowed=True となった割合 |
| avg_retry_steps_extra | 1ターンあたりの追加LLM呼び出し回数 |
| give_up_rate | リトライ上限に達した割合 |
| silent_correction_rate | 謝罪なしで行動が変わった割合 |

### Silent Correction 判定

```
silent_correction = (action_changed) AND (NOT apology_detected)
```

謝罪語リスト: すみません, ごめん, 間違え, 失礼, 申し訳

### 出力レポート

1. **REPORT.md**: Gate-3 Summary セクション
2. **CONVERSATION_REPORT.md**: ターン単位の詳細分析
3. **artifacts/**: raw_output, repaired_output, parsed.json

---

## 4. Gate‑Resilience（フォーマット修復）
### 目的
軽微な JSON 崩れ（末尾ゴミ、引用符ミス、カンマ等）を GM が修復し、**クラッシュせずに会話を継続**できることを確認します。

### 方針（ポステルの法則）
- **受信側（GM）は寛容**：`json.loads` 等の文法エラーは Repair で吸う
- **構造（Schema）エラー**：フィールド欠損などはプロンプト側（System Instruction / Few-shot）で直す

### 合格ライン（初期）
- `repair_steps >= 2` 発生率 < 5%
- GM Crash = 0

...（必要に応じて追記）

