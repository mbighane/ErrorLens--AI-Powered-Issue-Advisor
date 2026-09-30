import re

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
