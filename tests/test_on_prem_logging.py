import json

from backend.app.config import settings
from backend.app.logging_config import configure_local_logging, shutdown_local_logging
from backend.app.services.azure_ai_monitoring import AzureAIMonitoring


def test_print_output_is_persisted_as_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ERRORLENS_LOG_DIR", str(tmp_path))
    log_path = configure_local_logging("backend")
    try:
        print("persistent on-prem log")
    finally:
        shutdown_local_logging("backend")

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["message"] == "persistent on-prem log"
    assert record["component"] == "backend"
    assert "persistent on-prem log" in capsys.readouterr().out


def test_application_insights_is_disabled_on_prem(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "on_prem")
    monkeypatch.setattr(settings, "azure_monitor_connection_string", "configured")
    monkeypatch.setattr(settings, "azure_monitor_tracing_enabled", True)

    monitoring = AzureAIMonitoring()

    assert monitoring.enabled is False