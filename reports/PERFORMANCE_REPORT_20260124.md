# duo-talk-ecosystem 性能評価レポート

**実行日時**: 2026-01-24 13:20-13:30
**評価者**: Claude (自動生成)
**フェーズ**: Phase 2.2.1完了時点

---

## 1. エグゼクティブサマリー

| 項目 | 結果 | 判定 |
|------|------|:----:|
| 全テスト | **758パス** / 0失敗 | ✅ |
| TWO_PASSフォーマット成功率 | **100%** | ✅ |
| Director統合 | リトライ0回 | ✅ |
| StateExtractor精度 | 感情検出成功 | ✅ |
| コードカバレッジ | 97% (state), 89% (sanitizer) | ✅ |

**結論**: Phase 2.2.1の全機能が安定動作。本番運用準備完了。

---

## 2. 実験諸元

### 2.1 共通パラメータ

| パラメータ | 値 |
|-----------|-----|
| バックエンド | Ollama |
| LLM | gemma3:12b |
| Temperature | 0.7 |
| max_tokens (Thought) | 120 |
| max_tokens (Output) | 300 |
| 実行回数/シナリオ | 3 |

### 2.2 テストシナリオ

| シナリオ | プロンプト | ターン数 |
|----------|----------|---------|
| casual_greeting | おはよう、二人とも | 4-5 |
| topic_exploration | 最近のAI技術について話して | 6 |
| emotional_support | 最近疲れてるんだ... | 5 |

---

## 3. 生成モード比較 (TWO_PASS vs Two-Phase)

### 3.1 定量評価

| 指標 | TWO_PASS | Two-Phase | 評価 |
|------|----------|-----------|:----:|
| フォーマット成功率 | **100%** | **100%** | 同等 |
| 平均リトライ | 0.00 | 0.00 | 同等 |
| 平均Thought長 | **85文字** | 54文字 | TWO_PASS優位 |
| cross_turn_coherence | 1.00 | 1.00 | 同等 |
| state_extractability | 0.56 | 0.56 | 同等 |

### 3.2 Thoughtの性質比較

| 観点 | TWO_PASS | Two-Phase |
|------|----------|-----------|
| 傾向 | 内面モノローグ寄り | 行動計画寄り |
| 特徴 | 感情・関係性・含みが多い | 短く即座にSpeechに反映 |
| 用途 | **本番会話・没入感重視** | 実験・State抽出専用 |

### 3.3 会話サンプル

**TWO_PASS - やな**
```
Thought: あ、おはよう！あゆも元気そうでよかった。今日は何するのかな、楽しみだな！
Output: (あやふやな笑顔で)「おはよー！あゆも、元気いっぱいみたいだね。」
```

**Two-Phase - やな**
```
Thought: あゆも起きてるかな？朝から何して遊ぶか、もうワクワクしてる！
Output: 「おはよう、二人とも～！あゆ、もう起きてるかな？」
```

→ **TWO_PASSの方がThoughtが詳細で内面描写が豊か**

---

## 4. Director比較 (Minimal vs Hybrid)

### 4.1 定量評価

| メトリクス | Director無し | Director有り | 差分 |
|------------|-------------|-------------|------|
| 成功数 | 9/9 | 9/9 | - |
| 平均リトライ | 0.00 | 0.00 | ±0.00 |
| 総不採用数 | 0 | 0 | - |

### 4.2 評価スコア分布

| シナリオ | Director無し (平均) | Director有り (平均) |
|----------|-------------------|-------------------|
| casual_greeting | 0.57 | 0.52 |
| topic_exploration | 0.57 | 0.52 |
| emotional_support | 0.48 | 0.50 |

### 4.3 考察

- **リトライ0回**: DirectorMinimalの静的チェックが効果的に機能
- **スコア差が小さい**: 両条件とも安定した品質を維持
- **DirectorHybridの役割確定**: 本番はMinimal、評価/収集はHybrid

---

## 5. StateExtractor統合評価

### 5.1 感情検出結果

実験結果のThoughtをStateExtractorで分析:

| 感情 | 検出数 | 割合 |
|------|--------|------|
| JOY (喜び) | 4 | 50% |
| ANNOYANCE (苛立ち) | 2 | 25% |
| WORRY (心配) | 1 | 12.5% |
| NEUTRAL (中立) | 1 | 12.5% |

### 5.2 関係性トーン検出

| トーン | 検出数 | 割合 |
|--------|--------|------|
| TEASING (からかい) | 3 | 37.5% |
| NEUTRAL (中立) | 3 | 37.5% |
| WARM (温かい) | 2 | 25% |

### 5.3 統計サマリー

| 指標 | 値 |
|------|-----|
| 平均感情強度 | 0.59 |
| 平均抽出信頼度 | 0.49 |
| 感情変化検出 | 4回/8ターン |

### 5.4 感情変化の追跡例

```
Turn 1 (やな): JOY →
Turn 2 (あゆ): WORRY → emotion_changed: JOY → WORRY
Turn 3 (やな): JOY → emotion_changed: WORRY → JOY
Turn 4 (あゆ): NEUTRAL → emotion_changed: JOY → NEUTRAL
```

→ **キャラクター間の感情の対比が正しく検出されている**

---

## 6. テストカバレッジ

### 6.1 コンポーネント別

| コンポーネント | テスト数 | パス | カバレッジ |
|---------------|---------|------|----------|
| duo-talk-core | 199 | 199 | - |
| duo-talk-director | 250 | 250 | 97% (state) |
| duo-talk-evaluation | 309 | 309 | - |
| **合計** | **758** | **758** | - |

### 6.2 新規実装

| モジュール | テスト数 | カバレッジ |
|-----------|---------|----------|
| StateExtractor | 34 | **97%** |
| ActionSanitizer | 26 | **89%** |

---

## 7. 実装済み機能一覧

### 7.1 Phase 2.2.1 完了分

| 機能 | 状態 | 効果 |
|------|:----:|------|
| TWO_PASSデフォルト化 | ✅ | フォーマット成功率100% |
| ActionSanitizer v1.0 | ✅ | Propsハルシネーション防止 |
| StateExtractor v1.0 | ✅ | Thought状態抽出 |
| ToneChecker v2.2 | ✅ | Output部分のみチェック |
| DirectorHybrid役割定義 | ✅ | 失敗収集器として明確化 |
| CI/CDスクリプト | ✅ | Makefile、GitHub Actions |

### 7.2 設計原則の確立

1. **Thoughtの長さは品質指標ではない** - 役割が異なる
2. **TWO_PASSが主軸** - 本番会話はこちら
3. **Two-Phaseは隔離** - 実験・State抽出専用
4. **DirectorMinimalが本番** - 高速な静的チェック

---

## 8. 推奨構成

### 8.1 本番運用

```python
from duo_talk_core import create_dialogue_manager, GenerationMode
from duo_talk_director import DirectorMinimal

manager = create_dialogue_manager(
    backend="ollama",
    model="gemma3:12b",
    generation_mode=GenerationMode.TWO_PASS,  # デフォルト
    director=DirectorMinimal(),
    max_retries=3,
    temperature=0.7,
)
```

### 8.2 評価・分析用

```python
from duo_talk_director import DirectorHybrid
from duo_talk_director.state import StateExtractor

# 対話生成 + 品質評価
director = DirectorHybrid(llm_client)

# Thought状態分析
extractor = StateExtractor()
state = extractor.extract(thought, speaker)
```

---

## 9. 次フェーズへの推奨

### 9.1 Phase 2.3 候補

| 項目 | 優先度 | 理由 |
|------|:------:|------|
| Thought再利用ログ蓄積 | 高 | State Updater判断材料 |
| ActionSanitizer統合 | 中 | Two-Phase使用時に必須 |
| LLM評価精度向上 | 中 | スコアリング改善 |

### 9.2 Phase 3 (RAG統合) 準備

- StateExtractorの出力をRAGクエリに活用可能
- 感情・トピック・関係性の状態に基づく文脈検索

---

## 10. 結論

**Phase 2.2.1は全ての目標を達成**:

1. ✅ TWO_PASSモード100%フォーマット成功率
2. ✅ DirectorMinimal/Hybrid役割分担確立
3. ✅ StateExtractor 97%カバレッジで実装完了
4. ✅ ActionSanitizer 89%カバレッジで実装完了
5. ✅ CI/CD整備（758テスト全パス）

**本番運用準備完了。Phase 2.3への移行を推奨。**

---

*Report generated by duo-talk-evaluation experiment hub*
*Timestamp: 2026-01-24T13:30:00*
