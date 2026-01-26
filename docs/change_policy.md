# Change Policy

**Status**: Active (2026-01-25)

## Purpose

P1微調整沼の再発防止。変更レーンを明確化し、Core機能の安定性を保証する。

## Change Lanes

### Lane-Core (Frozen)

**対象**:
- GM判定ロジック (`preflight.py`, `action_judge.py`, `stall_detector.py`)
- Format repair (`output_parser.py`)
- Retry budget (`retry_budget` in interfaces)
- P0 Freeze対象全般 (see `docs/P0_FREEZE_POLICY.md`)

**ルール**:
- **変更禁止** (バグ修正のみ例外)
- 閾値・重み・定数の変更も禁止
- 新機能追加はLane-Researchで検証後に別PRで

### Lane-Ops (Changeable)

**対象**:
- Scenario files (`experiments/scenarios/*.json`)
- Registry (`experiments/scenarios/registry.yaml`)
- CLI/Tools (`scripts/scenario_tools.py`)
- GUI (`gui_nicegui/`)
- Reports (`reports/`)
- Documentation (`docs/`)

**ルール**:
- 自由に変更可能
- テスト通過必須 (`make test`)
- Gate実行推奨 (`make run-gate`)

### Lane-Research (Isolated)

**対象**:
- 改善実験（成功率向上、新アルゴリズム等）
- 新Director実装
- プロンプト最適化

**ルール**:
- **隔離ブランチ (`experiment/*`) でのみ実施**
- mainへのマージはGate通過後に別PRで
- 実験結果は `results/` に保存、`reports/` にレポート

## Exception Rules

Lane-Coreへの変更が許可される例外条件:

| 条件 | 許可レベル |
|------|-----------|
| Crash/例外発生 | 即時修正可 |
| ログ欠損/出力不正 | 即時修正可 |
| Schema破壊 | 即時修正可 |
| 成功率低下 | Research branchで検証 |
| 閾値調整 | Research branchで検証 |

## Enforcement

1. **PRレビュー**: Lane-Core変更時は理由必須
2. **CI**: `make test-freeze` でP0スナップショット検証
3. **Gate**: `make run-gate` で動作確認

---

*See also: [P0_FREEZE_POLICY.md](P0_FREEZE_POLICY.md), [dev_workflow.md](dev_workflow.md)*
