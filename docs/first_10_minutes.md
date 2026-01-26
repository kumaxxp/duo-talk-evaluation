# 最初の10分 - duo-talk-evaluation クイックスタート

初めて触る人向けの最短パス。10分で「問題発見 → 原因特定 → 修正方針」まで到達。

## 0. 前提条件

```bash
# conda環境がアクティブであること
conda activate duo-talk
```

## 1. Demo Packを実行（2分）

```bash
# GUIを起動
make gui

# または直接実行
python -m gui_nicegui.main
```

1. ブラウザで http://localhost:8080 を開く
2. **Demo Pack** タブをクリック
3. **Run Demo Pack** ボタンをクリック
4. 完了まで待機（約1-2分）

## 2. Issues Only ビューで問題を特定（2分）

完了後、**Issues Only** タブに切り替え。

### 優先度順（上から対処）

| 優先度 | マーク | 意味 |
|--------|--------|------|
| 1 | 🔴 Crash | システムエラー |
| 2 | 🟠 Schema | スキーマ違反 |
| 3 | 🟡 FormatBreak | フォーマット不正 |
| 4 | 🔵 GiveUp | タスク諦め |
| 5 | ⚪ Retry | リトライ発生 |

最初のIssueをクリックして詳細を展開。

## 3. Guidance Cardで原因を把握（1分）

展開した詳細に `guidance_card` が表示される:

```
[ERROR_CODE] MISSING_OBJECT
[BLOCKED_TARGET] コーヒー豆
[SUGGESTED_FIX] シナリオにオブジェクトを追加
```

これが問題の原因と修正方針。

## 4. Play Modeで現場確認（3分）

```bash
# シナリオをPlay Modeで探索
make play s=coffee_trap

# 起動後のコマンド
>>> look          # 現在地確認
>>> where         # 現在地とキャラ位置
>>> map           # 全体マップ
>>> move キッチン  # 移動
>>> inventory     # 所持品確認
>>> open 引き出し  # コンテナを開ける
>>> search        # 隠しオブジェクト探索
```

「コーヒー豆がpropsにない」「引き出しの中にある」など、問題の実態を確認。

## 5. 修正を適用（2分）

### パターン別対処法

| 症状 | 原因 | 対処 |
|------|------|------|
| MISSING_OBJECT | propsにない | シナリオJSONにオブジェクト追加 |
| 移動できない | exitsにない | シナリオJSONにexit追加 |
| 隠しオブジェクト | hidden_objects | search で発見可能か確認 |
| コンテナ内 | containers | open で取得可能か確認 |

### シナリオ修正例

```bash
# シナリオファイルを編集
$EDITOR experiments/scenarios/coffee_trap.json
```

```json
{
  "locations": {
    "キッチン": {
      "props": ["コーヒーメーカー", "コーヒー豆"],  // ← 追加
      "exits": ["リビング"]
    }
  }
}
```

## 6. 検証（自動）

```bash
# シナリオ構文チェック
make lint-scenarios

# 再度Demo Packを実行して確認
make gui
```

## コマンドまとめ

| コマンド | 用途 |
|----------|------|
| `make gui` | GUI起動 |
| `make play s=<scenario>` | Play Mode起動 |
| `make lint-scenarios` | シナリオ構文チェック |
| `make ci-gate` | 全テスト実行 |

## トラブルシューティング

問題が解決しない場合:

1. [triage_playbook.md](triage_playbook.md) の詳細手順を参照
2. `docs/機能一覧.md` で利用可能な機能を確認
3. `make test` でテストが通るか確認

---

*10分で終わらなかったら、それはバグです。Issue報告してください。*
