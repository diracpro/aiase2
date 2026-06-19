<!--
SYNC IMPACT REPORT
==================
Version change: [TEMPLATE/unversioned] → 1.0.0
Bump rationale: First concrete ratification. Template placeholders replaced with
  project-specific principles derived from the documented design guarantees
  ("Garantías de diseño") and the safety invariants enforced in code. MAJOR
  establishes the initial governance baseline at 1.0.0.

Principles defined (all new):
  I.   Read-Only Sobre Fuentes (Source Immutability)
  II.  Análisis Sin Red (Verifiable Offline Analysis)
  III. Sin Costos Falsos (No Fabricated Costs)
  IV.  Integridad Verificable (Verifiable Integrity / NO-GO Gate)
  V.   Simplicidad y Transparencia (Simplicity & Transparency)

Added sections:
  - Additional Constraints (scope boundaries / non-goals)
  - Development Workflow & Quality Gates
  - Governance

Removed sections: none (template scaffolding replaced in place)

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — "Constitution Check" gate defers
     dynamically to this file; no hardcoded principles to reconcile. Aligned.
  ✅ .specify/templates/spec-template.md — no constitution-mandated sections to
     add/remove. Aligned.
  ✅ .specify/templates/tasks-template.md — task categories remain valid; the
     principle-driven gates below map onto existing Polish/Foundational phases.
     Aligned.
  ✅ README.md (aiase-ejercicio-mvp/) — already the source of these guarantees;
     no change required.

Follow-up TODOs: none. RATIFICATION_DATE set to first adoption date.
-->

# AI Usage Dashboard Constitution

## Core Principles

### I. Read-Only Sobre Fuentes (Source Immutability)

The tool MUST NEVER write to, modify, or delete any source path it reads —
including `~/.claude`, `~/.codex`, `~/.config/{claude,codex}`, Skills, transcripts,
or configuration. The ONLY writable location is the configured output directory
(default `/tmp/ai-usage-dashboard`), which MUST resolve outside every protected
source root.

Every disk write MUST pass through the single centralized guard
`Config.assert_write_allowed()`. No code path may open a file for writing, create
directories, or persist data without first clearing that guard. A write attempt
outside the allowed output directory is a policy violation and MUST exit with
code `1`.

**Rationale**: The user's local AI history is irreplaceable and sensitive.
Centralizing the write decision in one auditable guard makes "we never touch your
data" a verifiable property rather than a promise scattered across modules.

### II. Análisis Sin Red (Verifiable Offline Analysis)

The analysis phase MUST run with the network disabled and MUST enforce this
technically — not by convention. Outbound socket connections and DNS resolution
are blocked during the scan (`offline.network_disabled`), so any accidental
network use raises rather than silently succeeding. Default operation is offline;
`--allow-network` requires explicit user intent and MUST remain off by default.

The localhost dashboard server (`serve`) is a separate, post-analysis step bound
to loopback only; it is NOT part of the guarded analysis phase. The pricing table
MUST be local and versioned — prices are NEVER fetched or auto-updated over the
network.

**Rationale**: "Zero network calls during analysis" must be a testable guarantee.
Enforcing it at the socket layer turns a privacy claim into an invariant the test
suite can prove.

### III. Sin Costos Falsos (No Fabricated Costs)

A cost MUST be reported as `CALCULATED` only when ALL of the following hold: the
model is recognized in the local pricing table, a configured price exists, and
both input and output token counts are present. In every other case the result
MUST carry an explicit non-calculable status (`UNKNOWN_MODEL`,
`PRICE_NOT_CONFIGURED`, `TOKENS_MISSING`) and MUST contain NO cost numbers.

The system MUST NEVER infer tokens from text, MUST NEVER substitute placeholder
or estimated cost values for missing data, and MUST exclude non-calculable
sessions from day/model aggregates (reporting them separately). All cost output
MUST carry the disclaimer that figures are estimates from locally configured
public API rates and do not represent real billing. Cache-billing token fields
MUST NOT be summed into cost.

**Rationale**: A dashboard that invents numbers is worse than one that admits gaps.
Explicit, exhaustive cost states preserve user trust and make the data honest.

### IV. Integridad Verificable (Verifiable Integrity / NO-GO Gate)

The tool MUST snapshot every source file (size, `mtime_ns`, `sha256`) before and
after each scan and diff the two. If anything changed during the scan, the run is
a technical NO-GO and MUST exit with code `2`. This gate is non-negotiable and
MUST NOT be silently downgraded to a warning.

Scanning MUST be resilient per file: a single unreadable or corrupt transcript
MUST yield a counted `Warning` and allow processing to continue — one bad file
MUST NEVER abort the run. The tool MUST process at least 95% of discovered
transcripts.

**Rationale**: Read-only safety is only credible if it can be proven after the
fact. The before/after hash gate detects any unexpected mutation (including the
tool's own), and resilient scanning keeps a partial dataset useful rather than
fatal.

### V. Simplicidad y Transparencia (Simplicity & Transparency)

The application MUST depend only on the Python (>= 3.10) standard library; adding
a third-party runtime dependency requires explicit justification recorded against
this constitution. Behavior MUST be transparent and inspectable: contractual exit
codes (`0` OK, `1` policy error, `2` integrity NO-GO) MUST be honored; logs go to
stdout/stderr only, with no persistent logs unless explicitly enabled (and then
only into the allowed output directory).

The local pricing table MUST record provenance for every model (`provider`,
prices, `source`, `consulted_at`); stale or missing prices MUST emit a warning
rather than be silently trusted. New user-facing strings and status/warning enum
values follow the existing Spanish convention; code identifiers and docstrings
remain in English.

**Rationale**: A small, dependency-free, observable tool is auditable by a single
reader. Transparency about prices and exit semantics keeps the estimate trustworthy
and the tool scriptable.

## Additional Constraints

The following are explicit non-goals for the MVP and MUST NOT be introduced
without a constitutional amendment:

- Representing real billing, plans, subscriptions, discounts, or cache billing.
- Estimating tokens from transcript text when usage data is absent.
- Cost calculation for Codex or Skills (P1 discovery is informational only).
- Multi-user operation, network-backed storage, or cloud sync.

Pricing data is governed: it is local, versioned, and never auto-updated. Mixing
public API rates with real plan/subscription billing is prohibited.

## Development Workflow & Quality Gates

- **Constitution Check**: The `plan` workflow MUST verify the design against
  Principles I–V before Phase 0 and again after Phase 1. Any violation MUST be
  recorded in the plan's Complexity Tracking with justification, or the design
  MUST be revised.
- **Guard discipline**: Code review MUST confirm that every new write path calls
  `Config.assert_write_allowed()` and that analysis-phase code runs inside the
  offline guard. A change that weakens a safety invariant requires an amendment.
- **Tests as evidence**: Changes touching scanning, costing, integrity, write
  policy, or the offline guard MUST keep the corresponding guarantees covered by
  `python3 -m unittest discover -s tests`. The ≥95% processed-transcripts KPI and
  the immutability/offline/write-policy checks MUST remain green.
- **Exit-code contract**: Changes MUST preserve the `0/1/2` exit-code semantics.

## Governance

This constitution supersedes ad-hoc practice for the AI Usage Dashboard. When
guidance conflicts, the constitution wins.

- **Amendments**: Proposed in writing, with rationale and (when an invariant is
  relaxed) a migration/justification note. Amendments take effect when merged
  into this file with an updated version and date.
- **Versioning**: Semantic versioning. MAJOR for backward-incompatible governance
  or principle removal/redefinition; MINOR for a new principle/section or
  materially expanded guidance; PATCH for clarifications and non-semantic edits.
- **Compliance review**: Every plan and PR is expected to verify compliance with
  the principles above. Unjustified complexity or weakened safety invariants MUST
  be rejected. Runtime development guidance lives in `CLAUDE.md` and the package
  `README.md`; both MUST stay consistent with this document.

**Version**: 1.0.0 | **Ratified**: 2026-06-19 | **Last Amended**: 2026-06-19
