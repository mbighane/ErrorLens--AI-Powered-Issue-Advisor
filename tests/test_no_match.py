import pytest

# Prevent tests from constructing real Azure DevOps clients.
class _DummyConnector:
    def __init__(self, *args, **kwargs):
        pass

import backend.app.services.hybrid_bug_search_service as _hbss
import backend.app.services.ado_wiki_search_service as _awss


@pytest.fixture(autouse=True)
def patch_azure_devops_connectors(monkeypatch):
    monkeypatch.setattr(_hbss, "AzureDevOpsConnector", _DummyConnector)
    monkeypatch.setattr(_awss, "AzureDevOpsConnector", _DummyConnector)

from backend.app.services.ado_bug_search_service import ADOBugSearchService
from backend.app.services.ado_wiki_search_service import ADOWikiSearchService
from backend.app.agents.recommendation_agent import RecommendationAgent
from backend.app.config import settings


@pytest.mark.asyncio
async def test_ado_bug_search_returns_no_match_for_low_similarity(monkeypatch):
    svc = ADOBugSearchService()

    async def fake_semantic_search(query, top_k=10):
        return [
            {"id": "1", "title": "Test Bug", "description": "desc", "similarity_score": 0.05}
        ]

    async def no_exact_matches(query, top_k=10):
        return "no match"

    monkeypatch.setattr(svc.hybrid_service, "_semantic_search", fake_semantic_search)
    monkeypatch.setattr(svc.hybrid_service, "_exact_match_search", no_exact_matches)

    result = await svc.search_similar_bugs("some query", top_k=5)
    assert result == "no match"


@pytest.mark.asyncio
async def test_title_exact_match_is_not_rejected(monkeypatch):
    svc = ADOBugSearchService()

    async def fake_semantic_search(query, top_k=10):
        return [
            {"id": "42", "title": "Exact Title Match", "description": "desc", "similarity_score": 0.12}
        ]

    async def no_exact_matches(query, top_k=10):
        return "no match"

    monkeypatch.setattr(svc.hybrid_service, "_semantic_search", fake_semantic_search)
    monkeypatch.setattr(svc.hybrid_service, "_exact_match_search", no_exact_matches)

    result = await svc.search_similar_bugs("Exact Title Match", top_k=5)
    assert isinstance(result, list)
    assert result[0].title == "Exact Title Match"


@pytest.mark.asyncio
async def test_ado_wiki_search_returns_no_match_for_low_similarity(monkeypatch):
    svc = ADOWikiSearchService()
    svc.local_vector_service = None
    svc.azure_ai_search_service.enabled = False

    async def fake_ado_search_wiki(query, top_k=5):
        return [
            {"title": "Some Page", "content": "content", "similarity_score": 0.01, "path": "/p"}
        ]

    monkeypatch.setattr(
        svc.connector, "search_wiki_pages", fake_ado_search_wiki, raising=False
    )

    result = await svc.search_wiki_pages("some wiki query", top_k=5)
    assert result == "no match"


def test_recommendation_agent_respects_no_match_sentinel():
    agent = RecommendationAgent()
    # When similar_bugs is the sentinel and there are no root causes,
    # the agent should return the explicit "no match" sentinel and avoid calling the LLM.
    result = agent._generate_ai_fixes(original_query="q", similar_bugs="no match", root_causes=[])
    assert result == "no match"


def test_search_thresholds_are_more_permissive():
    assert settings.search_similarity_threshold < 0.08
    assert settings.title_overlap_min_score < 0.25
    assert settings.semantic_title_overlap_min_score <= 0.05


