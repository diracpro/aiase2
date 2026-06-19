"""Local AI Usage Cost Dashboard (MVP).

A read-only tool that scans local Claude Code transcripts, estimates costs only
when complete data exists, and serves a simple localhost dashboard.

Hard guarantees (see PRD):
- Never writes to source paths (.claude, .codex, Skills, transcripts, config).
- No network access during analysis.
- Costs are estimates from a local, versioned pricing table; never real billing.
"""

__version__ = "0.1.0"
