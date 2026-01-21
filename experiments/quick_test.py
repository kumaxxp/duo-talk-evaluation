"""簡易動作確認スクリプト"""

import sys
import os
import time
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.evaluator import DialogueEvaluator, DEFAULT_MODEL_NAME

# サンプル会話
sample_conversation = [
    {"speaker": "やな", "content": "おはよう、あゆ。今日は何する予定？"},
    {"speaker": "あゆ", "content": "おはよー！えっとね、AIの勉強する予定だよ"},
    {"speaker": "やな", "content": "勉強偉いわね。具体的には何を勉強するの？"},
    {"speaker": "あゆ", "content": "強化学習について調べるんだ！お姉ちゃんは？"},
    {"speaker": "やな", "content": "私は散歩でもしようかしら。考え事もできるし"},
    {"speaker": "あゆ", "content": "お姉ちゃんらしいね。でも寒いから気をつけてね"},
]


def main():
    # API Key確認
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("エラー: GEMINI_API_KEY環境変数が設定されていません")
        print("export GEMINI_API_KEY='your-key' で設定してください")
        return

    print("=== duo-talk-evaluation 動作確認 ===\n")

    # 評価システム初期化
    print(f"評価システム初期化中... (モデル: {DEFAULT_MODEL_NAME})")
    try:
        evaluator = DialogueEvaluator()
        print("✓ 初期化完了\n")
    except Exception as e:
        print(f"✗ 初期化失敗: {e}")
        return

    # 会話表示
    print("評価対象の会話:")
    for msg in sample_conversation:
        print(f"  {msg['speaker']}: {msg['content']}")
    print()

    # 評価実行（リトライ対応）
    print("Gemini APIで評価中...")
    max_retries = 3
    metrics = None

    for attempt in range(max_retries):
        try:
            metrics = evaluator.evaluate_conversation(sample_conversation)
            if "評価失敗" not in str(metrics.issues):
                print("✓ 評価完了\n")
                break
            # 429エラーの場合はリトライ
            if "429" in str(metrics.issues) or "RESOURCE_EXHAUSTED" in str(metrics.issues):
                if attempt < max_retries - 1:
                    wait_time = 10 * (attempt + 1)
                    print(f"  Rate Limit発生。{wait_time}秒待機後リトライ ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
            break
        except Exception as e:
            print(f"✗ 評価エラー: {e}")
            if attempt < max_retries - 1:
                wait_time = 10 * (attempt + 1)
                print(f"  {wait_time}秒待機後リトライ ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                return

    if not metrics:
        print("✗ 評価に失敗しました")
        return
    
    # 結果表示
    print("=== 評価結果 ===")
    print(f"総合スコア: {metrics.overall_score:.2f}")
    print()
    print("詳細メトリクス:")
    print(f"  キャラクター一貫性: {metrics.character_consistency:.2f}")
    print(f"  話題の新規性:       {metrics.topic_novelty:.2f}")
    print(f"  姉妹関係性:         {metrics.relationship_quality:.2f}")
    print(f"  対話の自然さ:       {metrics.naturalness:.2f}")
    print(f"  情報の具体性:       {metrics.concreteness:.2f}")
    print()
    
    if metrics.strengths:
        print("良かった点:")
        for strength in metrics.strengths:
            print(f"  ✓ {strength}")
        print()
    
    if metrics.issues:
        print("問題点:")
        for issue in metrics.issues:
            print(f"  ✗ {issue}")
        print()
    
    if metrics.suggestions:
        print("改善提案:")
        for suggestion in metrics.suggestions:
            print(f"  → {suggestion}")

if __name__ == "__main__":
    main()
