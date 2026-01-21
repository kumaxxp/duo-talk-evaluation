"""利用可能なGeminiモデル一覧を表示"""

import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google import genai


def main():
    # API Key確認
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("エラー: GEMINI_API_KEY環境変数が設定されていません")
        print("export GEMINI_API_KEY='your-key' で設定してください")
        return

    client = genai.Client(api_key=api_key)

    print("=== 利用可能なGeminiモデル一覧 ===\n")

    try:
        # カテゴリ別に分類
        flash_models = []
        pro_models = []
        other_models = []

        for model in client.models.list():
            name = model.name
            # models/ プレフィックスを除去
            short_name = name.replace("models/", "")

            if "flash" in name.lower():
                flash_models.append(short_name)
            elif "pro" in name.lower():
                pro_models.append(short_name)
            else:
                other_models.append(short_name)

        # Flash モデル
        print("【Flash モデル（高速・低コスト）】")
        for name in sorted(flash_models):
            print(f"  - {name}")

        # Pro モデル
        print("\n【Pro モデル（高性能）】")
        for name in sorted(pro_models):
            print(f"  - {name}")

        # その他
        print("\n【その他のモデル】")
        for name in sorted(other_models)[:10]:  # 最初の10個のみ表示
            print(f"  - {name}")
        if len(other_models) > 10:
            print(f"  ... 他 {len(other_models) - 10} 件")

        print(f"\n合計: {len(flash_models) + len(pro_models) + len(other_models)} モデル")

    except Exception as e:
        print(f"取得エラー: {e}")


if __name__ == "__main__":
    main()
