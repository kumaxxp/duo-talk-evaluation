# 箱庭システム GM Cockpit - "Visual Board" 機能仕様書

**Version:** 1.0 (Draft)
**Target:** NiceGUI Frontend Implementation
**Date:** 2026/01/27

## 1. 概要 (Overview)

箱庭内のオブジェクト（Actor, Item, Furniture）を、テキストリストではなく「3x3グリッド上のアイコン」として表示する。
物理的なXY座標計算は行わず、オブジェクトが持つ「意味的な場所（Zone）」に基づいて配置を決定し、GMによる直感的な状況把握とオブジェクト選択を可能にする。

## 2. デザイン方針 (Design Principles)

1. **No Physics:** 衝突判定、移動経路計算は一切行わない。
2. **Semantic Mapping:** 「座標」ではなく「ゾーン（北、南、中央など）」で管理する。
3. **Click to Select:** アイコンをクリックすることで、アクションパネルの操作対象（Target）を切り替える。

## 3. 画面レイアウト仕様 (UI Layout)

### 3.1. グリッド構造

画面中央の「Action Panel」の左側、または上部に配置する。
3行3列（計9セル）のグリッドを採用する。

| Grid Index | Zone Name | 役割・表示内容 |
| --- | --- | --- |
| **0 (NW)** | Wall/Corner | 壁、装飾（操作不可） |
| **1 (N)** | **North** | 奥にある家具（本棚、窓など） |
| **2 (NE)** | Wall/Corner | 壁、装飾（操作不可） |
| **3 (W)** | **West** | 左側の家具、壁際 |
| **4 (C)** | **Center** | **メインエリア**（テーブル、Actor、主要アイテム） |
| **5 (E)** | **East** | 右側の家具、壁際 |
| **6 (SW)** | Wall/Corner | 壁、装飾（操作不可） |
| **7 (S)** | **South** | 入口、ドア |
| **8 (SE)** | Wall/Corner | 壁、装飾（操作不可） |

### 3.2. セル（マス）の表現

* **背景:** 暗色（Dark Slate / Black）。
* **未配置:** 薄いドット（`·`）を表示し、空間であることを示す。
* **配置済み:** オブジェクトの「アイコン（絵文字）」を表示する。
* 複数オブジェクトが同一ゾーンにある場合：
* **案A（推奨）:** フレックスボックスで並べて表示（重なりを許容しない）。
* **案B:** 代表的な1つを表示し、クリックでリスト展開。
* *MVPでは案Aを採用。*





### 3.3. オブジェクト表現（Iconography）

オブジェクトの `type` または `name` に基づき、以下のUnicode絵文字を自動割り当てする（コード内でマッピング辞書を持つ）。

* **Actor (NPC):** 👧 (Ayu), 👱‍♀️ (Yana), 👤 (Unknown)
* **Item:** 🍎 (Food), 🗝️ (Key), 📄 (Paper), 📦 (Box)
* **Furniture:** 🪑 (Chair/Table), 🚪 (Door), 📚 (Shelf), 🛏️ (Bed)

## 4. 内部ロジック仕様 (Logic & Data Mapping)

### 4.1. ゾーン決定ロジック (Zone Resolver)

バックエンドから取得したオブジェクトリストを、UI描画時に以下のルールで各ゾーン（0〜8）に振り分ける。

1. **Explicit Zone (明示指定):**
* オブジェクトの属性に `ui_zone`（例: "north", "center"）があればそれを優先する。


2. **Name Inference (名前推論):**
* 名前に "Door", "Entrance" が含まれる → **South (7)**
* 名前に "Window", "Shelf" が含まれる → **North (1)** または **West/East (3,5)**


3. **Default Fallback (デフォルト):**
* 上記以外（Actorや拾えるアイテム）はすべて **Center (4)** に配置する。
* *理由:* TRPGにおいて、PC/NPCや主要アイテムは基本的に部屋の中央（シーンの中心）に存在すると見なすため。



### 4.2. インタラクション (Events)

* **onClick(object_id):**
* グリッド上のアイコンがクリックされた際、GM Cockpitの「Selected Object」ステートを更新する。
* 右側の「Action Panel」の内容を、選択されたオブジェクトに合わせて再描画する。


* **Tooltip:**
* マウスオーバー時に `Name (State)` を表示する（例: "Apple (On Table)"）。



## 5. 除外事項 (Out of Scope)

* **ドラッグ＆ドロップ:** アイコンをドラッグして移動させる機能は実装しない（移動コマンドの発行が必要）。
* **厳密なマップ生成:** 部屋の大きさや形状に応じたグリッドサイズの動的変更は行わない（常に3x3固定）。

