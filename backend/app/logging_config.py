"""Local, persistent logging for on-prem deployments."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_configured_components: dict[
    str, tuple[logging.Logger, TextIO, TextIO, _LogStream, _LogStream]
] = {}


class _JsonFormatter(logging.Formatter):
    def __init__(self, component: str) -> None:
        super().__init__()
        self.component = component

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "component": self.component,
            "request_id": request_id_context.get(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        for key in (
            "http_method",
            "http_path",
            "http_status_code",
            "duration_ms",
            "event_name",
            "event_status",
            "provider",
            "model",
            "error_type",
            "fix_count",
            "similar_bug_count",
        ):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        return json.dumps(entry, ensure_ascii=False)


class _LogStream:
    """Send existing print output through the configured logger."""

    encoding = "utf-8"

    def __init__(self, logger: logging.Logger, level: int, stream: TextIO) -> None:
        self._logger = logger
        self._level = level
        self._stream = stream
        self._buffers = threading.local()

    def write(self, value: str) -> int:
        if not isinstance(value, str):
            value = str(value)
        written = self._stream.write(value)
        buffer = getattr(self._buffers, "value", "") + value
        lines = buffer.split("\n")
        self._buffers.value = lines.pop()
        for line in lines:
            line = line.rstrip("\r")
            if line:
                self._logger.log(self._level, line)
        return written

    def flush(self) -> None:
        self._stream.flush()
        buffer = getattr(self._buffers, "value", "").rstrip("\r")
        self._buffers.value = ""
        if buffer:
            self._logger.log(self._level, buffer)

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


def _get_log_directory() -> Path:
    configured = os.getenv("ERRORLENS_LOG_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        return Path(os.getenv("PROGRAMDATA", r"C:\ProgramData")) / "ErrorLens" / "logs"
    return Path("/var/log/errorlens")


def configure_local_logging(component: str) -> Path:
    """Persist this process's console output and logs with bounded rotation."""
    if component in _configured_components:
        return _get_log_directory()

    log_directory = _get_log_directory()
    log_directory.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("errorlens")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = _JsonFormatter(component)
    log_path = log_directory / f"{component}-{os.getpid()}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=int(os.getenv("ERRORLENS_LOG_MAX_BYTES", str(10 * 1024 * 1024))),
        backupCount=int(os.getenv("ERRORLENS_LOG_BACKUP_COUNT", "10")),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    original_stdout, original_stderr = sys.stdout, sys.stderr
    stdout_wrapper = _LogStream(logger, logging.INFO, original_stdout)
    stderr_wrapper = _LogStream(logger, logging.ERROR, original_stderr)
    _configured_components[component] = (
        logger,
        original_stdout,
        original_stderr,
        stdout_wrapper,
        stderr_wrapper,
    )
    sys.stdout = stdout_wrapper
    sys.stderr = stderr_wrapper
    return log_path


def shutdown_local_logging(component: str) -> None:
    configured = _configured_components.pop(component, None)
    if configured is None:
        return

    logger, original_stdout, original_stderr, stdout_wrapper, stderr_wrapper = configured
    stdout_wrapper.flush()
    stderr_wrapper.flush()
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)