# Step5 完了報告

## ステップ番号
**Step5: 魂の注入 (Real Integration)**

## 編集ファイル
- `gui_nicegui/adapters/core_adapter.py` (duo-talk-core 実統合)
- `gui_nicegui/adapters/director_adapter.py` (duo-talk-director 実統合)
- `gui_nicegui/clients/gm_client.py` (HTTP 実接続)

## 実施内容

### 1. Core Adapter (core_adapter.py)

duo-talk-core との実統合を実装:

```python
# パス解決とインポート
from duo_talk_core.llm_client import OllamaClient, GenerationConfig
from duo_talk_core.two_phase_engine import TwoPhaseEngine
from duo_talk_core.character import Character, CharacterConfig

# キャラクター設定
_characters = {
    "やな": Character(_yana_config),
    "あゆ": Character(_ayu_config),
}

# LLM クライアント初期化
_llm_client = OllamaClient(model="gemma3:12b")
_two_phase_engine = TwoPhaseEngine(max_thought_tokens=80)

# 同期 → 非同期ラップ
def _sync_generate_thought(speaker, topic, history):
    prompt = _two_phase_engine.build_phase1_prompt(character, topic, history)
    raw_response = _llm_client.generate(prompt, GenerationConfig(max_tokens=80))
    return _two_phase_engine.parse_thought_response(raw_response)

async def generate_thought(...):
    thought = await asyncio.wait_for(
        asyncio.to_thread(_sync_generate_thought, speaker, topic, history),
        timeout=timeout,
    )
```

特徴:
- `asyncio.to_thread` で同期 LLM 呼び出しを非同期化
- ImportError 発生時は mock にフォールバック
- Ollama が利用不可の場合も mock にフォールバック

### 2. Director Adapter (director_adapter.py)

duo-talk-director との実統合を実装:

```python
# インポート
from duo_talk_director.director_minimal import DirectorMinimal
from duo_talk_director.interfaces import DirectorStatus

_director = DirectorMinimal(strict_thought_check=True)

# 同期チェック関数
def _sync_director_check(stage, content, context):
    if stage == "thought":
        formatted_content = f"Thought: {content}\nOutput: "
    else:
        formatted_content = f"Thought: (thinking)\nOutput: {content}"

    evaluation = _director.evaluate_response(
        speaker=speaker,
        response=formatted_content,
        topic=topic,
        history=history,
        turn_number=turn_number,
    )

    status_map = {"PASS": "PASS", "WARN": "PASS", "RETRY": "RETRY", "MODIFY": "RETRY"}
    return status_map.get(evaluation.status.value, "PASS")
```

特徴:
- DirectorMinimal を使用（静的バリデーション、LLM 不要）
- Thought/Speech のフォーマット整形を適用
- 評価ステータスを GUI 期待形式にマッピング

### 3. GM Client (gm_client.py)

httpx による実 HTTP 接続を実装:

```python
GM_BASE_URL = "http://localhost:8001"
_gm_available: bool | None = None  # 自動検出

async def _check_gm_availability():
    async with httpx.AsyncClient(timeout=2.0) as client:
        response = await client.get(f"{GM_BASE_URL}/health")
        _gm_available = response.status_code == 200

async def post_step(payload, timeout=3.0, use_mock=None):
    if use_mock is None:
        if _gm_available is None:
            await _check_gm_availability()
        use_mock = not _gm_available

    gm_request = {
        "session_id": payload.get("session_id", "gui_session"),
        "turn_number": payload.get("turn_number", 0),
        "speaker": speaker,
        "raw_output": f"Thought: (thinking)\nOutput: {utterance}",
        "world_state": {...},
    }

    response = await client.post(f"{GM_BASE_URL}/v1/gm/step", json=gm_request)
```

特徴:
- 起動時に `/health` エンドポイントで GM 可用性を自動検出
- `POST /v1/gm/step` で GMStepRequest 互換ペイロードを送信
- GM 不可時は mock にフォールバック
- レスポンスを GUI 形式にマッピング

## E2E 検証結果

### サービス可用性確認

```
Core available: True
Director available: True
GM available: False (サーバー未起動のため mock フォールバック)
```

### Core 統合テスト

```
=== Core Integration Test ===
Generated thought: あゆが起きたかな？なんだか今日は朝からワクワクするな、何か楽しいことありそう！
Latency: 22568ms
```

### Director 統合テスト

```
=== Director Integration Test ===
Result: {'status': 'PASS', 'reasons': ['OK'], 'repaired_output': None, 'injected_facts': None, 'latency_ms': 1}
```

### テスト実行結果

```
======================= 729 passed, 12 skipped in 2.54s ========================
```

## 実行コマンド

### サービス起動手順

```bash
# 1. (オプション) GM サービス起動
cd duo-talk-gm && uvicorn duo_talk_gm.main:app --port 8001

# 2. GUI 起動
make gui
# または
python -m gui_nicegui.main
```

### テスト実行

```bash
python -m pytest tests/ -v
```

## フォールバック動作確認

| コンポーネント | 実サービス | フォールバック | 確認結果 |
|---------------|-----------|---------------|---------|
| Core | duo-talk-core + Ollama | mock | ✅ 自動切替 |
| Director | duo-talk-director | mock | ✅ 自動切替 |
| GM | localhost:8001 | mock | ✅ 自動切替 |

## 設計上の選択

1. **DirectorMinimal の採用**: DirectorHybrid は LLM クライアントを必要とするため、静的チェックのみの DirectorMinimal を使用。将来的に hybrid 対応も可能。

2. **自動検出パターン**: 各サービスの可用性を起動時に自動検出し、利用不可の場合は mock にシームレスにフォールバック。

3. **asyncio.to_thread の使用**: 同期 API (Ollama LLM 呼び出し) を非同期イベントループでブロッキングせずに実行。

## 未解決事項

- GM サービスとの実接続は GM サーバー起動時にのみ確認可能（現状は mock で検証済み）
- Core の Thought 生成に 20秒以上かかる場合がある（Ollama/gemma3:12b の応答速度依存）

## 次のステップ

Step6 以降の実装（Cline 仕様管理による指示待ち）

---
**実施日時**: 2026-01-30
**実施者**: Claude Code
