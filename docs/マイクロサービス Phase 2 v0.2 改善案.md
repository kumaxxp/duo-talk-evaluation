# duo-talk Phase 2 v0.2 Improvement Spec

**Version:** 2.0.2 (Prevention & Context)
**Date:** 2026-01-23
**Target:** Reduce "Ane-sama" generation rate via prompt hardening, and implement ContextChecker.

---

## 1. 現状分析と方針転換

`REPORT.md` の結果により、ToneCheckerのバグ修正だけでレイテンシ問題（無駄なリトライ）はほぼ解決しました。
しかし、**「やなが自分やあゆを『姉様』と呼ぶ」エラーが依然として多発（90%のリジェクト理由）** しており、これがリトライの主因となっています。

検知ロジックは機能しているため、対策は「検知後の処理」ではなく、**「そもそも間違えさせない（発生率を下げる）」** 方向へシフトします。

| 課題 | 旧方針 | **新方針 (v0.2)** |
| :--- | :--- | :--- |
| **無駄なリトライ** | 口調判定の緩和 | **解決済み**（バグ修正により不要に） |
| **呼称ミス多発** | 自動補正 / 新規Checker | **プロンプト強化（発生源対策）** + 既存禁止ワード運用の継続 |
| **文脈不整合** | ContextChecker | **ContextChecker実装**（毒舌ハルシネーション対策） |

---

## 2. 実装詳細

### A. Prompt Hardening (呼称ミスの発生源対策)

LLM（Gemma 3）がキャラクターの役割（姉/妹）を取り違えないよう、System PromptおよびFew-shotを物理的に強化します。
特に `negative_prompt` 的な指示をJSONスキーマ内に明記します。

**変更点 (duo-talk-core/prompts):**

```json
"conversation_rule": {
  "role_definition": {
    "yana": "ELDER SISTER (姉). Calls Ayu 'Ayu' or 'Ayu-chan'. NEVER uses 'Ane-sama' (Reserved for Ayu).",
    "ayu": "YOUNGER SISTER (妹). Calls Yana 'Ane-sama'.",
    "strict_prohibition": "User 'Yana' must NOT output '姉様' in dialogue."
  }
}

```

**Few-shotの強化**:
Few-shotの会話例の中に、あえて「呼び方」を強調するようなターンを含めるか、Thought内で呼称を確認する動作を含めます。

### B. ContextChecker (文脈不整合の検知)

`MICROSERVICE_PROGRESS_REPORT.md` で指摘されていた「毒舌じゃないのに『毒舌だね』と反応する問題」に対処するため、新規チェッカーを実装します。

* **目的**: 幻覚（Hallucination）による会話の噛み合わなさを防ぐ。
* **ロジック**:
1. Trigger: 現在の話者（やな）が「毒舌」「厳しい」「辛辣」などの単語を使用した。
2. Verification: 直前の相手（あゆ）の発言履歴を検索し、ネガティブワード（「無駄」「ダメ」「コスト」等）が含まれているか判定。
3. Action: 含まれていなければ **RETRY** させる。エラーメッセージには「直前の発言は毒舌ではありません。文脈に沿った反応をしてください」と明記。



```python
# duo_talk_director/checkers/context_checker.py

class ContextChecker:
    def check(self, current_text: str, history: list[dict]) -> CheckResult:
        # やなが「毒舌」反応をしたか
        if "毒舌" in current_text or "厳しい" in current_text:
            last_ayu_msg = history[-1]["content"] if history else ""
            
            # あゆの発言に毒舌要素があるか（簡易キーワードマッチ）
            toxic_keywords = ["無駄", "コスト", "ダメ", "無理", "非効率", "リスク"]
            is_toxic = any(k in last_ayu_msg for k in toxic_keywords)
            
            if not is_toxic:
                return CheckResult(
                    status="RETRY",
                    reason="Context Error: Reacting to non-existent toxicity."
                )
        
        return CheckResult(status="PASS", score=1.0)

```

### C. Error Feedback Optimization (リトライ精度の向上)

Directorがリトライを要求する際、LLMに送り返すエラーメッセージ（Feedback）を具体化します。
現在は単に「禁止ワードが含まれています」となっている可能性があります。

* **変更**:
* NG: `Forbidden word used.`
* OK: `System Alert: You are playing "Yana" (Elder Sister). You used the forbidden word "姉様". "Ane-sama" is valid ONLY for Ayu. Please rephrase using "Ayu" or "Ayu-chan".`



---

## 3. パラメータ設定

バグ修正により実行時間が短縮されたため、リトライ回数は減らさずに品質を担保します。

| パラメータ | 設定値 | 理由 |
| --- | --- | --- |
| `max_retries` | **3** (維持) | 呼称ミスは致命的なので、直るまで粘る（現状平均1.67回なので余裕あり）。 |
| `tone_threshold` | **Strict** (維持) | バグ修正により、正規の口調判定は正しく機能しているため緩和不要。 |

---

## 4. 開発タスクリスト

1. **[Core] プロンプト定義の更新**: JSONスキーマに呼称の禁止ルール（Negative Constraint）を強く追記。
2. **[Director] ContextCheckerの実装**: 毒舌反応の整合性チェックロジック追加。
3. **[Director] リトライメッセージの改善**: 禁止ワード検出時、どのキャラが何を言うべきかを具体的に指示するよう修正。

