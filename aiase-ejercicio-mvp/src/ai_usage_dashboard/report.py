"""Orchestrates a full scan into a ScanReport (PRD §2, §5).

Pipeline (all in-memory; offline-guarded):
  snapshot sources -> scan transcripts -> apply costs -> aggregate ->
  discover (P1) -> snapshot again -> integrity diff.

Writing the report to disk goes ONLY through Config.assert_write_allowed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from . import aggregate as agg
from . import discovery, scanner, verify
from .config import Config
from .cost_engine import apply_costs
from .models import ScanReport
from .offline import network_disabled
from .pricing import PricingTable


def run_scan(
    config: Config,
    *,
    pricing: Optional[PricingTable] = None,
    generated_at: Optional[str] = None,
    run_discovery: bool = True,
) -> ScanReport:
    pricing = pricing or PricingTable.load()

    integrity_roots = list(config.read_paths) + list(config.codex_paths) + list(
        config.skills_paths
    )

    with network_disabled(config.offline):
        before = verify.snapshot(integrity_roots)

        sessions, warnings, files_failed = scanner.scan(config)
        warnings += apply_costs(sessions, pricing)
        agg_result = agg.aggregate(sessions)
        discovery_result = discovery.discover(config) if run_discovery else {}

        after = verify.snapshot(integrity_roots)
        integrity = verify.diff(before, after)

    report = ScanReport(
        generated_at=generated_at,
        currency=pricing.currency,
        total_calculated_cost=agg_result["total_calculated_cost"],
        sessions_processed=agg_result["sessions_processed"],
        sessions_non_calculable=agg_result["sessions_non_calculable"],
        files_failed=files_failed,
        by_day=agg_result["by_day"],
        by_model=agg_result["by_model"],
        sessions=sessions,
        warnings=warnings,
        discovery=discovery_result,
        integrity=integrity,
        pricing_meta=pricing.meta(),
    )
    return report


def write_report(report: ScanReport, config: Config, filename: str = "report.json") -> Path:
    """Write the JSON report into the allowed output dir only."""
    target = config.assert_write_allowed(Path(filename))
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    return target
