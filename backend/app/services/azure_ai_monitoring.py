from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..config import settings

try:
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry import trace
except Exception:  # pragma: no cover - optional dependency path
    configure_azure_monitor = None
    trace = None


class AzureAIMonitoring:
    """Azure Monitor / Application Insights tracing wrapper for app-level telemetry."""

    def __init__(self) -> None:
        self.enabled = (
            not settings.is_on_prem_deployment
            and bool(settings.azure_monitor_connection_string)
            and settings.azure_monitor_tracing_enabled
        )
        self.trace_name = settings.azure_monitor_trace_name
        self._tracer = None
        self.init_error: Optional[str] = None

        if self.enabled and configure_azure_monitor and trace is not None:
            try:
                configure_azure_monitor(connection_string=settings.azure_monitor_connection_string)
                self._tracer = trace.get_tracer(__name__)
            except Exception as exc:  # pragma: no cover - runtime only
                self.enabled = False
                self.init_error = str(exc)

    def trace_event(self, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Emit a real Azure Monitor span when tracing is configured; otherwise return local payload."""
        if settings.is_on_prem_deployment:
            logging.getLogger("errorlens.telemetry").info(
                "Local AI telemetry event",
                extra={
                    "event_name": event_name,
                    "event_status": payload.get("status"),
                    "provider": payload.get("provider"),
                    "model": payload.get("model"),
                    "fix_count": payload.get("fix_count"),
                    "similar_bug_count": payload.get("similar_bug_count"),
                },
            )
            return {"event": event_name, "enabled": False, "payload": payload}

        if not self.enabled or self._tracer is None:
            return {"event": event_name, "enabled": False, "payload": payload}

        try:
            with self._tracer.start_as_current_span(f"{self.trace_name}.{event_name}") as span:
                for key, value in payload.items():
                    if value is None:
                        continue
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(key, value)
                    else:
                        span.set_attribute(key, str(value)[:1024])
                span.set_attribute("ai.service", "errorlens")
                span.set_attribute("ai.model", settings.azure_openai_chat_deployment or settings.ollama_chat_model)
                return {
                    "event": event_name,
                    "enabled": True,
                    "trace_name": self.trace_name,
                    "payload": payload,
                }
        except Exception:  # fall back to local payload only if telemetry fails
            return {"event": event_name, "enabled": False, "payload": payload}

    @staticmethod
    def log(event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience wrapper used by AI call sites for structured tracing."""
        return AzureAIMonitoring().trace_event(event_name, payload)
