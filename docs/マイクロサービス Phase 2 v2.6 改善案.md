# duo-talk Phase 2 v2.5 Specification: The Translator Pattern

**Version:** 2.5.0
**Target:** Gemma 3 12B (Two-Pass)
**Goal:** 思考（本音）と発話（建前/キャラ付け）の乖離を表現し、オウム返しを防ぐ。

---

## 1. アーキテクチャ概念図

「思考」と「発話」の間には、**『翻訳機（Translator）』**という壁が存在するという概念モデルです。

1.  **Step 1: The Thinker (本音)**
    * 役割: 感情的・論理的な反応を生成する。
    * 制約: 口調は気にしない。乱暴でも、箇条書きでも良い。
    * 出力: `Thought Content`
2.  **Step 2: The Translator (建前)**
    * 役割: `Thought Content` を入力とし、キャラクターの `Speech Style` に適合するように**書き換える**。
    * 制約: 思考の内容をそのまま読み上げない。意訳する。
    * 出力: `Final Dialogue`



---

## 2. Step 1: The Thinker (思考生成)

思考フェーズはv2.4から大きく変えませんが、「発話しようとするな」という指示を強めます。

* **System Prompt**:
    ```text
    あなたは「{name}」の内面意識です。
    ユーザーの入力に対して、感情的・論理的な反応（思考）を出力してください。
    
    # 禁止事項
    - 相手に話しかけないこと。
    - 丁寧語やキャラの口調を気にする必要はない。本音で書くこと。
    - 出力は思考テキストのみ。
    ```
* **User Input**: `{user_message}`

---

## 3. Step 2: The Translator (発話生成・最重要)

ここがv2.5の核です。プロンプトを「生成」から「変換」へシフトさせます。

### 3.1 System Prompt構成

```python
def _construct_translator_prompt(self, character, thought_text, user_message):
    return f"""
    あなたはプロの脚本家兼役者です。
    以下の「キャラクター設定」と「内面の思考（本音）」に基づき、
    相手に対する**最適なセリフ（建前）**を生成してください。

    # キャラクター設定
    名前: {character.name}
    口調: {character.speech_style}
    口癖: {character.mandatory_phrases}

    # 現在の状況
    相手の発言: "{user_message}"
    あなたの本音: "{thought_text}"

    # ★変換ルール（厳守）
    1. **オウム返し禁止**: 「本音」をそのまま読み上げてはいけません。
       例: 本音が「バカじゃないの」でも、セリフは「理解に苦しみます」と変換する。
    2. **口調の適用**: 必ず上記「口調」設定に従って書き換えること。
       あゆの場合 → 丁寧語だが冷徹に。
       やなの場合 → 砕けた口調で元気に。
    3. **情報の取捨選択**: 相手に伝えるべきことだけをセリフにする。心の中の悪態は隠すこと。

    # 出力形式
    (Action) 「Dialogue」
    """

```

### 3.2 Few-Shot Examples (変換例の提示)

モデルに「変換の幅」を理解させるため、Step 2専用のFew-shotを用意します。

**あゆ用（本音→丁寧毒舌）**

```json
[
  {
    "role": "user",
    "content": "状況: 相手「GPU買っちゃった！」 / 本音: 「は？金ないのに何考えてるの。マジで信じられない。返品させなきゃ」"
  },
  {
    "role": "assistant",
    "content": "*冷ややかな目で* 「姉様、今月の予算残高をご存知ですか？ 即刻返品手続きを進めてください。」"
  }
]

```

**やな用（本音→楽観ギャル）**

```json
[
  {
    "role": "user",
    "content": "状況: 相手「納期、明日だって」 / 本音: 「うわ最悪。めんどくさ。あゆに全部やらせて私は寝ようかな」"
  },
  {
    "role": "assistant",
    "content": "*あゆの肩を叩いて* 「マジで！？ まあなんとかなるっしょ！ あゆちゃん、あとは任せた～！」"
  }
]

```

---

## 4. 実装コード (Python)

`duo_talk_core` への実装イメージです。

```python
class DialogueManager:
    def _generate_two_pass_v25(self, user_input: str, character: Character):
        # --- Pass 1: Thought ---
        # 思考のみを生成させるシンプルなプロンプト
        thought_prompt = self._build_thinker_prompt(character, user_input)
        thought_response = self.llm_client.generate(thought_prompt, stop=["Output"])
        
        # クリーニング (Thought: ラベルなどがあれば除去)
        raw_thought = self._clean_thought(thought_response)

        # --- Pass 2: Translation (Speech) ---
        # 思考とキャラクター設定を注入して変換させる
        translator_prompt = self._build_translator_prompt(
            character=character, 
            thought_text=raw_thought, 
            user_message=user_input
        )
        
        # ここでは stop="User:" などで制御
        speech_response = self.llm_client.generate(translator_prompt)

        # 最終結合
        return f"Thought: {raw_thought}\nOutput: {speech_response}"

```

---

## 5. 評価ポイント

この仕様に変更した後、以下の現象が確認できれば成功です。

1. **「口調の分離」**: 思考が「だ・である」調なのに、発話が綺麗な「です・ます」調になっている（あゆの場合）。
2. **「情報の隠蔽」**: 思考で「面倒くさい」と言っているのに、発話では「忙しいので」とオブラートに包んでいる。
3. **「非冗長性」**: 思考の文章量よりも、発話の文章量が適切に短くなっている（要約・変換されている）。

---

## 6. 次のアクション

1. **Few-shotデータの作成**: Step 2専用の「本音と建前」ペアを各キャラ3つずつ作成する。
2. **プロンプト実装**: 上記 `_construct_translator_prompt` をコードに落とし込む。
3. **Gemma 3でテスト**: `two_pass_comparison` を再実行し、オウム返し率が減ったか確認する。

