Step4 実装完了の報告を受領しました。次の指示は以下です。Claude は各項目を実行し、結果を所定レポートにまとめて提出してください。

1) 完了報告の最終提出  
- ファイル: docs/specs/STEP4_COMPLETION_REPORT.md（未作成なら作成）  
- 内容: 編集ファイル一覧、実行コマンド、起動ログ抜粋、UI表示サンプル（Main Stage と God View の主要テキスト）、未解決事項

2) 動作確認（ローカル E2E）  
- 起動: make gui または python -m gui_nicegui.main  
- 操作: Control Panel → Speaker選択 → One‑Step 実行  
- 収集物: 起動ログの主要行（2〜5行）、One‑Step 実行で追加された最初のターンのカードテキスト、God View の world_state 要約

3) テスト実行（必要に応じて）  
- コマンド例: pytest -q tests/test_gui_components.py  
- 成果: 失敗があれば要因と暫定対応を報告

4) ドキュメント更新  
- docs/specs/PHASE4_GUI_IMPL_NOTES.md に実装差分と起動手順を短く記載

5) 提出と待機  
- 完了報告を上記ファイルに書き込んだら Cline に通知すること。Cline が最終検証し「Definition of Done」を判定する。

優先度: 1→2→3→4 の順。報告は短く要点のみ（ファイルパスと抜粋テキスト）。