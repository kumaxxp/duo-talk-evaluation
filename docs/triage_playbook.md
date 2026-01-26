# Triage Playbook

Quick reference for classifying and resolving test failures.

## Decision Table: Core vs Ops vs Research

| Symptom | Classification | Lane | Action |
|---------|---------------|------|--------|
| Test crash / exception | (A) Core bug | Lane-Core | Minimal fix, add regression test |
| Missing log / schema break | (A) Core bug | Lane-Core | Fix logging/schema only |
| Test expects old behavior | (B) Spec drift | Lane-Ops | Update test fixtures/expectations |
| Flaky / non-deterministic | (C) Flaky | Lane-Ops | Add seeding/mocking, or xfail |
| Experimental feature test | - | Lane-Research | Move to `experiments/*` |

## Lane Definitions

- **Lane-Core**: `duo-talk-core/`, `duo-talk-director/`, `duo-talk-gm/src/`
  - FROZEN except crash/log/schema exceptions
  - Requires: Regression test + docs/change_policy.md note

- **Lane-Ops**: Tests, configs, CI, GUI, Makefile
  - Freely changeable
  - No core behavior changes

- **Lane-Research**: `experiments/*`, `results/*`
  - Isolated experiments
  - May contain flaky/experimental code

## Required Evidence Checklist

Before fixing, collect:

```markdown
- [ ] Test name: `tests/test_xxx.py::TestClass::test_method`
- [ ] Stack trace: First 3 lines of failure
- [ ] Classification: (A) Core / (B) Spec / (C) Flaky
- [ ] Artifact refs: `results/<run_id>/` if applicable
- [ ] run_meta.gm_version: Version from experiment output
```

## Fix Templates

### (A) Core Bug Fix

```bash
# 1. Create conftest.py fixture if state leakage
# 2. Minimal code fix (no refactoring)
# 3. Add regression test
# 4. Update docs/change_policy.md with exception note
```

### (B) Spec Drift Fix

```bash
# 1. Update test fixture/expected values
# 2. Add docstring explaining new spec
# 3. No core code changes
```

### (C) Flaky Fix

```bash
# Option 1: Add deterministic seeding
random.seed(42)

# Option 2: Add pytest marker for skip in CI
@pytest.mark.flaky(reason="Non-deterministic LLM output")
def test_xxx():
    ...

# Option 3: Move to experiments/* if truly experimental
```

## Quick Commands

```bash
# Run CI gate (gm + eval + lint)
make ci-gate

# Run demo pack with gate profile
make demo-pack-gate

# Lint scenarios
make lint-scenarios

# Check test isolation
python -m pytest tests/test_xxx.py::test_single -v --tb=long
```

## Play Mode: 30秒で当たりをつける

### シナリオ探索

```bash
# シナリオをPlay Modeで探索
make play s=coffee_trap

# 基本コマンド
>>> look          # 現在地確認
>>> move キッチン  # 移動
>>> take コーヒー  # オブジェクト取得
>>> open 引き出し  # コンテナを開ける
>>> search        # 隠しオブジェクト探索
>>> where         # 現在地とキャラクター位置
>>> inventory     # 所持品一覧
>>> map           # 全体マップ表示
```

### Issue特定フロー

1. **GUI Demo Pack実行** → Issues Only view
2. **Issue優先度順**で確認:
   - Crash (赤) > Schema (オレンジ) > FormatBreak > GiveUp > Retry
3. **最初のIssue turnの詳細**を展開（自動展開）
4. **guidance_card**からブロック原因特定:
   ```
   [ERROR_CODE] MISSING_OBJECT
   [BLOCKED_TARGET] コーヒー豆
   ```
5. **Play Modeで再現**:
   ```bash
   make play s=coffee_trap
   >>> look       # コーヒー豆がpropsにない！
   >>> search     # hidden_objectsにあるかも？
   ```

### よくあるパターン

| 症状 | 原因 | 対処 |
|------|------|------|
| MISSING_OBJECT | propsにない | シナリオJSONにオブジェクト追加 |
| 移動できない | exitsにない | シナリオJSONにexit追加 |
| 隠しオブジェクト | hidden_objects | search コマンドで発見 |
| コンテナ内 | containers | open コマンドで開ける |

## Post-Fix Verification

```bash
# 1. Run failing test in isolation
python -m pytest tests/test_xxx.py::test_method -v

# 2. Run full test suite
make test

# 3. Run CI gate
make ci-gate

# 4. Verify no regressions
git diff --stat
```
