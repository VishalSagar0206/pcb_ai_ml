"""Analysis trace recording (Phase 23).

Every violation analysis produces an `AnalysisTrace` (tools called,
retrieved PCB objects/documents, model, prompt version, token usage,
latency). `record_trace` always logs it as structured JSON for
reproducibility; if Langfuse is enabled and installed, it is also
forwarded there as a best-effort, non-fatal integration.
"""
from __future__ import annotations

import logging

from pcb_ai.config import Settings, get_settings
from pcb_ai.schemas.context import AnalysisTrace

logger = logging.getLogger("pcb_ai.trace")

_langfuse_client = None
_langfuse_init_attempted = False


def _get_langfuse_client(settings: Settings):
    global _langfuse_client, _langfuse_init_attempted
    if _langfuse_init_attempted:
        return _langfuse_client
    _langfuse_init_attempted = True
    if not settings.caf_langfuse_enabled:
        return None
    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]

        _langfuse_client = Langfuse(
            host=settings.caf_langfuse_host,
            public_key=settings.caf_langfuse_public_key,
            secret_key=settings.caf_langfuse_secret_key,
        )
    except Exception:  # noqa: BLE001 - observability must never break the pipeline
        logger.warning("CAF_LANGFUSE_ENABLED is set but the langfuse package is unavailable/misconfigured; skipping.")
        _langfuse_client = None
    return _langfuse_client


def record_trace(trace: AnalysisTrace, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    logger.info("analysis_trace %s", trace.model_dump_json())

    client = _get_langfuse_client(settings)
    if client is None:
        return
    try:
        client.trace(
            name="pcb_violation_diagnosis",
            id=f"{trace.analysis_id}:{trace.violation_id}",
            metadata=trace.model_dump(mode="json"),
        )
    except Exception:  # noqa: BLE001 - never let telemetry break the pipeline
        logger.debug("Failed to forward trace to Langfuse", exc_info=True)
