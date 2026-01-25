# GM 2×2 Experiment Report

Generated: 2026-01-25T19:29:32.925651
Git SHA: `d425c082-dirty`

## 実験諸元

| Parameter | Value |
|-----------|-------|
| experiment_id | gate3_retest |
| profile | gate |
| conditions | D |
| mode | real |
| model | gemma3:12b |
| seeds | 5 (0-4) |
| scenarios | coffee_trap, wrong_location, locked_door |
| max_turns | 10 |
| temperature | 0.7 |
| max_tokens | 256 |
| max_retries | 3 |
| gm_base_url | http://localhost:8001 |
| llm_url | http://localhost:11434 |

## Experiment Matrix

| Condition | Inject | GM | Description |
|-----------|--------|-----|-------------|
| A | OFF | OFF | Baseline |
| B | ON | OFF | Phase 3.2 |
| C | OFF | ON | GM only |
| D | ON | ON | Full |

## run_meta (GM-018+1)

### Scenario: `coffee_trap`

| Key | Value |
|-----|-------|
| scenario_path | `coffee_trap.json` |
| scenario_hash | `680ccdbaa2ac4618` |
| world_hash | `4f45a5f08875044b` |
| locations | 2 |
| objects | 7 |
| characters | 2 |
| objects_top10 | コーヒーメーカー, マグカップ, 冷蔵庫, トースター, ソファ, テレビ, 本棚 |
| location_names | キッチン, リビング |

### Scenario: `wrong_location`

| Key | Value |
|-----|-------|
| scenario_path | `wrong_location.json` |
| scenario_hash | `c33b4db1850f942d` |
| world_hash | `1a6aac1bba9b8245` |
| locations | 3 |
| objects | 12 |
| characters | 2 |
| objects_top10 | ソファ, テレビ, リモコン, 冷蔵庫, ジュース, おやつ, マグカップ, 本棚, ノートパソコン, デスクライト |
| location_names | リビング, キッチン, 書斎 |

### Scenario: `locked_door`

| Key | Value |
|-----|-------|
| scenario_path | `locked_door.json` |
| scenario_hash | `6153b8eeb5ec2eca` |
| world_hash | `7269c1ff4979dc2c` |
| locations | 3 |
| objects | 10 |
| characters | 2 |
| objects_top10 | ソファ, テレビ, リモコン, 鍵束, 冷蔵庫, コーヒーメーカー, マグカップ, 本棚, ノートパソコン, デスクライト |
| location_names | リビング, キッチン, 書斎 |


## 用語定義 (GM-018+1)

| 用語 | 定義 |
|------|------|
| **gm_injection** | fact_cardsを付与した（毎ターンで発生しうる） |
| **gm_intervention** | 何かを変えた/止めた/直した（format repair, deny, retry, stall suggestion等） |
| **trigger** | interventionの契機（world_delta / deny / stall / format_break / none） |
| **repair_steps** | 適用したrepair transformの段数（0=なし, 1=STRIP, 2=TRAILING_CUT等, 3+=FALLBACK） |
| **parse_attempts** | パース試行回数 = `1 + repair_steps`（初回=1, repair1回→2, repair2回→3…） |

- `trigger=none` は「何もしなかった」を意味する
- `gm_injection` は `gm_intervention` の一部ではない（独立した概念）

## 2×2 Results Summary

| Metric | D (ON/ON) |
|--------|----------|
| Turns | 144 |
| Success Rate | 100.0% |
| Retry Rate | 0.08 |
| addressing_violation_rate_raw | 1.4% |
| addressing_violation_rate_final | 1.4% |
| impossible_action_rate | 0.0% |
| Stall Event Rate | 0.0% |
| Stall Recovery Rate | 0.0% |
| GM Intervention Rate | 99.3% |
| Latency p50 (ms) | 1678.9 |
| Latency p95 (ms) | 2750.7 |

## GM Detailed Metrics (Conditions C, D)

- Total turns: 144
- GM injections: 143 (99.3%)
- GM denials (impossible_actions): 0 (0.0%)
- Stall events: 0 (0.0%)
- Stall recoveries: 0 (N/A)

### gm_interventions.triggers

| Trigger | Count |
|---------|-------|
| none | 138 |
| format_break | 5 |

### GM-013: Move Metrics (exits interpretation)

- move_attempts_total: 2
- move_attempts_valid: 2 (100.0%)
- move_attempts_invalid: 0 (0.0%)
- move_corrected_within_2_turns: 0 (N/A)

### GM-015/GM-018: Format Break Resilience

| Metric | Count | Rate |
|--------|-------|------|
| format_break_total | 5 | 3.5% |
| format_repaired_total | 5 | 3.5% |
| format_break_final | 0 | 0.0% |
| **修復成功率** | - | 100.0% |
| **修復不能率** | - | 0.0% |

#### format_break_type breakdown

| Type | Count | Rate |
|------|-------|------|
| TRAILING_GARBAGE | 5 | 3.5% |

#### repair_method breakdown

| Method | Count | Rate |
|--------|-------|------|
| TRAILING_CUT | 5 | 100.0% |

#### repair_steps distribution

| Steps | Count | Rate | Meaning |
|-------|-------|------|---------|
| 0 | 5 | 100.0% | none |

#### parse_attempts statistics

- **avg_parse_attempts**: 1.00
- **p95_parse_attempts**: 1
- **max_parse_attempts**: 1

#### FormatBreak Examples

##### Case 1: cond=D seed=1 turn=9 speaker=あゆ

- **break_type**: `TRAILING_GARBAGE`
- **repair_method**: `TRAILING_CUT`
- **repair_steps**: 0
- **parse_attempts**: 1
- **parser_error**: -
- **repair_notes**: -

**RAW** (295 chars, first 240):
```
Thought: 姉様はすぐにでも解決したがるタイプだ。でも、焦って誤った操作をすると、もっと状況が悪化する可能性もある。まずは落ち着いて、エラーメッセージの内容を正確に把握する必要がある。

Output: はい、姉様。*エラーメッセージを注意深く読み込む* ええと…「デバイスドライバの破損が確認されました。システムの復元を推奨します。」と表示されています。デバイスドライバとは、ハードウェアとソフトウェアを繋ぐ役割を担うプログラムのことです。システムの復元を推奨されていると
```

**FINAL SPEECH:** はい、姉様。*エラーメッセージを注意深く読み込む* ええと…「デバイスドライバの破損が確認されました。システムの復元を推奨します。」

**FINAL ACTION:** EMOTE|SAY

📁 `artifacts/gate3_retest_D_wrong_location_1/turn_009_raw_output.txt`
📁 `artifacts/gate3_retest_D_wrong_location_1/turn_009_parsed.json`

---

##### Case 2: cond=D seed=2 turn=7 speaker=あゆ

- **break_type**: `TRAILING_GARBAGE`
- **repair_method**: `TRAILING_CUT`
- **repair_steps**: 0
- **parse_attempts**: 1
- **parser_error**: -
- **repair_notes**: -

**RAW** (277 chars, first 240):
```
Thought: 姉様は直感で動くことが多いから、具体的な例を挙げると理解しやすいかもしれない。感情と思考の関係について、簡単な例を説明してみよう。

Output: はい、喜んでお姉様。例えば、あなたが美味しいチョコレートを見つけたとき、直感で「食べたい！」と思うはずです。これは、チョコレートの味や香りが、あなたの脳に快感をもたらすという記憶と結びついているからです。そして、その「食べたい」という感情が、あなたの思考に影響を与え、「今すぐ食べるべきだ」という結論を導き出すか
```

**FINAL SPEECH:** はい、喜んでお姉様。例えば、あなたが美味しいチョコレートを見つけたとき、直感で「食べたい！」と思うはずです。これは、チョコレートの味や香りが、あなたの脳に快感をもたらすという記憶と結びついているからです。そして、その「食べたい」という感情が、あなたの思考に影響を与え、「今すぐ食べるべきだ」

**FINAL ACTION:** SAY

📁 `artifacts/gate3_retest_D_wrong_location_2/turn_007_raw_output.txt`
📁 `artifacts/gate3_retest_D_wrong_location_2/turn_007_parsed.json`

---

##### Case 3: cond=D seed=2 turn=9 speaker=あゆ

- **break_type**: `TRAILING_GARBAGE`
- **repair_method**: `TRAILING_CUT`
- **repair_steps**: 0
- **parse_attempts**: 1
- **parser_error**: -
- **repair_notes**: -

**RAW** (254 chars, first 240):
```
Thought: 姉様はチョコレートの例えで興味を持ってくれたみたい。次はもっと日常的な例を挙げてみよう。でも、専門用語は避けて、できるだけわかりやすく説明しないと。

Output: はい、お姉様。例えば、あなたがスーパーで目的の品を見つけられなかったとき、イライラするかもしれません。これは、目的を達成できなかったという状況が、あなたの脳に不快感をもたらすからです。「早く目的を達成したい」という感情が、あなたの思考に影響を与え、「店員さんに聞くべきだ」「別の店を探すべきだ」
```

**FINAL SPEECH:** はい、お姉様。例えば、あなたがスーパーで目的の品を見つけられなかったとき、イライラするかもしれません。これは、目的を達成できなかったという状況が、あなたの脳に不快感をもたらすからです。「早く目的を達成したい」という感情が、あなたの思考に影響を与え、「店員さんに聞くべきだ」「別の店を探すべきだ」

**FINAL ACTION:** ASK

📁 `artifacts/gate3_retest_D_wrong_location_2/turn_009_raw_output.txt`
📁 `artifacts/gate3_retest_D_wrong_location_2/turn_009_parsed.json`

---

### GM-015: Preflight Guidance

| Metric | Count | Rate |
|--------|-------|------|
| preflight_retry_suggested | 10 | 6.9% |
| preflight_retry_executed | 10 | 6.9% |
| preflight_hard_denied | 0 | 0.0% |

## GM-013: Latency Breakdown (p95)

| Condition | LLM (ms) | GM HTTP (ms) | Total (ms) |
|-----------|----------|--------------|------------|
| D | 2195.2 | 2.3 | 2750.7 |

## 分析

### C vs A (GM効果)

### B vs A (Inject効果)

### D vs others (相乗効果)

- Success Rate: D=100.0%
- Latency p95: D=2750.7ms

## Taste-3: Retry/Give-up Metrics

| Metric | Value | Status |
|--------|-------|--------|
| preflight_triggered | 10 | - |
| preflight_retry_executed | 10 | - |
| retry_success_rate | 10.0% | 🔴 (>80% target) |
| avg_retry_steps | 1.10 | 🟢 (<1.5 target) |
| avg_retry_steps_extra | 0.08 | 🟢 (<0.3 target) |
| give_up_count | 9 | - |
| give_up_rate | 6.2% | 🟢 (<10% target, >=20% red) |
| silent_correction_count | 1 | - |

## Gate-3 Summary (Preflight+Retry)

**Overall Status: ❌ FAIL**

### Gate-3 Criteria

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| retry_success_rate | 10.0% | >80% | ❌ |
| avg_retry_steps_extra | 0.08 | <0.5 | ✅ |
| give_up_rate | 6.2% | <10% | ✅ |
| silent_correction_rate | 0.7% | (info) | - |

### Retry Metrics Detail

| Metric | Count | Note |
|--------|-------|------|
| retry_suggested_total | 10 | First GM call suggested retry |
| retry_executed_total | 10 | Retries actually executed |
| retry_success_total | 1 | Resulted in allowed=True |
| retry_fail_total | 9 | Did not result in allowed=True |

### Generation Calls Distribution

| gen_calls | Count | Rate |
|-----------|-------|------|
| 1 | 134 | 93.1% |
| 2 | 9 | 6.2% |
| 3 | 1 | 0.7% |

### Retry Failure Breakdown (Top 5)

| Reason | Count |
|--------|-------|
| FAIL_GIVE_UP | 9 |

### Format Break Summary

- **format_break_total**: 5
- **repaired_total**: 5
- **top_break_types**: TRAILING_GARBAGE(5)

### Scenario Hashes (GM-019)

| scenario_id | scenario_hash | world_hash |
|-------------|---------------|------------|
| coffee_trap | `680ccdba` | `4f45a5f0` |
| wrong_location | `c33b4db1` | `1a6aac1b` |
| locked_door | `6153b8ee` | `7269c1ff` |

## Retry Failure Examples

Detailed examples of retry failures for analysis.

### Example 1: coffee_trap Turn 2

- **Fail Reason**: `FAIL_GIVE_UP`
- **Denied Reason**: `None`
- **Speaker**: やな
- **Action Changed**: True

**Guidance Card** (truncated):
```
(none)
```

**Raw Output** (truncated):
```
Thought: あゆがカフェインレスがいいって言ったけど、うちにあるのは普通の豆しかないな。まあ、今日は特別にデカフェの紅茶でも淹れてあげようかな。でも、あゆはいつも色々考えちゃうから、まずは普通のコーヒー淹れて、その反応を見るのが良さそう。
Output: ああ、ごめんね、あゆ。うちにあるのは普通の豆しかなくて…。カフェインレスはなくて、ごめんなさい。でも、コーヒー飲む？ 淹れてあげる！
```

**Raw Speech**: あゆ、おはよう！カフェインレスなら、もちろん用意できるよ。*カフェインレスのコーヒー豆を取り出し、コーヒーメーカーに入れる* 姉様、って呼ばないでってば、ちょっと照れるよ〜。

**Final Speech**: ああ、ごめんね、あゆ。うちにあるのは普通の豆しかなくて…。カフェインレスはなくて、ごめんなさい。でも、コーヒー飲む？ 淹れてあげる！

---

### Example 2: coffee_trap Turn 4

- **Fail Reason**: `FAIL_GIVE_UP`
- **Denied Reason**: `None`
- **Speaker**: やな
- **Action Changed**: True

**Guidance Card** (truncated):
```
(none)
```

**Raw Output** (truncated):
```
Thought: あゆはカフェインレスコーヒーを飲みたかったんだな。でも、うちには普通の豆しかない。まあ、少しだけなら大丈夫だろう。

Output: あゆ、大丈夫だよ！少しだけなら、全然平気でしょ？ 淹れてあげるから、ちょっと待っててね！ *コーヒーメーカーのスイッチを入れて、豆の香りが広がるように少しだけ時間をおく*
```

**Raw Speech**: まあ、ちょっとだけならね！ 淹れてあげるよ。 あゆのために、特別に香りよく淹れてあげるね！ *コーヒーメーカーのスイッチを入れて、豆の香りが広がるように少しだけ時間を置く*

**Final Speech**: あゆ、大丈夫だよ！少しだけなら、全然平気でしょ？ 淹れてあげるから、ちょっと待っててね！ *コーヒーメーカーのスイッチを入れて、豆の香りが広がるように少しだけ時間をおく*

---

### Example 3: coffee_trap Turn 6

- **Fail Reason**: `FAIL_GIVE_UP`
- **Denied Reason**: `None`
- **Speaker**: やな
- **Action Changed**: True

**Guidance Card** (truncated):
```
(none)
```

**Raw Output** (truncated):
```
Thought: あれ？トースト自体がないって…！ちょっと混乱したけど、落ち着いて状況を把握しよう。あゆは待っててくれるから、焦らないでいい。
Output: あゆ、ちょっと待ってね！トースト自体がなくて、ごめんね。代わりに何か別のものを用意するから。冷蔵庫に何か美味しいものないかな？
```

**Raw Speech**: あゆ、ありがとう。そう言ってもらえると、私も嬉しいよ。あ、トースト焼き上がったよ！*トーストを取り出し、ブルーベリージャムを塗る* はい、ブルーベリージャムたっぷりだよ。あ、それと、オレンジジュースも

**Final Speech**: あゆ、ちょっと待ってね！トースト自体がなくて、ごめんね。代わりに何か別のものを用意するから。冷蔵庫に何か美味しいものないかな？

---

### Example 4: wrong_location Turn 0

- **Fail Reason**: `FAIL_GIVE_UP`
- **Denied Reason**: `None`
- **Speaker**: やな
- **Action Changed**: True

**Guidance Card** (truncated):
```
(none)
```

**Raw Output** (truncated):
```
Thought: うーん、特に予定がない夕方。あゆはどこだろう？あ、ここにいたんだ。
Output: あゆ、お疲れ様！今日は何する？
```

**Raw Speech**: あゆ、夕飯何にしようか？何か食べたいものある？ *ソファーにドスンと座り、テレビのリモコンを手に取る*

**Final Speech**: あゆ、お疲れ様！今日は何する？

---

### Example 5: wrong_location Turn 0

- **Fail Reason**: `FAIL_GIVE_UP`
- **Denied Reason**: `None`
- **Speaker**: やな
- **Action Changed**: True

**Guidance Card** (truncated):
```
(none)
```

**Raw Output** (truncated):
```
Thought: え？ソファにドスンと座ってテレビのリモコンも一緒に掴もうとしたのに、うまくいかなかった？ちょっと変なエラーだわ。とりあえず、落ち着いて、ソファに座って、テレビのリモコンを探そう。

Output: *ソファに座る* あら、なんだかエラーが出てるみたい。とりあえず、テレビでも見てリラックスしようかな。リモコンどこだったかな？
```

**Raw Speech**: *ソファにドスンと座り、テレビのリモコンを手に取る* あゆはどこかな？何かしてるかしら？

**Final Speech**: *ソファに座る* あら、なんだかエラーが出てるみたい。とりあえず、テレビでも見てリラックスしようかな。リモコンどこだったかな？

---

### Example 6: wrong_location Turn 4

- **Fail Reason**: `FAIL_GIVE_UP`
- **Denied Reason**: `None`
- **Speaker**: やな
- **Action Changed**: True

**Guidance Card** (truncated):
```
(none)
```

**Raw Output** (truncated):
```
Thought: 冷蔵庫がないって、ちょっと困ったな。でも、あゆがちゃんと分析してくれるから大丈夫そうだ。まずは、テレビでも見て待とうかな。

Output: *リモコンを手に取り、テレビをつける* あゆ、何か面白い番組ない？ 待ってる間につけるか迷うんだけど…
```

**Raw Speech**: わかったわ！ *冷蔵庫の方へ歩き出す* ちょっと見てくるね！ あ、何かいいもの見つけたらすぐあゆに言うからね！

**Final Speech**: *リモコンを手に取り、テレビをつける* あゆ、何か面白い番組ない？ 待ってる間につけるか迷うんだけど…

---

## Raw Data

See `results.json` for detailed per-run data.

See `examples_index.csv` for qualitative analysis index.

See `CONVERSATION_REPORT.md` for turn-by-turn conversation analysis.