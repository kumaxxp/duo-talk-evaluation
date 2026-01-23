# PROPOSAL A: Model Migration Plan

**Version:** 1.0
**Target:** Solve "Empty Thought" & "Format Error" by changing the LLM.
**Cost:** Low (No code changes required)

---

## 1. 概要と仮説

### 現状の問題
Gemma 3 12B は指示追従性が高い反面、チャットテンプレートの制約が厳しく、システム側で強制する「Thought/Output形式」や「Prefill（書き出し強制）」に対して抵抗（空出力や形式無視）を示す傾向がある。

### 仮説
**「指示に従順」かつ「柔軟なフォーマットを受け入れる」モデルに変更することで、既存のコード（v3.8/v0.4）を一切変更せずに、Thought出力率100%を達成できる。**

---

## 2. 選定モデル（RTX A5000 24GB環境）

### 候補1: Llama-3.1-8B-Instruct (Benchmark)
* **役割**: 「基準機」。システムが正しく実装されているかを確認するためのデバッグ用。
* **理由**: 世界で最も標準的なInstructモデルであり、Ollamaのテンプレートとも親和性が高い。「これで動かなければコードが悪い」と断定できる。
* **Ollamaタグ**: `llama3.1:8b`

### 候補2: Qwen2.5-14B-Instruct (Production)
* **役割**: 「本番機」。日本語性能とロールプレイ能力のバランス型。
* **理由**: A5000のVRAM（24GB）を有効活用でき、Llama 3.1よりも日本語が流暢。指示追従性もGemmaより柔軟。
* **Ollamaタグ**: `qwen2.5:14b`

---

## 3. 検証手順

1.  **モデルのプル**:
    ```bash
    ollama pull llama3.1:8b
    ollama pull qwen2.5:14b
    ```

2.  **設定変更**:
    `duo-talk-core` の設定ファイル（`config.yaml`等）で `model_name` を変更。
    * Case 1: `gemma3:12b` -> `llama3.1:8b`
    * Case 2: `gemma3:12b` -> `qwen2.5:14b`

3.  **シナリオ実行**:
    既存の `casual_greeting` シナリオをDirector有効（v0.4）で実行。

4.  **評価指標**:
    * **Thought欠落率**: 0% になるか？
    * **空Thought率**: 0% になるか？
    * **リトライ回数**: 平均 1.0回以下になるか？

---

## 4. 期待される効果

* **即効性**: コード修正なしで、設定変更のみで完了する。
* **副作用**: Llama 3.1の場合、日本語が少し「翻訳調」になる可能性がある（Qwenで解消見込み）。