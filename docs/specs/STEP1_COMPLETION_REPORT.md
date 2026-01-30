# Step1 完了報告

## ステップ番号
**Step1: レイアウトの枠組み作成**

## 編集ファイル
- `gui_nicegui/main.py`

## 実施内容

### 1. AppState への新規プロパティ追加
以下のプロパティを AppState クラスに追加:
- `dialogue_log: list[dict]` - 会話ログ（ダミーデータ3件）
- `director_status: dict` - Director の最終判定結果
- `world_state_summary: dict` - GM の世界状態サマリー
- `action_logs: list[dict]` - GM のアクションログ
- `speaker: str` - 現在の話者選択
- `topic: str` - トピック/プロンプト
- `core_connected: bool` - Core 接続状態
- `director_connected: bool` - Director 接続状態
- `gm_connected: bool` - GM 接続状態

### 2. 3ペイン構成の実装
新規コンポーネント:
- `create_control_panel()` - 左ペイン: Profile/Speaker選択、手動トリガーボタン、Director状態表示
- `create_main_stage()` - 中央ペイン: キャラクター表示、会話ログカード
- `create_god_view()` - 右ペイン: World State、Recent Changes、Action Log
- `create_hakoniwa_console()` - 3ペイン統合レイアウト
- `_create_dialogue_card()` - 個別会話カード生成
- `_refresh_main_stage()` - Main Stage 再描画

### 3. 既存機能との両立
- タブ切り替え（Console / Legacy）で新旧レイアウトを切り替え可能
- 既存の Evaluation GUI 機能は Legacy タブで維持

## 実行コマンド
```bash
make gui
# または
python -m gui_nicegui.main
```

## 起動ログ抜粋
```
NiceGUI ready to go on http://localhost:8080, http://172.17.0.1:8080, ...
```

## Main Stage サンプル表示

### 最初の会話カード（T1）
| 項目 | 内容 |
|------|------|
| Turn | T1 |
| Speaker | やな |
| Status | PASS |
| Thought | 妹と一緒に朝を迎えられて嬉しいな。今日も楽しい一日になりそう。 |
| Speech | おはよう、あゆ〜！今日もいい天気だね！ |

### 2番目の会話カード（T2）
| 項目 | 内容 |
|------|------|
| Turn | T2 |
| Speaker | あゆ |
| Status | PASS |
| Thought | 姉様は相変わらず朝から元気ね。少し眩しいけど、悪くない。 |
| Speech | おはようございます、姉様。...朝から声が大きいですよ。 |

### 3番目の会話カード（T3）- RETRY表示
| 項目 | 内容 |
|------|------|
| Turn | T3 |
| Speaker | やな |
| Status | RETRY（オレンジ枠線） |
| Thought | あゆったら、素直じゃないんだから。でもそこが可愛いよね。 |
| Speech | えへへ、ごめんね〜。でもあゆの寝癖、可愛いよ？ |
| Raw | あゆの寝癖可愛い |
| Repaired | えへへ、ごめんね〜。でもあゆの寝癖、可愛いよ？ |

## UI 確認項目

### Header
- タイトル: "HAKONIWA Console"
- 接続状態バッジ: Core(green), Director(green), GM(grey)
- サブタイトル: "Phase 4: Integration Dashboard"

### Control Panel（左ペイン）
- Profile 選択: dev / gate / full
- Speaker 選択: やな / あゆ
- Topic / Prompt 入力欄
- Manual Triggers:
  - Generate Thought（Step2で実装予定）
  - Generate Utterance（Step2で実装予定）
  - One-Step（Step4で実装予定）
- Director Status: Last Stage, Last Status, Retry Count

### Main Stage（中央ペイン）
- キャラクターアイコン: やな（ピンク）/ あゆ（紫）
- 会話ログ: 3件のダミーカード表示
- 各カードに Turn番号、Speaker、Status バッジ
- Thought は折りたたみ表示
- RETRY 時は Repair Diff 表示可能

### God View（右ペイン）
- World State: Location, Time, Characters
- Recent Changes: 直近の変更（やなが起床した、あゆが起床した）
- Action Log: 直近のアクション（T1 WAKE_UP やな、T2 WAKE_UP あゆ）

### Footer
- ステータスログ表示: "Ready"

### Legacy タブ
- 既存の Scenario Selection / Execution / Results / Demo Pack / Visual Board 機能を維持

## 未解決事項
- なし

## 次のステップ
Step2: CoreAdapter の実装（Generate Thought / Generate Utterance ボタン動作）

---
**実施日時**: 2026-01-30
**実施者**: Claude Code
