import pytest

from backend.app.agents.orchestrator_agent import OrchestratorAgent


@pytest.mark.asyncio
async def test_orchestrator_returns_no_results_when_services_no_match(monkeypatch):
    # Patch service search methods to return the explicit sentinel
    async def fake_search_bugs(self, query, top_k=5):
        return "no match"

    async def fake_search_wiki(self, query, top_k=5):
        return "no match"

    # Patch the agent-level execute methods so Orchestrator uses our canned
    # responses without instantiating real service connectors.
    import backend.app.agents.bug_analysis_agent as _bagent
    import backend.app.agents.wiki_knowledge_agent as _wagent
    import backend.app.agents.recommendation_agent as _ragent
    import backend.app.services.ado_bug_search_service as _abss
    import backend.app.services.ado_wiki_search_service as _awss

    # Also stub AzureDevOpsConnector used during service construction
    class _DummyConnector:
        def __init__(self, *a, **k):
            pass

    _abss.AzureDevOpsConnector = _DummyConnector
    _awss.AzureDevOpsConnector = _DummyConnector

    async def fake_bug_execute(self, query, top_k=5):
        return {"agent": self.name, "status": "success", "similar_bugs": [], "root_causes": [], "fixes": [], "bug_count": 0, "no_match": True}

    async def fake_wiki_execute(self, query, top_k=5):
        return {"agent": self.name, "status": "success", "wiki_pages": [], "page_count": 0, "no_match": True}

    async def fake_recommendation(self, bug_analysis, wiki_knowledge, integration_context, original_query):
        return {"agent": self.name, "status": "success", "root_causes": [], "suggested_fixes": [], "confidence_level": 0.0}

    monkeypatch.setattr(_bagent.BugAnalysisAgent, "execute", fake_bug_execute)
    monkeypatch.setattr(_wagent.WikiKnowledgeAgent, "execute", fake_wiki_execute)
    monkeypatch.setattr(_ragent.RecommendationAgent, "execute", fake_recommendation)

    orch = OrchestratorAgent()
    resp = await orch.execute("some issue", user_id="test")

    assert resp.similar_bugs == []
    assert resp.relevant_wiki == []
    assert resp.suggested_fixes == []


@pytest.mark.asyncio
async def test_orchestrator_returns_populated_response_when_services_return_results(monkeypatch):
    # Patch searches to return high-confidence candidates
    async def fake_search_bugs(self, query, top_k=5):
        return [{"id": "1", "title": "Bug A", "description": "a", "similarity_score": 0.85}]

    async def fake_search_wiki(self, query, top_k=5):
        return [{"title": "Page", "content": "helpful", "similarity_score": 0.9, "path": "/p"}]

    # Patch recommendation agent to return deterministic recommendations
    async def fake_recommendation_execute(self, bug_analysis, wiki_knowledge, integration_context, original_query):
        return {
            "agent": self.name,
            "status": "success",
            "root_causes": [{"description": "Cause A", "confidence": 0.8}],
            "suggested_fixes": [{"description": "Fix A", "steps": ["do X"], "priority": "high"}],
            "confidence_level": 0.8,
        }

    import backend.app.agents.bug_analysis_agent as _bagent
    import backend.app.agents.wiki_knowledge_agent as _wagent
    import backend.app.agents.recommendation_agent as _ragent
    import backend.app.services.ado_bug_search_service as _abss
    import backend.app.services.ado_wiki_search_service as _awss

    # Stub AzureDevOpsConnector as above
    class _DummyConnector:
        def __init__(self, *a, **k):
            pass

    _abss.AzureDevOpsConnector = _DummyConnector
    _awss.AzureDevOpsConnector = _DummyConnector

    async def fake_bug_execute_populated(self, query, top_k=5):
        return {"agent": self.name, "status": "success", "similar_bugs": [{"id": "1", "title": "Bug A", "description": "a", "similarity_score": 0.85}], "root_causes": ["Cause A"], "fixes": ["Fix A"], "bug_count": 1}

    async def fake_wiki_execute_populated(self, query, top_k=5):
        return {"agent": self.name, "status": "success", "wiki_pages": [{"title": "Page", "content": "helpful", "similarity_score": 0.9, "path": "/p"}], "page_count": 1}

    monkeypatch.setattr(_bagent.BugAnalysisAgent, "execute", fake_bug_execute_populated)
    monkeypatch.setattr(_wagent.WikiKnowledgeAgent, "execute", fake_wiki_execute_populated)
    monkeypatch.setattr(_ragent.RecommendationAgent, "execute", fake_recommendation_execute)

    orch = OrchestratorAgent()
    resp = await orch.execute("some issue", user_id="test")

    assert len(resp.similar_bugs) == 1
    assert len(resp.relevant_wiki) == 1
    assert len(resp.suggested_fixes) == 1
    assert resp.root_causes and resp.root_causes[0].description == "Cause A"
