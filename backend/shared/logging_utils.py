"""
Logging utilities for the agents platform.

Wraps structlog so every module gets a contextual logger and stops using
naked `print()` calls that bypass log routing and dump full payloads.
"""

from typing import Any, Mapping

import structlog


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger with `module` context."""
    log = structlog.get_logger()
    if name:
        log = log.bind(module=name)
    return log


def safe_preview(value: Any, max_chars: int = 200) -> str:
    """Render `value` for logging without dumping full bodies."""
    text = value if isinstance(value, str) else repr(value)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}...<truncated {len(text) - max_chars} chars>"


_REDACT_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "supabase_key",
    "google_api_key",
    "smtp_password",
    "password",
    "token",
    "secret",
}


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of `data` with sensitive keys masked."""
    out: dict[str, Any] = {}
    for key, val in data.items():
        if key.lower() in _REDACT_KEYS:
            out[key] = "***"
        elif isinstance(val, Mapping):
            out[key] = redact_mapping(val)
        else:
            out[key] = val
    return out
