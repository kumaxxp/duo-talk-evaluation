"""KoboldCPPバックエンドアダプタ"""

import requests
from .base import LLMBackendAdapter


class KoboldCPPAdapter(LLMBackendAdapter):
    """KoboldCPP バックエンド（Gemma2 Swallow対応）"""
    
    def __init__(self, base_url: str = "http://localhost:5001"):
        self.base_url = base_url
    
    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """テキスト生成"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/generate",
                json={
                    "prompt": prompt,
                    "max_length": max_tokens,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "rep_pen": 1.1,
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()["results"][0]["text"]
        except Exception as e:
            return f"[KoboldCPP生成エラー: {e}]"
    
    def is_available(self) -> bool:
        """バックエンドが利用可能かチェック"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/model", timeout=5)
            return response.status_code == 200
        except:
            return False
