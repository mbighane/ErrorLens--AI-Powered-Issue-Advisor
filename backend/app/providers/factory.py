"""Create deployment-specific providers from application settings."""

from __future__ import annotations

from typing import Optional

from ..config import settings
from .interfaces import IChatProvider, IEmbeddingProvider, ISearchProvider


def create_chat_provider() -> Optional[IChatProvider]:
    from .chat_providers import AzureChatProvider, OllamaChatProvider

    if settings.is_on_prem_deployment:
        if not settings.ollama_enabled:
            return None
        return OllamaChatProvider()

    if settings.use_azure_openai:
        return AzureChatProvider()

    return None


def create_embedding_provider() -> IEmbeddingProvider:
    from .embedding_providers import AzureEmbeddingProvider, OllamaEmbeddingProvider

    if settings.is_on_prem_deployment:
        return OllamaEmbeddingProvider()
    return AzureEmbeddingProvider()


def create_search_provider() -> ISearchProvider:
    from .search_providers import AzureSearchProvider, LocalSearchProvider

    if settings.is_on_prem_deployment:
        return LocalSearchProvider()
    return AzureSearchProvider()
