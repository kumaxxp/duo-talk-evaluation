# HAKONIWA-G3 仕様 v1.0（全体概要）

## 0. 目的
HAKONIWA-G3 は、**環境決定論（Environmental Determinism）** に基づく「箱庭」型の会話・行動システムです。  
ここでの原則は **World is Truth（世界が真実）** であり、AI（Actor）は **世界定義（The Stage）に記述された事実だけ** を根拠に、行動と発話を行います。

この仕様書は、プロジェクト内に散らばりがちな用語（Taste / Trap / Gate / GM など）と、構成要素（Runner / GM Service / Scenario）を、**実装可能な形**に固定します。

---

## 1. 非交渉ルール（Non‑negotiable）
### 1.1 World is Truth（世界が真実）
- 世界（Scenario / WorldState）に存在しないものは **存在しない**。
- 世界に定義されていない場所へは **移動できない**（`exits` グラフに従う）。
- 世界に定義されていない所有物は **持っていない**（`owner` に従う）。

### 1.2 No World Expansion（世界拡張の禁止）
- 失敗を減らすために「世界側（scenario/props）を増やす」方向には安易に倒れない。
- 代わりに、**正規化（alias/derived）**、**事前ガード（preflight）**、**ヒント提示（fact/guidance cards）** によって、Actor が自律的に修正する流れを作る。

---

## 2. システム構成（System Components）
HAKONIWA-G3 は大きく次の3層で構成されます。

### 2.1 Runner（実験実行器）
- 2×2 実験（A/B/C/D）を実行し、ログとメトリクスを集計します。
- `--profile dev|gate|full` により高速化（GM-016）を行い、開発サイクルを短縮します。

### 2.2 Generator（LLM 生成器）
- `SimGenerator`: シミュレーション出力（決定論的・高速）。
- `RealLLMGenerator`: Ollama などの実 LLM 呼び出し。
- `OpenAICompatibleGenerator`: vLLM/llama.cpp 等、OpenAI互換API。

### 2.3 GM Service（環境制御・審判）
- WorldState を「真実」として保持し、Actor の出力を判定・更新します。
- 主な役割：
  - **ActionJudge**: 不可能行動（MISSING_OBJECT / NOT_OWNED / WRONG_LOCATION / OUT_OF_SCOPE 等）の判定  
  - **WorldUpdater**: 正当な world_delta の適用  
  - **FactCard / Guidance**: 失敗時のヒント注入（Preflight / Retry）  
  - **Parser / Repair**: 出力フォーマット崩れの修復（GM-015 Resilience）

---

## 3. 用語体系（命名の3階層）
仕様書内では、用語を次の3階層に分けて管理します。

1) **System**（全体）：HAKONIWA‑G3  
2) **Component**（部品）：Runner / Generator / GM Service / Scenario  
3) **Experiment & Gate**（検証）：Experiment / Gate Test / Scenario

> 俗称の「Taste」は、仕様上は **Gate Test** を正式名称とし、Taste は俗称として扱います。

---

## 4. 実験（2×2）定義
2×2 実験は「注入（Inject）」と「GM」を ON/OFF で切り替えます。

| Condition | Inject | GM | 意味 |
|---|---:|---:|---|
| A | OFF | OFF | Baseline（素の生成） |
| B | ON  | OFF | Injectのみ（観測・注入の寄与を測る） |
| C | OFF | ON  | GMのみ（環境決定論の寄与を測る） |
| D | ON  | ON  | Full（運用想定） |

---

## 5. Gate Test（旧Taste）の考え方
Gate Test は「段階的に味見しながら、手戻りを最小化する」ためのゲートです。

- Gate‑Nav（旧Taste‑1）: `exits` による移動制限が理解されるか  
- Gate‑Retry（旧Taste‑3）: Preflight + Retry により **自己修正**できるか（最重要）  
- Gate‑Resilience（旧Taste‑4）: 多少の JSON 崩れを GM が吸収できるか  

---

## 6. 期待される振る舞い（What to expect）
### 6.1 期待する「賢さ」の正体
HAKONIWA-G3 が狙う賢さは「モデルが万能になる」ことではなく、

- **世界の制約が明示され**
- **間違いは環境からのフィードバックで気づけて**
- **自律的に修正できる**

という「舞台設計（Stage）による賢さ」です。

### 6.2 Silent Correction（黙って修正）
Retry の後、謝罪や言い訳ではなく、**行動だけが自然に変わる**ことを重視します。  
これによりユーザー体験上は「AIが最初から賢かった」ように見えます。

---

## 7. 今後の拡張（ガイドライン）
- 大規模マップ、リッチな持ち物、観測、未知情報（Hidden Object）などは増やせますが、v1.0 の基本は **YAML + スキーマ検証** で回します。
- DB/RAG を導入するのは、シナリオ数やアセット規模がボトルネック化してからで良い（詳細は Scenarios Spec を参照）。

