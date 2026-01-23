# PROPOSAL B: Two-Pass Architecture Plan

**Version:** 1.0
**Target:** Architecturally guarantee "Thought" & "Output" separation.
**Cost:** High (Code modification required)

---

## 1. 概要と仮説

### 現状の問題
1回のLLM呼び出し（One-Pass）の中で「思考」と「発話」の両方を行わせようとしているため、コンテキスト長不足、Stop Sequenceの誤爆、モデルのフォーマット学習不足による事故が防げない。

### 仮説
**生成プロセスを「思考フェーズ（Thinker）」と「発話フェーズ（Speaker）」に物理的に分割することで、モデルの性能に依存せず、システム的にフォーマット遵守率100%を保証する。**

---

## 2. アーキテクチャ変更仕様

`DialogueManager` の生成フローを以下のように変更する。

### Step 1: The Thinker (思考生成)
* **Input**: ユーザーの発言 + キャラクター設定
* **System Prompt**: 「あなたは{name}です。返答はせず、内面の思考のみを出力してください。」
* **Output**: 純粋な思考テキスト（例：「姉様がまた無茶を言っている…」）
* **検証**: 出力が空ならシステム側でデフォルト思考「（特に懸念はない）」を注入。

### Step 2: The Speaker (発話生成)
* **Input**: ユーザーの発言 + **Step 1で生成した思考**
* **System Prompt**: 「思考『{thought}』に基づき、相手への返答（セリフ）のみを出力してください。思考は出力しないでください。」
* **Output**: 純粋なセリフ（例：「姉様、正気ですか？」）

---

## 3. 実装イメージ (Python)

```python
def generate_two_pass(self, prompt, character):
    # Pass 1: Thought
    thought_msgs = [
        {"role": "system", "content": f"Analyze as {character.name}. Output ONLY inner thought."},
        {"role": "user", "content": prompt}
    ]
    thought = self.llm.generate(thought_msgs, stop=None) # Stop sequence不要
    
    if not thought.strip():
        thought = "(No specific thought)"

    # Pass 2: Output
    output_msgs = [
        {"role": "system", "content": f"Roleplay as {character.name}. Based on thought: {thought}. Output ONLY dialogue."},
        {"role": "user", "content": prompt}
    ]
    output = self.llm.generate(output_msgs)

    return f"Thought: {thought}\nOutput: {output}"