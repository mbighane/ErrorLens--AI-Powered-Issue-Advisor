"""Deployment-specific chat provider implementations."""

from __future__ import annotations

from typing import Dict, List

from openai import AzureOpenAI, OpenAI

from ..config import settings
from .interfaces import IChatProvider


class AzureChatProvider(IChatProvider):
    def __init__(self) -> None:
        self._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        self._model = settings.azure_openai_chat_deployment

    @property
    def provider_name(self) -> str:
        return "azure_openai"

    @property
    def model_name(self) -> str:
        return self._model

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


class OllamaChatProvider(IChatProvider):
    def __init__(self) -> None:
        self._client = OpenAI(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
        )
        self._model = settings.ollama_chat_model

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
