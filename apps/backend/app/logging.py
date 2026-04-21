"""Redacting logger formatter. See CLAUDE.md §11 and §14.

API keys, ticker positions, and portfolio values must never hit INFO logs.
This formatter is load-bearing — do not bypass it.
"""
from __future__ import annotations

import logging
import re
from typing import Final

from app.config import settings

# Redact anything that looks like an Anthropic key.
_API_KEY_RE: Final = re.compile(r"sk-[A-Za-z0-9_\-]{10,}")
# Redact obvious position/value mentions: "qty=1234", "avg_price=45.6", etc.
_POSITION_RE: Final = re.compile(
    r"\b(qty|quantity|avg_price|price|position|value|pnl|balance)\s*[=:]\s*[-0-9.]+",
    re.IGNORECASE,
)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        msg = super().format(record)
        msg = _API_KEY_RE.sub("sk-***REDACTED***", msg)
        return _POSITION_RE.sub(lambda m: f"{m.group(1)}=***", msg)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
