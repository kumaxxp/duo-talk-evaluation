# シナリオ仕様 v1.0（World 定義）

## 0. 目的
Scenario は、HAKONIWA-G3 が使用する **決定論的な世界パッケージ**です。

- 厳密な exits グラフ（移動制約）
- 厳密な物体の存在 / 位置 / 所有
- alias による正規化（表記揺れ吸収）
- キャラクター初期状態

本ドキュメントでは、実行に必要な **最小十分セット（Minimum Viable World）** を凍結します。

---

## 1. シナリオパッケージ構造
```
scenarios/<scenario_id>/
...
```

---

## 2. scenario.yaml 必須キー（Director 決裁）
以下は **完全必須**です。欠けている場合は `SchemaValidationError` として起動させません。

```yaml
scenario_id: str
meta:
  time: str
  weather: str
locations:
  - id: str
    name: str
    description: str
    exits:
      - target: str
        description: str
objects:
  - id: str
    name: str
    aliases: List[str]     # 空リストでもキーは必須
    location: str          # locations.id または character_id
    owner: str             # public / char_id
    properties: List[str]
characters:
  - id: str
    name: str
    location_id: str
```

### 任意キー（将来拡張）
- `connections`：エッジ属性（鍵/通行不可等）。当面は exits の記述でカバー可。
- `global_objects`：床/壁/空気等。現状は GM コード側の `GLOBAL_ALLOW_LIST` で代用可。

---

## 3. 世界規模のスケーリングについて
大きいマップやリッチな持ち物へは拡張できますが、**最初からDB/RAGは不要**です。

- 世界は YAML で保持し、ID で曖昧さを排除する
- まずはツール（GUI + バリデータ）を整備し、作者（人間）の負担を下げる
- DB/RAG を検討するのは、例えば次の条件を満たす頃：
  - シナリオ数が ~200 を超える
  - アセットが巨大で検索が必要
  - シナリオ作成がボトルネック化した

v1.0 は **決定論的 YAML + スキーマ検証** を推奨ベースラインとします。

---

## 4. Scenario Registry（GM-019）

シナリオの解決と検証は Scenario Registry を通じて行います。

詳細は [registry_validation.md](./registry_validation.md) を参照してください。

### 4.1 主な機能

- **scenario_id 解決**: registry.yaml による一元管理
- **整合性検証**: exits/locations/characters の参照整合性チェック
- **ハッシュ計算**: scenario_hash / world_hash による再現性保証

