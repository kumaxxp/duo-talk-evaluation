# Development Workflow

**Status**: Active (2026-01-25)

## Overview

duo-talk-evaluation開発の標準ワークフロー。P1微調整沼を防ぐためのガードレール。

## Core Principles

### 1. Gate Success = Done

> **Gateに通ればOK。成功率改善はResearchへ。**

- Gate (`make run-gate`) が通れば実装完了
- 成功率の数値改善を追い求めない
- 改善実験は隔離ブランチで別途実施

### 2. Timebox Rule

| セッション | 上限 |
|-----------|------|
| 時間 | 90分 |
| PR数 | 2件 |

超過したら一度休憩/レビュー。

### 3. No Improvement Metrics Tracking

**禁止事項**:
- "成功率を○%→○%に改善" の追跡
- "リトライ回数を○回→○回に削減" の目標設定
- 数値改善のための閾値微調整

**許可事項**:
- Gate通過の確認
- Crash/エラーの修正
- 新シナリオでのGate実行

## Standard Workflow

### Feature Development (Lane-Ops)

```
1. ブランチ作成: feat/xxx または func/xxx
2. TDD: テスト作成 → 実装 → リファクタ
3. 検証: make test && make test-freeze
4. Gate: make run-gate SCENARIO=xxx
5. PR作成: テンプレート記入
6. マージ
```

### Research Experiment (Lane-Research)

```
1. ブランチ作成: experiment/xxx
2. 実験実装（Core変更可）
3. 検証: make test
4. 実験実行: 複数シナリオでデータ収集
5. レポート作成: reports/xxx.md
6. 結論が出るまでmainにマージしない
7. 採用決定後、別PRでmainに統合
```

### Bug Fix (Lane-Core Exception)

```
1. ブランチ作成: fix/xxx
2. 最小限の修正のみ
3. 検証: make test && make test-freeze
4. Gate: make run-gate SCENARIO=xxx
5. PR作成: 例外理由を明記
6. レビュー後マージ
```

## Quick Commands

```bash
# 開発サイクル
make test              # 全テスト
make test-freeze       # P0スナップショット検証
make run-gate          # Gateプロファイル実行

# シナリオ操作
make new-scenario id=scn_xxx
make lint-scenarios
make scenario-summary s=xxx

# GUI
make gui               # NiceGUI起動 (http://localhost:8080)
```

## Gate Definition

| Profile | Seeds | Turns | 用途 |
|---------|-------|-------|------|
| dev | 1 | 3 | 開発中の素早い確認 |
| gate | 3 | 5 | PR前の検証 |
| full | 5 | 10 | リリース前の完全検証 |

**Gate通過条件**:
- 実行完了（クラッシュなし）
- ログ出力正常
- Format repair動作確認

**Gate通過条件に含まれないもの**:
- 成功率○%以上
- リトライ回数○回以下
- 特定スコア達成

---

*See also: [change_policy.md](change_policy.md), [P0_FREEZE_POLICY.md](P0_FREEZE_POLICY.md)*
