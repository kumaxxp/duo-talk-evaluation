# PHASE4_GUI_SPEC: HAKONIWA Console（NiceGUI）

- Document ID: PHASE4-GUI-SPEC
- Version: 0.9.0 (Draft)
- Target URL: http://localhost:8080
- Scope: duo-talk-evaluation 内で稼働する統合管理UI（Core / Director / GM を監視・操作）
- Sources: docs/strategy/STRATEGY.md, docs/architecture/ECOSYSTEM.md, gui_nicegui/main.py

## 1. 概要 (Overview)
- NiceGUIを用いて、Core（対話生成）、Director（品質判定/RAG）、GM（世界状態/アクション判定）を統合表示・操作するWeb UI「HAKONIWA Console」を提供。
- 目的:
  - 実行フロー（Thought→Check→Utterance→Check→GM Step）の可視化
  - 手動トリガーによる検証操作
  - 世界状態とアクション判定の即時可視化
- 成果物:
  - 1ページ構成のダッシュボード
  - 最小API連携（Core/Director: 同一プロセスImportアダプタ, GM: FastAPI REST）

## 2. 画面構成 (UI Layout)
- レイアウト: 3ペイン構成（左: Control Panel / 中央: Main Stage / 右: God View）
- ヘッダ: タイトル、接続状態インジケータ（Core/Director/GM）
- フッタ: ステータスログ（非同期処理の最新行）

### 2.1 Main Stage
- 立ち絵表示: やな/あゆ（プレースホルダー画像→将来差替）
- 会話ログ: ターン順にカード/吹き出し表示
  - 表示要素: Tn, Speaker, Speech, 補助: Thought（折りたたみ）
  - 監督判定: PASS/RETRYバッジ、修正差分（raw→repaired）
- 補助UI:
  - 再生コントロール: 次の発話へ/停止
  - 検索/フィルタ: RETRYのみ、GIVE_UPのみ

### 2.2 Control Panel
- セッション制御:
  - Topic/Prompt選択、Profile選択(dev/gate/full)
  - 話者選択（やな/あゆ）
- 手動トリガー:
  - Generate Thought（Phase1）
  - Generate Utterance（Phase2; Thought依存）
  - One-Step（Thought→Check→Utterance→Check→GM Step を一括）
- Director表示:
  - 判定結果リアルタイム表示（PASS/RETRY、理由のサマリ）
  - RETRYカウント、GIVE_UPフラグ
  - RAG注入有無/採用Fact数
- 実行状態:
  - スピナー/進捗、エラー通知、タイムアウト

### 2.3 God View (GM Monitor)
- World State（要約ビュー）
  - 現在地、時間、所持品、ロック状態などの主要属性
  - 変更差分（patch）をハイライト
- Action Log
  - ActionJudge結果（normalized action, judge結果, 修復/却下理由）
  - 直近N件のログ
- 操作:
  - Step実行（最新発話でGMへ/step）
  - 巻き戻し/やり直し（将来拡張）

## 3. 連携アーキテクチャ
### 3.1 接続方針
- Core/Director: 同一プロセスImport（Evaluation内アダプタ経由）で低レイテンシ・デバッグ容易
- GM: FastAPI (http://localhost:8001) にRESTアクセス（POST /step, GET /health）

```text
UI(NiceGUI) ──import── Core/Director (同一プロセス)
      │
      └─HTTP── GM(FastAPI:8001)
```

### 3.2 インターフェース（抽象）
- CoreAdapter（python import）
  - generate_thought(req) -> ThoughtResponse
  - generate_utterance(req) -> UtteranceResponse
- DirectorAdapter（python import）
  - check(stage, content, context) -> {status: PASS|RETRY, reasons[], repaired?, injected_facts[]}
- GMClient（HTTP）
  - POST /step (GMStepRequest) -> GMResponse
  - GET /health -> {status:"ok"}

### 3.3 データモデル（最小）
- ThoughtRequest: {session_id, speaker, topic, context}
- ThoughtResponse: {thought, tokens, latency_ms}
- UtteranceRequest: {session_id, speaker, thought, context}
- UtteranceResponse: {speech, tokens, latency_ms}
- DirectorCheckRequest: {stage:"thought"|"speech", content, context}
- DirectorCheckResponse: {status, reasons, injected_facts?, repaired_output?}
- GMStepRequest: {utterance, speaker, world_state?}
- GMResponse: {actions, world_patch, logs}

### 3.4 シーケンス
```text
1) UI: Generate Thought
2) Director: check(thought) → PASSなら3, RETRYなら再生成or修復
3) Core: Generate Utterance(thought’)
4) Director: check(speech) → PASSなら5, RETRYなら再生成or修復
5) GM: /step に utterance を送信 → world_patch / action log を取得
6) UI更新: Main Stageに発話、God Viewにworld更新・actionログ
```

### 3.5 非同期方針
- すべてasync/awaitで実装
- 長時間処理はasyncio.create_taskでバックグラウンド化
- UI更新はAppStateに集約しbind
- タイムアウト: Core/Director各3〜10s, GM 3s 推奨（例: $\\le 10\\text{s}$）
- リトライ: Director指示に従い $N=2$ 回まで再試行

## 4. 実装ステップ
### Step 1: レイアウトの枠組み作成
- 3ペイン構成の雛形を追加（既存 gui_nicegui/main.py の構造・AppStateを再利用）
- AppStateに会話ログ、判定結果、世界状態のストアを追加
- 接続状態インジケータ（Core/DirectorはダミーOK、GMは/healthで実測）

### Step 2: Core APIとの接続（会話表示）
- CoreAdapterを実装（既存Two-Phase生成を薄くラップ）
- Thought→Utteranceを最低限通す
- Main Stageに発話ログを表示、Thoughtは折りたたみ

### Step 3: Director/GM情報の表示
- DirectorAdapterを実装し、PASS/RETRYをバッジ表示
- RETRY時の修復差分（raw→repaired）をインライン表示
- GM /step を呼び、world_patchをGod Viewへ反映、Action Log表示

### Step 4: インタラクティブ操作の実装
- 手動トリガー（Thought / Utterance / One-Step）を接続
- エラー処理（通知、再試行、打切り）
- 設定（Profile, 話者, RAG on/off）のUI反映

## 5. 参考・整合
- STRATEGY.md: Phase 4優先項目「NiceGUI Dashboard」「Integration Test Suite」に整合
- ECOSYSTEM.md: GMをPort 8001でREST、Core/DirectorはImport経路で整合
- 既存GUI（gui_nicegui/main.py）:
  - 再利用: AppState、非同期実行、結果パネル、Visual Boardコンポーネント
  - 追加: Main Stage/Control Panel/God Viewの3ペイン、Director/GM直結フロー

## 6. 疑似コード（最小フロー）
```python
async def one_step(session, speaker, topic):
    thought = await core.generate_thought(session, speaker, topic)
    c1 = await director.check("thought", thought, ctx=session.ctx)
    if c1["status"] == "RETRY":
        thought = c1.get("repaired_output") or await core.generate_thought(session, speaker, topic)

    speech = await core.generate_utterance(session, speaker, thought)
    c2 = await director.check("speech", speech, ctx=session.ctx)
    if c2["status"] == "RETRY":
        speech = c2.get("repaired_output") or await core.generate_utterance(session, speaker, thought)

    gm_res = await gm.post_step({"utterance": speech, "speaker": speaker})
    session.apply_world_patch(gm_res["world_patch"])
    ui_log.append({"speaker": speaker, "thought": thought, "speech": speech, "judge": c2["status"]})
```

## 7. 画面イベントと状態
- State:
  - session_id, speaker, profile
  - dialogue_log: [{turn, speaker, thought?, speech, pass_retry, diffs}]
  - director_status: last_result, retry_count
  - world_state_summary, action_logs
- Events:
  - on_click: generate_thought, generate_utterance, one_step
  - after_speech: gm_step → world更新
  - error: notify + 状態復旧

## 8. 非機能要件
- 応答時間: 1ステップ $\\le 10\\text{s}$（LLM依存）
- 信頼性: 失敗時は明示通知、再実行可能
- 視認性: 主要情報は1画面で完結、判定/差分は色付きバッジ

## 9. 起動
```bash
make gui
# → http://localhost:8080
```
- GMは別ターミナルで起動（uvicorn ... --port 8001）

## 10. 今後の拡張（Out of Scope）
- ストリーミング表示（Chunking）
- セッション永続化/ロード
- シナリオエディタ統合