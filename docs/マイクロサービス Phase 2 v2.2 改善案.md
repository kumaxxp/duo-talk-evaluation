# duo-talk Phase 2 v2.2 Improvement Spec

**Version:** 2.2.0 (Thought Injection)
**Date:** 2026-01-23
**Target:** 「Thought出力率 100%」をシステム的に保証し、リトライを根絶する。

---

## 1. 問題の核心と解決アプローチ

### 現状の分析

レポートによると、v0.4（ThoughtCheckerあり）でのリトライ数が劇的に増加しました。
原因は **「LLMが自発的に `Thought:` というラベルを出力する確率が約60%しかない」** ことにあります。

v3.6/v3.8の実験で成功したのは、Pythonコード側で `Thought:` を **Prefill（先行入力）** していたからです。
しかし、現在の `duo-talk-core` と `Director` の連携において、このPrefillロジックが以下のいずれかの理由で機能していません。

1. **統合時の漏れ**: AdapterがPrefillを行っていない。
2. **文字列結合ミス**: Prefillした `Thought:` 文字列を、Directorに渡す前に結合し忘れている（そのためDirectorは「Thoughtがない」と判定する）。
3. **リトライ時の欠落**: 初回はPrefillしているが、Directorからのリトライ要求時（`Retry Prompt`）にはPrefillが含まれていない。

### 解決策: "Thought Injection" (思考注入)

プロンプトで「Thought形式で書いて」と頼む（Soft Enforcement）のはやめます。
**「システムが常に `Thought:` から書き始めさせ、LLMにはその続きだけを書かせる（Hard Enforcement）」** 仕組みを、初回生成だけでなく**リトライ時にも徹底**します。

---

## 2. 実装詳細

### A. Core実装の修正 (V38Adapterの厳格化)

`duo-talk-core` の生成ロジックにおいて、LLMの出力に依存せず、システム側でヘッダーを保証します。

```python
# duo_talk_core/adapters/v38_adapter.py

def generate(self, messages, ...):
    # 1. リクエスト作成: 常に "Thought:" を末尾に注入する
    # これは初回リクエストでも、Directorからのリトライリクエストでも共通で行う
    messages_with_prefill = messages + [{"role": "assistant", "content": "Thought:"}]

    # 2. 生成実行 (Ollama/LLM)
    raw_response = self.client.generate(messages_with_prefill, ...)

    # 3. 結合保証 (Crucial Fix)
    # LLMは "Thought:" の続き（中身）しか返さないため、
    # システム側で必ずヘッダーを付与して復元する。
    
    # 既に "Thought:" で始まっている場合（稀なケース）はそのまま、
    # そうでなければ付与する。
    if not raw_response.strip().startswith("Thought:"):
        full_response = "Thought: " + raw_response
    else:
        full_response = raw_response

    return full_response

```

### B. Directorのリトライロジック修正

Directorがリトライを要求する際、エラーメッセージ（Feedback）を送るだけでなく、**「次はどう書き始めるべきか」** を誘導する必要がありますが、上記のCore改修（常にThought注入）があれば、Director側は特別な変更をしなくても自動的に解決します。

ただし、**空Thought（`Thought: ( )`）** の問題 に対処するため、Directorのチェックロジックを微調整します。

### C. ThoughtCheckerの判定ロジック緩和

「空の思考」や「短すぎる思考」でリトライするのはコストが高すぎます。
形式さえ合っていれば（`Thought:` があれば）、中身が薄くても **PASS** させます。

```python
# duo_talk_director/checkers/thought_checker.py

def check(self, text: str) -> CheckResult:
    # 1. Thoughtブロックの検出
    match = re.search(r"^Thought:(.*?)(?=\nOutput:|$)", text, re.DOTALL | re.IGNORECASE)
    
    if not match:
        # Coreの改修でこれはあり得ないはずだが、念のため
        return CheckResult(status="RETRY", reason="Format Error: Missing 'Thought:'")
    
    content = match.group(1).strip()
    
    # 2. 空Thoughtの判定緩和
    # () のみや空文字でも、Outputがあれば一旦許容する（リトライコスト削減のため）
    if not content or content == "()":
        # RETRYではなくWARN（ログに残すだけ）にする
        return CheckResult(status="PASS", score=0.5, reason="Warning: Empty thought")
        
    return CheckResult(status="PASS", score=1.0)

```

---

## 3. プロンプト（Few-shot）の補強

LLMが「Thoughtの書き方」を忘れないよう、Few-shotの例を増強し、`Thought:` が必ず先頭に来るパターンを刷り込みます。

```json
"few_shots": [
  {
    "user": "おはよう",
    "assistant": "Thought: (Yana: 朝から元気よく挨拶しなきゃ！)\nOutput: (笑顔で) 「おはよう！今日もいい天気だね！」"
  },
  {
    "user": "GPU欲しい",
    "assistant": "Thought: (Ayu: 予算と電力が心配…。)\nOutput: *ため息をついて* 「姉様、コスト計算はしましたか？」"
  },
  {
    "user": "..." 
    // 例を3つ以上に増やす
  }
]

```

---

## 4. 期待される効果

この修正により、以下の劇的な改善が見込まれます。

| メトリクス | v0.4 (現状) | v2.2 (改善後) | 根拠 |
| --- | --- | --- | --- |
| **Thought欠落率** | 40% | **0%** | システムによる強制付与（Injection）のため。 |
| **平均リトライ数** | 10.67回 | **0〜1回** | フォーマットエラーによるリトライが消滅するため。 |
| **実行時間** | 35秒 | **10秒前後** | リトライ地獄からの脱却。 |

---

## 5. 開発タスクリスト

1. **[Core] Adapter改修**: `generate` メソッドで `messages` の末尾に必ず `{"role": "assistant", "content": "Thought:"}` を付与するロジックを実装。
2. **[Core] レスポンス復元**: LLMからの返答に `Thought:` プレフィックスを結合して返す処理を確認・修正。
3. **[Director] ThoughtChecker緩和**: 空ThoughtをRETRYではなくWARNに変更。

この「Software-Assisted Generation（システム補助生成）」への完全移行こそが、Gemma 3のようなモデルを制御する唯一の解です。実装修正をお願いします。