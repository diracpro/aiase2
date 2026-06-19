# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project layout

The actual application lives in `aiase-ejercicio-mvp/` (a Python package, `ai_usage_dashboard`). The repo root is a [Spec Kit](https://github.com/github/spec-kit) workspace: `.specify/` holds templates, scripts, and the constitution; `.claude/skills/speckit-*` are the spec-driven workflow commands (specify → plan → tasks → implement). The `<!-- SPECKIT ... -->` block at the bottom of this file is managed by the `speckit-agent-context-update` skill — don't hand-edit it.

## Commands

All commands run from `aiase-ejercicio-mvp/`. There are **no third-party dependencies** — Python ≥ 3.10 stdlib only. A `.venv/` exists with the package installed editable.

```bash
# Run tests (unittest, not pytest)
python3 -m unittest discover -s tests -v

# Run a single test module / case
python3 -m unittest tests.test_dashboard -v
python3 -m unittest tests.test_dashboard.TestClassName.test_method -v

# Run the CLI without installing
PYTHONPATH=src python3 -m ai_usage_dashboard.cli scan
PYTHONPATH=src python3 -m ai_usage_dashboard.cli serve

# Or install the console script
pip install -e .
ai-usage-dashboard scan          # writes report.json to /tmp/ai-usage-dashboard
ai-usage-dashboard serve         # dashboard on http://127.0.0.1:8765
```

CLI exit codes are contractual: `0` OK, `1` policy error (write outside allowed path / network use), `2` technical NO-GO (source files changed during the scan).

## Architecture

The tool is a **local, read-only, offline** estimator of Claude Code usage cost from JSONL transcripts in `~/.claude`. The whole design is built around hard safety guarantees, so changes must respect these invariants rather than work around them:

- **Write policy is centralized in `config.py`.** `Config.assert_write_allowed(target)` is the single guard every writer must call; it rejects anything outside `output_dir` or inside a protected source root (`~/.claude`, `~/.codex`, `~/.config/{claude,codex}`, skills). The only writable location is `output_dir` (default `/tmp/ai-usage-dashboard`). Never bypass this guard to write files.
- **Offline is enforced, not assumed.** `offline.network_disabled()` monkeypatches `socket.socket`/`getaddrinfo` to raise during analysis. The whole scan in `report.run_scan` runs inside this context manager. The localhost `serve` step runs *outside* the guard (loopback is intentional and separate from analysis).
- **Source integrity = NO-GO gate.** `verify.snapshot()` hashes (size + mtime_ns + sha256) every source file before and after the scan; `verify.diff()` reports `unchanged`. If sources changed mid-scan, the run is a NO-GO (exit 2). This is why scanning while Claude Code is actively writing fails — expected behavior.
- **No fake costs.** Tokens and costs are `Optional` by construction (`models.py`). `cost_engine.compute_cost` marks a `CostResult` as `CALCULATED` only when model + input_tokens + output_tokens + a configured price all exist; otherwise it returns an explicit non-calculable `CostStatus` (`UNKNOWN_MODEL`, `PRICE_NOT_CONFIGURED`, `TOKENS_MISSING`) with **no** cost numbers. Never infer tokens from text.

### Module pipeline (`report.run_scan`)

`scanner.scan` (read transcripts, resilient per-file — one bad file never aborts the run, it yields a `Warning` and continues) → `cost_engine.apply_costs` → `aggregate.aggregate` (per-day / per-model, **excludes** non-calculable sessions) → `discovery.discover` (P1: informational detection of Codex & Skills, no costing) → `verify` integrity diff. The result is an in-memory `ScanReport` (`models.py`), serialized to JSON only via `write_report`.

`server.py` serves the static `web/` UI plus the report at `/api/report`, bound to loopback. `pricing.py` loads the local, versioned `pricing/pricing_table.json` (each model carries `provider`, prices, `source`, `consulted_at`); stale/missing prices emit warnings — there is **no** automatic price update over the network.

### Conventions

- User-facing strings, warnings, and `CostStatus`/`WarningType` enum *values* are in **Spanish**; code identifiers and docstrings are English. Match this when adding messages.
- Cache token fields are intentionally **not** summed (cache billing is out of scope).
- Tests use fixtures under `tests/fixtures/sources/.claude/projects/demo/` covering valid/corrupt/no-tokens/no-model/unknown-price transcripts, plus the ≥95% processed-transcripts KPI and the immutability/offline/write-policy guarantees.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
