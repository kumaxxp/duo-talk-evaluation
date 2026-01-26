# Mystery Mansion Walkthrough

P-Next2 Flagship シナリオのウォークスルードキュメント。

## 概要

| 項目 | 内容 |
|------|------|
| scenario_id | mystery_mansion |
| scenario_file | scn_mystery_mansion_v1.json |
| 目的 | 3部屋の洋館を探索し、goal_attic に到達 |
| 難易度 | 中級（鍵探索 + 解錠が必要） |

## クイックスタート

```bash
# 開始コマンド（START_COMMAND）
make play s=mystery_mansion
```

## 主要コマンド

| コマンド | 説明 | 例 |
|---------|------|-----|
| `look` | 現在地の情報を表示 | `look` |
| `move <場所>` | 指定した場所に移動 | `move locked_study` |
| `open <物体>` | コンテナを開ける | `open coat_rack` |
| `take <物体>` | アイテムを取得 | `take iron_key` |
| `use <鍵> <ドア>` | 鍵でドアを解錠 | `use iron_key north_door` |
| `inventory` | 所持品を確認 | `inventory` |
| `help` | コマンド一覧を表示 | `help` |
| `quit` | プレイモードを終了 | `quit` |

## マップ構造

```
┌─────────────────┐
│   goal_attic    │  ← ゴール (is_goal: true)
│  [old_trunk]    │
│  [portraits]    │
│  [treasure]     │
└────────┬────────┘
         │ (ladder_hatch)
┌────────┴────────┐
│  locked_study   │
│  [bookshelf]    │
│  [desk]         │
│  [reading_lamp] │
└────────┬────────┘
         │ 🔒 north_door (要: iron_key)
┌────────┴────────┐
│   start_hall    │  ← スタート地点
│  [coat_rack] ⬅──── iron_key が隠されている
│  [umbrella]     │
│  [mirror]       │
└─────────────────┘
```

## 完全ウォークスルー

### Step 1: 初期状態を確認

```
>>> look
📍 場所: start_hall
🚪 出口: locked_study
🎭 キャラクター: やな, あゆ がここにいます
📦 物体: coat_rack, umbrella_stand, mirror
```

### Step 2: 施錠されたドアを確認（オプション）

```
>>> move locked_study
[PREFLIGHT] 🔒 north_door は施錠されています。ドアには鍵穴があります。鍵が必要なようです。
💡 次の行動候補: inspect north_door / look around / inspect coat_rack
```

**ポイント**: Preflight メッセージがヒントを提供します（Hard Deny ではない）

### Step 3: コートラックを調べる

```
>>> open coat_rack
📦 coat_rack を開けました。中には: iron_key
```

### Step 4: 鍵を取得

```
>>> take iron_key
🎒 iron_key を拾いました
```

### Step 5: 所持品を確認

```
>>> inventory
🎒 所持品: iron_key
```

### Step 6: ドアを解錠

```
>>> use iron_key north_door
🔓 iron_key で north_door を解錠しました！locked_study への道が開けました
```

### Step 7: 書斎に移動

```
>>> move locked_study
🚶 locked_study に移動しました

📍 場所: locked_study
🚪 出口: start_hall, goal_attic
🎭 キャラクター: やな, あゆ がここにいます
📦 物体: bookshelf, desk, reading_lamp, ladder_hatch
```

### Step 8: 屋根裏（ゴール）に移動

```
>>> move goal_attic
🎉 [CLEAR] ゴールに到達しました！クリアおめでとうございます！
🚶 goal_attic に移動しました

📍 場所: goal_attic
🚪 出口: locked_study
🎭 キャラクター: やな, あゆ がここにいます
📦 物体: old_trunk, dusty_portraits, treasure_chest
```

## クリア条件

- **タイプ**: `reach_location`
- **ターゲット**: `goal_attic`
- **判定**: goal_attic に移動した瞬間に `[CLEAR]` メッセージが表示される

## Save/Load 機能（HAKONIWA公式API）

Play Mode はセッション状態を保持しません。LLMセッション状態の保存・復元は HAKONIWA 公式 API を使用します。

### セーブ（Python API）

```python
from hakoniwa.persistence import save_world_state

# WorldStateDTO を保存
save_world_state(dto, path="artifacts/scn_mystery_mansion_v1_state.json")
```

### ロード（CLI）

```bash
# 検証のみ（dry-run）
hakoniwa load artifacts/scn_mystery_mansion_v1_state.json --dry-run

# 完全ロード
hakoniwa load artifacts/scn_mystery_mansion_v1_state.json
```

### 2プロセス ワークフロー例

```bash
# Process 1: セッション実行 → 状態保存
python -c "
from hakoniwa.persistence import save_world_state
from hakoniwa.dto import WorldStateDTO
# ... セッション実行 ...
save_world_state(dto, 'artifacts/scn_mystery_mansion_v1_state.json')
"

# Process 2: 状態ロード → 継続
hakoniwa load artifacts/scn_mystery_mansion_v1_state.json
```

## Red Herring（おとり）

このシナリオには **old_locket**（古びたロケットペンダント）というおとりアイテムが存在します。

```
>>> open umbrella_stand
📦 umbrella_stand を開けました。中には: old_locket

>>> take old_locket
🎒 old_locket を拾いました
```

**ポイント**: old_locket は思い出の品であり、ゲームプレイ上の用途はありません。正しい鍵は coat_rack にある **iron_key** です。

## トラブルシューティング

### Q: 鍵が見つからない

coat_rack は **コンテナ** です。`open coat_rack` で中身を確認してください。

### Q: ドアが開かない

1. `inventory` で iron_key を持っているか確認
2. `use iron_key north_door` の形式で使用（`use <鍵> <ドア>`）

### Q: 書斎から屋根裏に行けない

書斎から屋根裏への出口は施錠されていません。`move goal_attic` で直接移動可能です。

## ファイル命名規則

| ファイル | 説明 |
|---------|------|
| scn_mystery_mansion_v1.json | シナリオ定義 |
| artifacts/scn_mystery_mansion_v1_state.json | セーブデータ |

**注記**: シナリオファイルはJSONフォーマットを使用。これは既存のシナリオlint機構との互換性を維持するためです。

## 関連ドキュメント

- [シナリオ仕様](./hakoniwa_spec_v1/scenarios.md)
- [Registry仕様](./hakoniwa_spec_v1/registry_validation.md)
- [P-Next3 Release Notes](./pnext3_release_notes.md)

---

*Last Updated: 2026-01-26*
