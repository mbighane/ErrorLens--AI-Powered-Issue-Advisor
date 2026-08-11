import pytest

# Stub external connectors used elsewhere so importing app doesn't trigger
# unexpected network calls during test collection or startup.
try:
    import backend.app.services.ado_bug_search_service as _abss
    import backend.app.services.ado_wiki_search_service as _awss
    class _DummyConnector:
        def __init__(self, *a, **k):
            pass
    _abss.AzureDevOpsConnector = _DummyConnector
    _awss.AzureDevOpsConnector = _DummyConnector
except Exception:
    # If modules aren't importable here, tests below don't depend on them.
    pass

from backend.app.main import root, health_check


@pytest.mark.asyncio
async def test_root():
    response = await root()
    assert response == {"message": "ErrorLens API"}


@pytest.mark.asyncio
async def test_health():
    response = await health_check()
    assert response == {"status": "healthy"}