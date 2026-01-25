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

## 3. Gate‑Resilience（フォーマット修復）
### 目的
軽微な JSON 崩れ（末尾ゴミ、引用符ミス、カンマ等）を GM が修復し、**クラッシュせずに会話を継続**できることを確認します。

### 方針（ポステルの法則）
- **受信側（GM）は寛容**：`json.loads` 等の文法エラーは Repair で吸う
- **構造（Schema）エラー**：フィールド欠損などはプロンプト側（System Instruction / Few-shot）で直す

### 合格ライン（初期）
- `repair_steps >= 2` 発生率 < 5%
- GM Crash = 0

...（必要に応じて追記）

