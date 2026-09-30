"""Deployment-specific search provider adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from ..services.ado_bug_search_service import ADOBugSearchService
from ..services.ado_wiki_search_service import ADOWikiSearchService
from .interfaces import ISearchProvider


class BaseSearchProvider(ISearchProvider):
    def __init__(self) -> None:
        self._bug_service = ADOBugSearchService()
        self._wiki_service = ADOWikiSearchService()

    async def search_bugs(self, query: str, top_k: int = 5) -> Union[List[Any], str]:
        return await self._bug_service.search_similar_bugs(query, top_k)

    async def search_wiki(self, query: str, top_k: int = 5) -> Union[List[Any], str]:
        return await self._wiki_service.search_wiki_pages(query, top_k)


class AzureSearchProvider(BaseSearchProvider):
    @property
    def provider_name(self) -> str:
        return "azure_ai_search"


class LocalSearchProvider(BaseSearchProvider):
    @property
    def provider_name(self) -> str:
        return "local_vector_index"
