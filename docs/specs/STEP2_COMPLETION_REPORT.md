# Step2 完了報告

## ステップ番号
**Step2: CoreAdapter 実装**

## 編集ファイル
- `gui_nicegui/adapters/__init__.py` (新規作成)
- `gui_nicegui/adapters/core_adapter.py` (新規作成)
- `gui_nicegui/main.py` (変更)

## 実施内容

### 1. gui_nicegui/adapters/core_adapter.py (新規作成)
CoreAdapter モジュールを実装:

```python
# API
async def generate_thought(session_id: str, speaker: str, topic: str, timeout: float = 5.0) -> ThoughtResponse
async def generate_utterance(session_id: str, speaker: str, thought: str, timeout: float = 5.0) -> UtteranceResponse

# Response Types
ThoughtResponse = {"thought": str, "tokens": int, "latency_ms": int}
UtteranceResponse = {"speech": str, "tokens": int, "latency_ms": int}
```

実装詳細:
- モック実装（やな/あゆ用のテンプレート応答）
- `asyncio.wait_for` によるタイムアウト（デフォルト5秒）
- 例外処理（TimeoutError 伝搬）
- 実行時間計測（latency_ms）

### 2. gui_nicegui/main.py (変更)
AppState 追加プロパティ:
- `session_id: str` - セッション識別子
- `pending_thought: str` - 生成済み Thought（Utterance 生成用）
- `generating: bool` - 生成中ロック

新規ハンドラ関数:
- `_handle_generate_thought()` - Thought 生成 → dialogue_log 追加 → UI 更新
- `_handle_generate_utterance()` - Utterance 生成 → dialogue_log 更新 → UI 更新

ボタン接続:
- Generate Thought → `_handle_generate_thought`
- Generate Utterance → `_handle_generate_utterance`

ステータス追加:
- `THOUGHT` ステータスバッジ（青色アウトライン）

## 実行コマンド
```bash
make gui
# または
python -m gui_nicegui.main
```

## 起動ログ抜粋
```
NiceGUI ready to go on http://localhost:8080, ...
```

## アダプタ動作確認
```
=== Generate Thought ===
thought: テストについて...
お腹空いたなぁ。あゆと一緒に何か食べに行こうかな。
tokens: 36
latency_ms: 317

=== Generate Utterance ===
speech: ねえねえ、あゆ〜！これ見て見て！
tokens: 16
latency_ms: 318
```

## UI 表示サンプル

### Generate Thought 実行後
| 項目 | 内容 |
|------|------|
| Turn | T4 (既存3件の次) |
| Speaker | やな |
| Status | THOUGHT (青色バッジ) |
| Thought | テストについて... お腹空いたなぁ。あゆと一緒に何か食べに行こうかな。 |
| Speech | (未生成) |

### Generate Utterance 実行後
| 項目 | 内容 |
|------|------|
| Turn | T4 |
| Speaker | やな |
| Status | PASS (緑色バッジ) |
| Thought | (上記と同じ) |
| Speech | ねえねえ、あゆ〜！これ見て見て！ |

## フロー確認

1. **Generate Thought ボタン押下**
   - 選択された Speaker の Thought を生成
   - dialogue_log に新エントリ追加（status: THOUGHT）
   - Main Stage 再描画
   - Footer に "Thought generated for {speaker} ({latency}ms)" 表示
   - 通知: "Thought generated: {内容...}"

2. **Generate Utterance ボタン押下**
   - pending_thought を使用して Utterance 生成
   - dialogue_log の最新エントリを更新（speech 追加、status: PASS）
   - Main Stage 再描画
   - Footer に "Utterance generated for {speaker} ({latency}ms)" 表示
   - 通知: "Utterance: {内容...}"

3. **エラーハンドリング**
   - 生成中に再度ボタン押下 → "Generation already in progress" 警告
   - pending_thought なしで Utterance 生成 → "No pending thought" 警告
   - タイムアウト → エラー通知、状態維持

## 未解決事項
- なし

## 次のステップ
Step3: DirectorAdapter と GMClient の実装

---
**実施日時**: 2026-01-30
**実施者**: Claude Code
