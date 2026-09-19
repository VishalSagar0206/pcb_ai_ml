"""KiCad DRC invocation (Phase 2).

Prefers `kicad-cli pcb drc` (KiCad 7+) as the deterministic source of
truth. If `kicad-cli` is unavailable in the current environment, this
module never fabricates a DRC result -- it returns a `DRCRunResult` with
`executed=False` and a clear `error`, OR (only when the caller explicitly
opts in via `load_fixture_drc_report`) loads a pre-recorded fixture report
that is unambiguously marked `fixture_used=True`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from pcb_ai.config import Settings, get_settings
from pcb_ai.drc.normalizer import normalize_drc_report
from pcb_ai.schemas.drc import DRCRunResult
from pcb_ai.schemas.pcb import PCBDesign


class KiCadUnavailableError(Exception):
    """Raised (only where the caller requests strict mode) when kicad-cli
    cannot be located and no fixture fallback is permitted."""


def find_kicad_cli(settings: Optional[Settings] = None) -> Optional[str]:
    settings = settings or get_settings()
    configured = settings.kicad_cli_path
    if configured and Path(configured).exists():
        return configured
    resolved = shutil.which(configured or "kicad-cli")
    return resolved


def run_kicad_drc(
    pcb_path: Union[str, Path],
    pcb_design: PCBDesign,
    settings: Optional[Settings] = None,
    strict: bool = False,
) -> DRCRunResult:
    """Run KiCad's deterministic DRC engine against `pcb_path`.

    If kicad-cli is not available:
      - strict=True  -> raises KiCadUnavailableError
      - strict=False -> returns DRCRunResult(executed=False, error=...)

    This function NEVER invents violations. Use `load_fixture_drc_report`
    for offline/deterministic testing instead.
    """
    settings = settings or get_settings()
    pcb_path = Path(pcb_path)
    board_id = pcb_design.board.board_id

    cli = find_kicad_cli(settings)
    if cli is None:
        message = (
            "kicad-cli was not found (checked KICAD_CLI_PATH and PATH). "
            "Live KiCad DRC execution is unavailable in this environment. "
            "Install KiCad 7+ and set KICAD_CLI_PATH, or use "
            "load_fixture_drc_report() for offline/deterministic testing."
        )
        if strict:
            raise KiCadUnavailableError(message)
        return DRCRunResult(board_id=board_id, executed=False, error=message)

    with tempfile.TemporaryDirectory() as tmp_dir:
        report_path = Path(tmp_dir) / "drc_report.json"
        cmd = [
            cli,
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--output",
            str(report_path),
            str(pcb_path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.kicad_drc_timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return DRCRunResult(
                board_id=board_id,
                executed=False,
                error=f"kicad-cli DRC timed out after {settings.kicad_drc_timeout_s}s: {exc}",
            )
        except OSError as exc:
            return DRCRunResult(
                board_id=board_id,
                executed=False,
                error=f"Failed to invoke kicad-cli: {exc}",
            )

        raw_report = None
        if report_path.exists():
            try:
                raw_report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return DRCRunResult(
                    board_id=board_id,
                    executed=True,
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    error=f"kicad-cli produced non-JSON DRC report: {exc}",
                )

        if raw_report is None:
            return DRCRunResult(
                board_id=board_id,
                executed=True,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                error="kicad-cli did not produce a DRC report file.",
            )

        violations = normalize_drc_report(raw_report, pcb_design)
        return DRCRunResult(
            board_id=board_id,
            kicad_version=raw_report.get("kicad_version"),
            executed=True,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            raw_report_path=str(report_path),
            raw_report=raw_report,
            violations=violations,
            unconnected_count=len(raw_report.get("unconnected_items", []) or []),
        )


def load_fixture_drc_report(
    fixture_path: Union[str, Path],
    pcb_design: PCBDesign,
) -> DRCRunResult:
    """Load a pre-recorded, real-schema-shaped KiCad DRC JSON report from
    disk for offline/deterministic testing when kicad-cli is unavailable.

    The returned result is explicitly marked `fixture_used=True` and
    `executed=False` so downstream consumers (reports, evaluation) never
    confuse it with a live KiCad invocation.
    """
    fixture_path = Path(fixture_path)
    raw_report = json.loads(fixture_path.read_text(encoding="utf-8"))
    violations = normalize_drc_report(raw_report, pcb_design)
    return DRCRunResult(
        board_id=pcb_design.board.board_id,
        kicad_version=raw_report.get("kicad_version"),
        executed=False,
        raw_report_path=str(fixture_path),
        raw_report=raw_report,
        violations=violations,
        unconnected_count=len(raw_report.get("unconnected_items", []) or []),
        fixture_used=True,
    )
