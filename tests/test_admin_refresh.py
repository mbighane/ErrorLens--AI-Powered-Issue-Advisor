import asyncio

import pytest

import backend.app.api.admin as admin


@pytest.mark.asyncio
async def test_refresh_index_updates_azure_search_incrementally(monkeypatch):
    calls = []

    class DummyLoop:
        async def run_in_executor(self, executor, func):
            return func()

    def fake_subprocess_run(cmd, capture_output, text, encoding, cwd, env):
        calls.append(cmd[1])
        return type("Result", (), {"returncode": 0, "stderr": "", "stdout": ""})()

    monkeypatch.setattr(admin, "settings", type("Settings", (), {"azure_search_enabled": True, "vector_index_dir": "data/vector_index"})())
    monkeypatch.setattr(admin, "PROJECT_ROOT", admin.PROJECT_ROOT)
    monkeypatch.setattr(admin.asyncio, "get_event_loop", lambda: DummyLoop())
    monkeypatch.setattr(admin.subprocess, "run", fake_subprocess_run)

    result = await admin.refresh_index()

    assert result.success is True
    assert "scripts/ingest_bugs.py" in calls
    assert "scripts/ingest_wiki.py" in calls
    assert "scripts/create_azure_search_index.py" not in calls
