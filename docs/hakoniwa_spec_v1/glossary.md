# 用語集 v1.0

## System（システム）
- **HAKONIWA‑G3**：環境決定論（World is Truth）に基づく箱庭型の会話・行動システム。

## Component（コンポーネント）
- **Runner**：2×2 実験（A/B/C/D）を回し、結果（results.json/REPORT.md/examples_index.csv 等）を出力する実行器。
- **Generator**：LLM（またはシミュレーション）から出力を生成する層（Sim / Real / OpenAI互換）。
- **GM Service**：WorldState を真実として保持し、判定・更新・ヒント注入・修復を行う審判。

## World / Scenario（世界）
- **Scenario**：決定論的な世界パッケージ。場所（locations/exits）、物体（objects/aliases/owner）、キャラ（characters）を含む。
- **WorldState**：Scenario を実行中に保持した状態（現在地、所有、プロパティ、ロック状態など）。

## Experiment（実験）
- **2×2**：Inject と GM の ON/OFF による4条件比較（A/B/C/D）。
- **Metrics**：Success Rate、impossible_action_rate、format_break、stall、latency 等。

## Gate Test（ゲート）
- **Gate Test**：旧称 Taste。段階的な結合確認（Nav / Retry / Resilience など）。
- **Gate‑Nav**：移動（MOVE）制約が `exits` で制御されることを確認。
- **Gate‑Retry**：Preflight + Retry で自己修正できることを確認（最重要）。
- **Gate‑Resilience**：パーサ修復でフォーマット崩れに耐えることを確認。

## システム固有の現象
- **Impossible Action**：世界の真実と矛盾した行動（存在しない物体・持っていない物・行けない場所など）。
- **Preflight**：実行前の事前チェック。NGなら deny ではなく guidance を注入し、再生成を促す。
- **Guidance / Fact Cards**：システム側の「物語外」情報注入。Actorが自律修正するためのフィードバック。
- **Silent Correction**：謝罪や言い訳無しで、行動だけが自然に修正されること。

## Registry & Validation（GM-019）
- **Scenario Registry**：scenario_id → ファイルパスの解決を一元管理する Single Source of Truth。`registry.yaml` で定義。
- **scenario_hash**：シナリオJSONから計算した SHA256 ハッシュ（16文字）。シナリオファイルの変更検出に使用。
- **world_hash**：WorldState の canonical JSON から計算した SHA256 ハッシュ（16文字）。ランタイムフィールドを除外した再現性検証用。
- **Canonical JSON**：決定論的なハッシュ計算のための正規化JSON。キーのソート、ランタイムフィールド除外を行う。
- **ValidationErrorCode**：整合性検証エラーの種別コード（REGISTRY_MISSING, SCENARIO_ID_MISMATCH, EXIT_TARGET_MISSING 等）。
- **SchemaValidationError**：整合性検証エラーを示す例外。code, message, details を含む。

## Artifacts（アーティファクト）
- **world_canonical.json**：セッション単位で保存される canonical JSON 形式の WorldState。
- **raw_output.txt**：各ターンのLLM生出力（切り詰めなし）。
- **repaired_output.txt**：フォーマット修復が行われた場合の修復後出力。
- **parsed.json**：パース結果のメタデータ（thought, speech, action_intents, format_break情報など）。

