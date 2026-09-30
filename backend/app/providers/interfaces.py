"""Provider contracts shared by agents and application services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional, Union


class IChatProvider(ABC):
    """Generate text without exposing the underlying model vendor."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        ...


class IEmbeddingProvider(ABC):
    """Create embeddings without exposing the embedding vendor."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        ...

    @abstractmethod
    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        ...


class ISearchProvider(ABC):
    """Common search contract for deployment-specific retrieval providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    async def search_bugs(
        self,
        query: str,
        top_k: int = 5,
    ) -> Union[List[Any], str]:
        ...

    @abstractmethod
    async def search_wiki(
        self,
        query: str,
        top_k: int = 5,
    ) -> Union[List[Any], str]:
        ...
