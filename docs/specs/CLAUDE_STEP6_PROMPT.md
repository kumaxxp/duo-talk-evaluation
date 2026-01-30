# Step6 実装指示（Claude Code 宛） — Integration Test Suite & Hardening

目的:
- Phase4 の実装（Step1〜Step5）を受け、統合テストと本番運用に耐えるハードニングを行う。安定性・パフォーマンス・監視を確立する。

対象範囲（主要）
- 統合テスト: tests/integration/ 以下の追加
- CI: scripts/ci または Makefile のテストジョブ強化
- ロギング/監視: gui_nicegui のログ出力強化、GM/Director/Core 側のヘルスチェック自動化
- 性能: タイムアウト/リトライ設定の検証・調整、重負荷での回復試験
- 回帰防止: flaky test の安定化（モック境界の明確化）

必須タスク
1. tests/integration/test_one_step_e2e.py を追加
   - 条件:
     - 起動順序: duo-talk-gm (uvicorn:8001) → （任意: duo-talk-core/duo-talk-director） → GUI
     - テスト: GUI の One‑Step をモック経由で呼び、Core→Director→GM の往復が成功することを検証
     - 検証ポイント: HTTP 200、Director status in {PASS,RETRY}, GM に /step によるログ保存

2. CIジョブ追加
   - scripts/ci/run_integration.sh（簡易スクリプトでローカルコンテナやプロセスを起動し、pytest tests/integration を実行）
   - Makefile タスク: `make test-integration` を追加

3. 安定化・監視
   - gui_nicegui 側: state.log_output に詳細タイムスタンプ付ログ、失敗時にトレースIDを出力
   - health-check エンドポイント呼び出しの自動リトライ（指数バックオフ：1s→2s→4s、最大3回）
   - テストで検出したタイムアウト閾値の調整（ONE_STEP_TIMEOUT_* の見直し）

4. 性能試験
   - 単純負荷試験スクリプト（scripts/load_test_one_step.py）を追加し、同時 N=5 の One‑Step 呼びを実行して失敗率/遅延を記録
   - 結果を reports/ に保存（CSV または簡易MD）

5. ドキュメント & レポート
   - docs/specs/STEP6_COMPLETION_REPORT.md を作成（編集ファイル一覧、テストコマンド、主要ログ抜粋、性能指標、未解決事項）
   - docs/specs/PHASE4_GUI_IMPL_NOTES.md に運用手順（再起動手順、トラブルシュート）を追記

完了条件
- tests/integration が CI 上で通過する（少なくともローカルで安定実行可能）
- `make test-integration` が実行でき、主要E2Eシナリオが成功する
- ログ/監視ポイントが整備され、タイムアウト閾値が検証済みであること

提出フォーマット（必須）
- docs/specs/STEP6_COMPLETION_REPORT.md に以下を含める:
  - ステップ番号: Step6
  - 編集ファイル一覧
  - 実行コマンド（CI/ローカル）
  - 起動ログ抜粋
  - テスト結果（pytest 出力）
  - 性能試験の主要指標
  - 未解決事項

運用ルール（厳守）
- PR作成禁止。コミットは可（推奨メッセージ: "Phase4: Step6 completed"）。
- 実施前に依存サービスの起動手順を報告すること。

短文テンプレート（Claude 実装者向け）
- 「Step6 実行開始。tests/integration を追加し、CI ジョブ make test-integration を実装して E2E を自動化する。負荷試験スクリプトと監視改善も実施。完了したら docs/specs/STEP6_COMPLETION_REPORT.md を提出せよ。」

備考:
- 実装は Claude に委任する。Cline は結果の検証と受入判定を行う。