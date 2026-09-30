"""Small Ollama HTTP client used by local-only deployments."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import requests


class OllamaChatResponse(str):
    """Chat text that also matches the OpenAI response shape used by callers."""

    def __new__(cls, content: str) -> "OllamaChatResponse":
        response = super().__new__(cls, content)
        response.choices = [
            SimpleNamespace(message=SimpleNamespace(content=content))
        ]
        return response


class OllamaClient:
    def __init__(self, base_url: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return response.ok
        except requests.RequestException:
            return False

    def embed_texts(self, texts: List[str], model: str) -> List[List[float]]:
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": model, "input": texts},
            timeout=self.timeout,
        )
        if response.status_code == 404:
            embeddings = [self._embed_text(text, model) for text in texts]
            return embeddings
        response.raise_for_status()
        return response.json()["embeddings"]

    def _embed_text(self, text: str, model: str) -> List[float]:
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> OllamaChatResponse:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        return OllamaChatResponse(content)