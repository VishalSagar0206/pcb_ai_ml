"""Logging configuration (Phase 28: LOG_LEVEL)."""
from __future__ import annotations

import logging

from pcb_ai.config import Settings, get_settings

_configured = False


def configure_logging(settings: Settings | None = None) -> None:
    global _configured
    if _configured:
        return
    settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _configured = True
