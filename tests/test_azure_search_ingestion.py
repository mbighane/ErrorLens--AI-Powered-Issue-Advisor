import re
from unittest.mock import MagicMock, patch

from backend.app.config import settings
from backend.app.services.local_vector_search_service import LocalVectorSearchService
from scripts import ingest_bugs, ingest_wiki


def test_bug_search_id_is_safe_for_azure_ai_search():
    value = ingest_bugs._safe_azure_search_id("ErrorLensProject.wiki")
    assert re.fullmatch(r"[A-Za-z0-9_-]+", value)
    assert "ErrorLensProject" in value
    assert value != "ErrorLensProject.wiki"


def test_wiki_search_id_is_safe_for_azure_ai_search():
    value = ingest_wiki._safe_azure_search_id("Lessons learned")
    assert re.fullmatch(r"[A-Za-z0-9_-]+", value)
    assert "Lessons" in value
    assert "learned" in value
    assert value != "Lessons learned"


def test_local_vector_search_falls_back_to_openai_when_azure_deployment_is_missing():
    original_azure = settings.use_azure_openai
    original_openai_key = settings.openai_api_key
    settings.use_azure_openai = True
    settings.openai_api_key = "test-openai-key"

    try:
        azure_client = MagicMock()
        azure_client.embeddings.create.side_effect = Exception("404 Resource not found")

        openai_client = MagicMock()

        with patch("backend.app.services.local_vector_search_service.AzureOpenAI", return_value=azure_client), \
             patch("backend.app.services.local_vector_search_service.OpenAI", return_value=openai_client):
            service = LocalVectorSearchService()
            assert service.enabled is True
            assert service._client is openai_client
    finally:
        settings.use_azure_openai = original_azure
        settings.openai_api_key = original_openai_key
