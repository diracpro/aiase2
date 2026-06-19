"""Command-line entry point.

Subcommands:
  scan   Run a read-only scan and write report.json to the allowed output dir.
  serve  Run a scan and serve the dashboard on localhost.

Both are offline by default; pass --allow-network only with explicit intent.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import Config, DEFAULT_OUTPUT_DIR
from .pricing import PricingTable
from .report import run_scan, write_report
from .server import serve as serve_dashboard


def _build_config(args) -> Config:
    kwargs = {}
    if args.read_path:
        kwargs["read_paths"] = [Path(p) for p in args.read_path]
    if args.output_dir:
        kwargs["output_dir"] = Path(args.output_dir)
    kwargs["offline"] = not args.allow_network
    return Config(**kwargs)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _print_summary(report) -> None:
    print(f"  Total calculado:        {report.currency} {report.total_calculated_cost}")
    print(f"  Sesiones procesadas:    {report.sessions_processed}")
    print(f"  No calculables:         {report.sessions_non_calculable}")
    print(f"  Archivos con error:     {report.files_failed}")
    ig = report.integrity
    if ig.get("unchanged"):
        print(f"  Integridad de fuentes:  OK (sin cambios, {ig.get('files_checked')} archivos)")
    else:
        print("  Integridad de fuentes:  ¡CAMBIOS DETECTADOS! (NO-GO técnico)")
    print(f"  Advertencias:           {len(report.warnings)}")


def cmd_scan(args) -> int:
    config = _build_config(args)
    pricing = PricingTable.load(args.pricing_table) if args.pricing_table else PricingTable.load()
    report = run_scan(config, pricing=pricing, generated_at=_now_iso())
    out = write_report(report, config)
    print(f"Reporte escrito en: {out}")
    _print_summary(report)
    if not report.integrity.get("unchanged"):
        return 2  # NO-GO
    return 0


def cmd_serve(args) -> int:
    config = _build_config(args)
    pricing = PricingTable.load(args.pricing_table) if args.pricing_table else PricingTable.load()
    report = run_scan(config, pricing=pricing, generated_at=_now_iso())
    _print_summary(report)
    if args.write:
        out = write_report(report, config)
        print(f"Reporte escrito en: {out}")
    serve_dashboard(report, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-usage-dashboard",
        description="Dashboard local de solo lectura para costos estimados de Claude Code.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--read-path", action="append", help="Ruta de lectura permitida (repetible). Default: ~/.claude")
    common.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Ruta de salida permitida para escritura.")
    common.add_argument("--pricing-table", help="Ruta a una tabla de precios local alternativa.")
    common.add_argument("--allow-network", action="store_true", help="Desactiva el guard offline (requiere intención explícita).")

    s = sub.add_parser("scan", parents=[common], help="Escanea y escribe report.json.")
    s.set_defaults(func=cmd_scan)

    v = sub.add_parser("serve", parents=[common], help="Escanea y sirve el dashboard en localhost.")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8765)
    v.add_argument("--write", action="store_true", help="También escribe report.json en la ruta de salida.")
    v.set_defaults(func=cmd_serve)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (PermissionError, ValueError) as exc:
        print(f"Error de política: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
