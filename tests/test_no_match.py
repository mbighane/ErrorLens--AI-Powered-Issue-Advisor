import pytest

# Prevent tests from instantiating the real AzureDevOpsConnector which makes
# network calls (and may have expired tokens). Patch the symbol in the
# modules that import it so service constructors don't contact ADO.
class _DummyConnector:
    def __init__(self, *args, **kwargs):
        pass

import backend.app.services.ado_bug_search_service as _abss
import backend.app.services.ado_wiki_search_service as _awss
_abss.AzureDevOpsConnector = _DummyConnector
_awss.AzureDevOpsConnector = _DummyConnector

from backend.app.services.ado_bug_search_service import ADOBugSearchService
from backend.app.services.ado_wiki_search_service import ADOWikiSearchService
from backend.app.agents.recommendation_agent import RecommendationAgent


@pytest.mark.asyncio
async def test_ado_bug_search_returns_no_match_for_low_similarity():
    svc = ADOBugSearchService()
    # Ensure local index path is not used
    svc.local_vector_service.enabled = False

    # Mock redis fallback to return only very-low-similarity results
    def fake_redis_search(query, top_k=5):
        return [
            {"id": "1", "title": "Test Bug", "description": "desc", "similarity_score": 0.05}
        ]

    svc.redis_vector_service.search_bugs = fake_redis_search

    result = await svc.search_similar_bugs("some query", top_k=5)
    assert result == "no match"


@pytest.mark.asyncio
async def test_ado_wiki_search_returns_no_match_for_low_similarity():
    svc = ADOWikiSearchService()
    svc.local_vector_service.enabled = False

    def fake_redis_search_wiki(query, top_k=5):
        return [
            {"title": "Some Page", "content": "content", "similarity_score": 0.01, "path": "/p"}
        ]

    svc.redis_vector_service.search_wiki_pages = fake_redis_search_wiki

    result = await svc.search_wiki_pages("some wiki query", top_k=5)
    assert result == "no match"


def test_recommendation_agent_respects_no_match_sentinel():
    agent = RecommendationAgent()
    # When similar_bugs is the sentinel and there are no root causes,
    # the agent should return the explicit "no match" sentinel and avoid calling the LLM.
    result = agent._generate_ai_fixes(original_query="q", similar_bugs="no match", root_causes=[])
    assert result == "no match"
