"""Ollamaバックエンドアダプタ"""

import requests
from typing import Optional
from .base import LLMBackendAdapter


class OllamaAdapter(LLMBackendAdapter):
    """Ollama バックエンド"""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:11434",
        model: str = "gemma3:12b"
    ):
        self.base_url = base_url
        self.model = model
    
    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """テキスト生成"""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens}
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            return f"[Ollama生成エラー: {e}]"
    
    def is_available(self) -> bool:
        """バックエンドが利用可能かチェック"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
