# HAKONIWA-G3 仕様 v1.0: Scenario Registry & Validation

## 1. Scenario Registry（シナリオ登録）

### 1.1 概要
Scenario Registry は、scenario_id からファイルパスへの解決を一元管理する **Single Source of Truth** です。

### 1.2 registry.yaml 形式

```yaml
# experiments/scenarios/registry.yaml
scenarios:
  - scenario_id: default
    path: null  # built-in default scenario
    tags: [baseline, kitchen_living]
    recommended_profile: dev
    description: "Default kitchen-living morning scenario"

  - scenario_id: coffee_trap
    path: coffee_trap.json
    tags: [gate_taste3, retry, missing_object]
    recommended_profile: dev
    description: "Coffee maker exists but no beans - triggers MISSING_OBJECT"
```

### 1.3 解決ルール

1. `scenario_id` が registry.yaml に存在しない → `REGISTRY_MISSING` エラー
2. `path: null` → built-in default シナリオ（ハードコード）
3. `path: xxx.json` → `scenarios/xxx.json` からロード

### 1.4 ScenarioEntry フィールド

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| scenario_id | string | ✓ | 一意な識別子 |
| path | string\|null | ✓ | ファイルパス（null=built-in） |
| tags | list[str] | - | フィルタリング用タグ |
| recommended_profile | string | - | 推奨プロファイル（dev/gate/full） |
| description | string | - | 説明文 |

---

## 2. Integrity Validation（整合性検証）

### 2.1 検証項目

シナリオをロードする際、以下の整合性チェックを行います：

| チェック | エラーコード | 条件 |
|----------|-------------|------|
| Exit先の存在 | `EXIT_TARGET_MISSING` | exits に記載された location が存在しない |
| キャラクター位置 | `CHAR_LOCATION_MISSING` | character.location が存在しない |
| オブジェクト位置 | `OBJ_LOCATION_MISSING` | prop.location が存在しない |
| scenario_id 一致 | `SCENARIO_ID_MISMATCH` | registry の id とファイル内 name が不一致 |

### 2.2 ValidationResult

```python
@dataclass
class ValidationResult:
    passed: bool
    errors: list[SchemaValidationError]

    @property
    def error_codes(self) -> list[str]:
        return [e.code.value for e in self.errors]
```

### 2.3 SchemaValidationError

```python
class SchemaValidationError(Exception):
    code: ValidationErrorCode  # エラー種別
    message: str               # 人間可読メッセージ
    details: dict              # 追加コンテキスト
```

---

## 3. Reproducibility Metadata（再現性メタデータ）

### 3.1 ハッシュ定義

| ハッシュ | 対象 | 用途 |
|---------|------|------|
| scenario_hash | scenario JSON（そのまま） | シナリオファイルの変更検出 |
| world_hash | WorldState（canonical JSON） | 実験条件の同一性検証 |

### 3.2 Canonical JSON ルール

world_hash 計算時、以下のルールで正規化します：

1. **キーのソート**: dict のキーはアルファベット順
2. **リストのソート**: id/name がある場合はそれでソート
3. **ランタイムフィールド除外**:
   - `events` （ターン中に蓄積）
   - `time.turn` （毎ターン変動）
   - `_` で始まるフィールド（内部用）

### 3.3 run_meta 出力

```json
{
  "run_meta": {
    "scenarios": {
      "default": {
        "scenario_id": "default",
        "scenario_path": "default",
        "scenario_resolved_path": "built-in",
        "registry_path": "experiments/scenarios/registry.yaml",
        "scenario_hash": "c05916c746e9ce8a",
        "world_hash": "c05916c746e9ce8a",
        "world_summary": {
          "counts": {"locations": 2, "objects": 4, "characters": 2},
          "objects_top10": ["マグカップ", "コーヒーメーカー", ...],
          "locations": ["キッチン", "リビング"]
        },
        "validation_passed": true,
        "validation_errors": []
      }
    }
  }
}
```

---

## 4. Artifacts（アーティファクト）

### 4.1 セッション単位のアーティファクト

| ファイル | 説明 |
|----------|------|
| `world_canonical.json` | canonical JSON 形式の WorldState（再現性検証用） |

### 4.2 ターン単位のアーティファクト

| ファイル | 条件 | 説明 |
|----------|------|------|
| `turn_NNN_raw_output.txt` | 常時 | LLM生の出力（切り詰めなし） |
| `turn_NNN_repaired_output.txt` | repair時のみ | 修復後の出力 |
| `turn_NNN_parsed.json` | 常時 | パース結果メタデータ |

---

## 5. エラーコード一覧

| コード | 説明 |
|--------|------|
| `REGISTRY_MISSING` | scenario_id が registry.yaml に存在しない |
| `SCENARIO_ID_MISMATCH` | registry と JSON ファイルの name が不一致 |
| `SCENARIO_FILE_NOT_FOUND` | 指定されたファイルが存在しない |
| `REGISTRY_LOAD_ERROR` | registry.yaml の読み込みに失敗 |
| `EXIT_TARGET_MISSING` | exits の参照先 location が未定義 |
| `OBJ_LOCATION_MISSING` | prop の location が未定義 |
| `CHAR_LOCATION_MISSING` | character の location が未定義 |
| `HASH_COMPUTATION_ERROR` | ハッシュ計算に失敗 |

---

## 6. 利用方法

### 6.1 シナリオの追加

1. `experiments/scenarios/` にJSONファイルを作成
2. `experiments/scenarios/registry.yaml` にエントリを追加
3. 実験実行: `python -m experiments.gm_2x2_runner --scenario your_scenario`

### 6.2 検証エラーの対処

```
SchemaValidationError: [EXIT_TARGET_MISSING] Exit target '寝室' from 'キッチン' does not exist
```

→ シナリオJSONの `locations.キッチン.exits` に記載された「寝室」が未定義。
  `locations` に「寝室」を追加するか、exits から削除してください。

---

*GM-019: Scenario/World整合性固定 + Spec追記 + 回帰テスト*
