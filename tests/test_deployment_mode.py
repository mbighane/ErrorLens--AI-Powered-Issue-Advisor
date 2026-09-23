import os


def test_on_prem_mode_disables_azure_and_enables_ollama(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "on_prem")
    monkeypatch.setenv("AZURE_SEARCH_API_KEY", "")
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "")

    import importlib
    import backend.app.config as config_module
    importlib.reload(config_module)

    settings = config_module.settings
    assert settings.deployment_mode == "on_prem"
    assert settings.use_azure_openai is False
    assert settings.azure_search_enabled is False
    assert settings.ollama_enabled is True
    assert settings.should_use_local_only is True
