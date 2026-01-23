# Empty Thought Investigation Request

**Date**: 2026-01-23
**Issue**: LLM generates empty Thought content despite format instructions
**Priority**: Medium (functional but suboptimal)

---

## 1. Problem Statement

When generating dialogue using a two-stage format (Thought + Output), the LLM (gemma3:12b) produces empty or near-empty Thought sections approximately 14% of the time.

### Example of the Problem

**Expected**:
```
Thought: (あゆも起きてるかな？朝から張り切ってるかも。)
Output: (にこやかに) 「おはよう！あゆ、ちゃんと朝ごはん食べた？」
```

**Actual (problematic)**:
```
Thought: (
Output: (にこやかに) 「おはよう！あゆ、ちゃんと朝ごはん食べた？」
```

### Statistics from v2.2 Experiment

| Metric | Value |
|--------|-------|
| Total responses | 64 |
| Thought present | 64 (100%) |
| Thought empty | 9 (14%) |
| Thought with content | 55 (86%) |

---

## 2. Technical Context

### 2.1 Generation Flow (dialogue_manager.py)

```python
def _generate_v38_flow(self, prompt: str) -> str:
    """Two-stage generation flow"""

    # Stage 1: Generate Thought with prefill
    thought_config = GenerationConfig(
        temperature=0.7,
        max_tokens=200,
        stop_sequences=[
            "Output",
            "Output:",
            "\nOutput",
            "\n\n",
            "やな:",
            "あゆ:",
            "<|im_end|>",
            "<|im_start|>",
            "<|eot_id|>",
            "<end_of_turn>",
            "<start_of_turn>",
        ],
    )

    # Prefill "Thought:" and generate
    thought_response = self.llm_client.generate_with_prefill(
        prompt=prompt,
        prefill="Thought:",
        config=thought_config,
    )

    # Stage 2: Generate Output
    continued_content = thought_content + "\nOutput:"

    full_response = self.llm_client.generate_with_prefill(
        prompt=prompt,
        prefill=continued_content,
        config=output_config,
    )

    return full_response
```

### 2.2 Prompt Structure (prompt_engine.py)

**System Prompt Instruction**:
```
"instruction": "あなたは以下のJSONプロファイルで定義された2人のAIキャラクター『あゆ』と『やな』です。思考（Thought）と発言（Output）の2段階で応答してください。"
```

**Few-Shot Examples**:
```
User: GPUをもう一枚買おう！
Assistant:
Thought: (Yana: やった！もっとパワーアップだ！)
Output: (ガッツポーズをして) 「いいじゃんいいじゃん！あゆ、あとはよろしくね～」
```

### 2.3 Backend Configuration

| Item | Value |
|------|-------|
| LLM Backend | Ollama |
| Model | gemma3:12b |
| Temperature | 0.7 |
| Context | 8192 tokens |

---

## 3. Root Cause Analysis

### 3.1 Hypothesis 1: Stop Sequence Premature Termination

The `stop_sequences` include `"Output"`, which may trigger when the model attempts to generate "Output:" immediately after "Thought:".

**Flow**:
```
Prefill: "Thought:"
Model generates: " ("
Model tries to generate: "Output:"
Stop sequence triggers on "Output"
Result: "Thought: ("
```

### 3.2 Hypothesis 2: Model Confusion with Two-Stage Format

gemma3:12b may not reliably follow the Thought → Output pattern, especially when:
- The prompt is complex (JSON structure)
- There are few-shot examples but the model skips to Output

### 3.3 Hypothesis 3: Temperature Variance

At temperature=0.7, the model may occasionally generate minimal Thought content as a valid probability path.

---

## 4. Potential Solutions

### Solution A: Minimum Thought Length Enforcement

Add a post-generation check for minimum Thought length (e.g., 10 characters).

```python
class ThoughtChecker:
    def __init__(self, min_thought_length: int = 10, strict_mode: bool = True):
        self.min_thought_length = min_thought_length

    def check(self, response: str) -> CheckResult:
        thought_content = self._extract_thought(response)
        if len(thought_content.strip()) < self.min_thought_length:
            return CheckResult(status=RETRY, reason="Thought too short")
```

**Pros**: Simple, catches problem early
**Cons**: Increases retry rate

### Solution B: Modified Stop Sequences

Remove "Output" from stop sequences, rely on "\nOutput:" instead.

```python
stop_sequences=[
    "\nOutput:",  # More specific
    "\n\n",
    ...
]
```

**Pros**: Allows model to generate more before stopping
**Cons**: May generate beyond Thought section

### Solution C: Thought-Only Generation First

Generate Thought content completely, then generate Output separately.

```python
# Stage 1: Generate ONLY Thought content (no Output mention)
thought_only_prompt = prompt + "\n\nGenerate Thought ONLY:"
thought_content = generate(thought_only_prompt)

# Stage 2: Generate Output with full context
output_prompt = prompt + f"\n\nThought: {thought_content}\nOutput:"
output_content = generate(output_prompt)
```

**Pros**: Complete separation of generation stages
**Cons**: Doubles API calls, increases latency

### Solution D: Prompt Engineering

Strengthen instructions and add more explicit few-shot examples.

```
【重要】Thoughtは必ず10文字以上の内容を書いてください。
空のThoughtや「(」のみは禁止です。

例（良い）：Thought: (あゆも起きてるかな？朝から張り切ってるかも。)
例（悪い）：Thought: (
```

**Pros**: No code changes
**Cons**: May not reliably work with all models

### Solution E: Retry with Feedback

When empty Thought is detected, retry with explicit feedback.

```python
if is_empty_thought(response):
    new_prompt = prompt + "\n\n【注意】前の応答はThoughtが空でした。内面の思考を詳しく書いてください。"
    response = generate(new_prompt)
```

**Pros**: Teaches model what went wrong
**Cons**: Increases latency on failure

---

## 5. Test Data

### 5.1 Successful Thought Examples

```
Thought: (あゆも起きてるかな？朝から張り切ってるかも。)
Thought: (姉様の明るさが眩しい…でも、朝ごはんの確認はありがたい。)
Thought: (おっ、新しい話題。情報収集モードに切り替えよう。)
```

### 5.2 Empty/Problematic Thought Examples

```
Thought: (
Thought: (姉
Thought: (...)
Thought: ( )
```

### 5.3 Edge Cases

```
Thought: (yana: ...)  # Truncated speaker prefix
Thought: (。)         # Punctuation only
Thought: ()           # Empty parentheses
```

---

## 6. Evaluation Criteria

Any proposed solution should be evaluated on:

| Criteria | Target |
|----------|--------|
| Empty Thought rate | < 5% (down from 14%) |
| Average retry count | < 1.0 |
| Latency overhead | < 20% increase |
| Implementation complexity | Minimal code changes |

---

## 7. Questions for Investigation

1. **Model-Specific**: Is this a gemma3-specific issue? Would gemma3:27b or llama3.1 behave differently?

2. **Prefill Interaction**: How does Ollama's prefill implementation interact with stop sequences?

3. **Temperature**: Would lower temperature (0.5) reduce empty Thought rate?

4. **Few-Shot Count**: Would more examples (5-7 instead of 3) improve compliance?

5. **Prompt Structure**: Is the JSON-based prompt confusing the model about the two-stage format?

---

## 8. Files for Reference

| File | Purpose |
|------|---------|
| `duo-talk-core/src/duo_talk_core/dialogue_manager.py` | Generation flow |
| `duo-talk-core/src/duo_talk_core/prompt_engine.py` | Prompt construction |
| `duo-talk-director/src/duo_talk_director/checks/thought_check.py` | Thought validation |
| `duo-talk-director/src/duo_talk_director/director_minimal.py` | Director implementation |

---

## 9. Request

Please analyze this problem and recommend the most effective solution considering:

1. Root cause identification
2. Solution effectiveness
3. Implementation simplicity
4. Side effect minimization

Provide a detailed analysis with code examples if possible.

---

*Generated by duo-talk-evaluation experiment framework*
*Experiment ID: director_ab_20260123_140023*
