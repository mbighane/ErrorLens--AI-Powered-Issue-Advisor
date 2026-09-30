"""Deployment-specific embedding provider implementations."""

from __future__ import annotations

from typing import Iterable, List

from openai import AzureOpenAI, OpenAI

from ..config import settings
from .interfaces import IEmbeddingProvider


class AzureEmbeddingProvider(IEmbeddingProvider):
    def __init__(self) -> None:
        if not settings.use_azure_openai:
            raise RuntimeError("Azure OpenAI embedding credentials are not configured")
        self._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        self._model = settings.azure_openai_embedding_deployment

    @property
    def dimensions(self) -> int:
        return settings.azure_openai_embedding_dims

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        values = [text or " " for text in texts]
        if not values:
            return []
        response = self._client.embeddings.create(model=self._model, input=values)
        vectors = [item.embedding for item in response.data]
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError(f"Azure embedding model must return {self.dimensions} dimensions")
        return vectors


class OllamaEmbeddingProvider(IEmbeddingProvider):
    def __init__(self) -> None:
        self._client = OpenAI(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
        )
        self._model = settings.ollama_embedding_model

    @property
    def dimensions(self) -> int:
        return settings.ollama_embedding_dims

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        values = [text or " " for text in texts]
        if not values:
            return []
        response = self._client.embeddings.create(model=self._model, input=values)
        vectors = [item.embedding for item in response.data]
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError(f"Ollama embedding model must return {self.dimensions} dimensions")
        return vectors
