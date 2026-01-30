# Step7 実装指示（Claude Code 宛） — 出荷準備・UX磨き（Release & Polish）

目的:
- Phase4 の完成を受け、配布・受け入れ準備を整える。UX磨き、ドキュメント最終化、デモ準備、リリースパッケージ作成を行う。

優先タスク（必須）
1. UX/表示改善（低コストで優先度高）
   - Main Stage の吹き出し見やすさ調整、Thought 折りたたみのデフォルト、色とバッジのコントラスト確認
   - モバイル/小窓でのレイアウト崩れ確認

2. アクセシビリティ・国際化
   - 日本語表示の全体確認（長文の折返し等）
   - キーボード操作で主要コントロールを操作可能に（tab順）

3. ドキュメント最終化
   - docs/specs/PHASE4_GUI_IMPL_NOTES.md を完成（起動手順、依存、FAQ）
   - Release Notes（docs/specs/PHASE4_RELEASE_NOTES.md）を作成

4. デモ/受入手順
   - Demo Script を作成（短い手順書: 5分デモ）
   - スクリーンショット数枚を docs/assets に保存（Main Stage/Control Panel/God View の要点）

5. リリースパッケージ
   - make target `make release-gui` を追加（requirements export + zip 作成）
   - 起動スクリプト（run_gui.sh）を作成

6. テスト & QA
   - 既存の integration テストを再実行し、ステータスを docs/specs/STEP7_COMPLETION_REPORT.md に記載
   - 手動UATチェックリストを作成（項目: 起動/One‑Step/Director/GMログ/通知/エラー表現）

7. リリース手順
   - コミットタグ付け: `v0.1.0-phase4`
   - 簡易リリースノートの作成と配布先（Slack/メール）テンプレを作成

完了報告（docs/specs/STEP7_COMPLETION_REPORT.md）
- ステップ番号: Step7
- 編集ファイル一覧
- 実行コマンド（release/test）
- 起動ログ抜粋
- デモ手順とスクショパス
- 未解決事項

運用ルール
- PR禁止。コミット可（推奨メッセージ: \"Phase4: Step7 completed\"）
- 実施後、Cline に短報（編集ファイル・デモ手順・主要スクリーンショットのパス）を提出すること。

短い送信用テンプレート（Claude 実装者向け）
- 「Step7 実行開始。UX磨き、ドキュメント最終化、デモ準備、リリースパッケージ作成を実施し、docs/specs/STEP7_COMPLETION_REPORT.md を提出せよ。」