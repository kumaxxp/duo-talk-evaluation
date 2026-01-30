# Step5 実装指示（Claude Code 宛） — 魂の注入 (Real Integration)

目的:
- Mock を実サービス接続に差し替え、GUI の One‑Step 操作で実際に Core / Director / GM が連携して動く状態にする。

対象ファイル（実装先）
- src/gui_nicegui/adapters/core_adapter.py
- src/gui_nicegui/adapters/director_adapter.py
- src/gui_nicegui/clients/gm_client.py

必須要件（概要）
1. Core & Director（内部）
   - duo-talk-core の実クラス（例: prompt_engine.py の PromptEngine / two_phase_engine.py の TwoPhaseEngine）をインポートして利用する。
   - duo-talk-director の実クラス（例: DirectorHybrid, director_llm など）の check API を呼び、Director 判定を受け取る。
   - 既存の mock 実装を置換またはフォールバックで切替可能にする（ImportError や配置差異を考慮）。
   - 長時間処理が同期APIの場合は asyncio.to_thread でラップして非同期化。

2. GM（外部: HTTP）
   - httpx.AsyncClient を使用し `http://localhost:8001` に対して
     - GET /health
     - POST /step
     を非同期で呼ぶ（timeout=3s をデフォルト）。
   - レスポンスを既存 UI が期待する形式にマッピングして返す。

3. パス解決 / インポート方針
   - adapter ファイル冒頭で安全にプロジェクトルートを sys.path に追加するコードを入れる（try/except）。
   - 例:
     ```python
     import sys
     from pathlib import Path
     PROJECT_ROOT = Path(__file__).resolve().parents[2]
     if str(PROJECT_ROOT) not in sys.path:
         sys.path.insert(0, str(PROJECT_ROOT))
     ```
   - その上で `from duo_talk_core.prompt_engine import PromptEngine` 等を試行し、ImportError 発生時は mock を使う。

4. タイムアウト・再試行・エラーハンドリング
   - Core: asyncio.wait_for(..., timeout=ONE_STEP_TIMEOUT_CORE)
   - Director: asyncio.wait_for(..., timeout=ONE_STEP_TIMEOUT_DIRECTOR)
   - GM: httpx timeout=ONE_STEP_TIMEOUT_GM
   - Import/接続失敗時は UI に ui.notify で警告し、動作継続のため mock をフォールバックする。

5. 非同期化とブロッキング関数
   - ブロッキング関数（sync）の呼び出しは:
     - `await asyncio.to_thread(sync_call, args...)`
   - LLM 呼び出しで cpu-bound なら別プロセス/外部実行の考慮をコメントに残す。

6. ロギングと可観測性
   - 各アダプタは latency_ms, status を返す辞書を返す。
   - 失敗時は詳細ログ（例外トレース）をログファイルに吐き、UI には簡潔な通知。

E2E 検証手順
1. duo-talk-gm を起動: `cd duo-talk-gm && uvicorn duo_talk_gm.main:app --port 8001`
2. （必要なら core/director を起動または配置）
3. GUI を起動: `make gui` または `python -m gui_nicegui.main`
4. ブラウザ: http://localhost:8080
5. Control Panel → Speaker 選択 → One‑Step 実行
6. 成功条件:
   - Main Stage に実生成 Thought/Utterance が表示される
   - Director 判定が返る（PASS/RETRY）
   - GM の /step ログにエントリが残る（GM 側ログまたは結果ディレクトリで確認）

完了報告フォーマット（docs/specs/STEP5_COMPLETION_REPORT.md を作成）
- ステップ番号: Step5
- 編集ファイル:
  - src/gui_nicegui/adapters/core_adapter.py
  - src/gui_nicegui/adapters/director_adapter.py
  - src/gui_nicegui/clients/gm_client.py
  - gui_nicegui/main.py（変更があれば）
- 実行コマンド:
  - 起動手順(簡潔)
- 起動ログ抜粋:
  - NiceGUI 起動行、GM health 確認行、One‑Step の主要ログ数行
- UI 表示サンプル:
  - One‑Step 実行で表示された Thought/Speech のテキスト（1件）
  - Director 判定のサンプル（PASS/RETRY）
  - GM側に残ったログ/patch 要約
- 未解決事項（あれば）

実装ルール（厳守）
- PR作成禁止。コミットは可（推奨メッセージ: "Phase4: Step5 completed"）
- 実装は既存仕様（docs/specs/PHASE4_GUI_SPEC.md）に従うこと
- 事前に実環境が起動可能かを確認し、起動手順を報告すること

短い送信用テンプレート（Claude 実装者向け）
- 「Step5 実行開始。src/gui_nicegui/adapters と clients を実サービス接続へ置換する。duo-talk-core 及び duo-talk-director の import を試み、失敗時は mock へフォールバックする。GM は httpx.AsyncClient で POST /step を実装。完了したら docs/specs/STEP5_COMPLETION_REPORT.md を提出せよ。」

---

上記内容で良ければ、Claude に直接このファイルの内容を渡して実装を開始させてください。