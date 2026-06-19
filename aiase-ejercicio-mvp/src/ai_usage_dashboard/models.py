"""In-memory data model produced by the scanner and consumed by the cost engine
and the dashboard UI.

Design rule (PRD §1, §4): tokens and costs are OPTIONAL by construction. A
session without tokens must be representable WITHOUT any fake cost values, and a
cost result must always carry an explicit status.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class CostStatus(str, Enum):
    """Exhaustive, explicit states a cost computation can land in."""

    CALCULATED = "calculado"
    PRICE_NOT_CONFIGURED = "precio_no_configurado"
    TOKENS_MISSING = "tokens_faltantes"
    UNKNOWN_MODEL = "modelo_desconocido"


class WarningType(str, Enum):
    FILE_UNREADABLE = "archivo_ilegible"
    FILE_CORRUPT = "archivo_corrupto"
    UNKNOWN_FORMAT = "formato_desconocido"
    PRICE_STALE = "precio_vencido"
    PRICE_MISSING = "precio_no_configurado"
    UNKNOWN_MODEL = "modelo_desconocido"
    TOKENS_MISSING = "tokens_faltantes"


@dataclass
class Warning:
    type: WarningType
    message: str
    source: Optional[str] = None  # file path or model name, never file contents

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


@dataclass
class CostResult:
    status: CostStatus
    input_cost: Optional[float] = None
    output_cost: Optional[float] = None
    total_cost: Optional[float] = None
    currency: str = "USD"

    @property
    def is_calculable(self) -> bool:
        return self.status == CostStatus.CALCULATED

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class Session:
    """One detected Claude Code session.

    `input_tokens` / `output_tokens` are None when the transcript does not record
    them. We never infer tokens from text (PRD non-goal).
    """

    session_id: str
    source_file: str
    started_at: Optional[str] = None      # ISO 8601 string, local-agnostic
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    message_count: int = 0
    summary: str = ""
    cost: Optional[CostResult] = None
    warnings: list[Warning] = field(default_factory=list)

    @property
    def day(self) -> Optional[str]:
        if not self.started_at:
            return None
        return self.started_at[:10]  # YYYY-MM-DD

    @property
    def has_tokens(self) -> bool:
        return self.input_tokens is not None and self.output_tokens is not None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "source_file": self.source_file,
            "started_at": self.started_at,
            "day": self.day,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "message_count": self.message_count,
            "summary": self.summary,
            "cost": self.cost.to_dict() if self.cost else None,
            "warnings": [w.to_dict() for w in self.warnings],
        }


@dataclass
class DayAggregate:
    day: str
    total_cost: float = 0.0
    calculable_sessions: int = 0
    non_calculable_sessions: int = 0


@dataclass
class ModelAggregate:
    model: str
    total_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    calculable_sessions: int = 0
    non_calculable_sessions: int = 0


@dataclass
class ScanReport:
    """Top-level in-memory result. Serialized to JSON only into the allowed
    output path, never into a source path."""

    generated_at: Optional[str] = None
    currency: str = "USD"
    total_calculated_cost: float = 0.0
    sessions_processed: int = 0
    sessions_non_calculable: int = 0
    files_failed: int = 0
    by_day: list[DayAggregate] = field(default_factory=list)
    by_model: list[ModelAggregate] = field(default_factory=list)
    sessions: list[Session] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
    discovery: dict = field(default_factory=dict)
    integrity: dict = field(default_factory=dict)
    pricing_meta: dict = field(default_factory=dict)
    disclaimer: str = (
        "Estos costos son estimaciones con tarifas API públicas configuradas "
        "localmente; no representan facturación real."
    )

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "currency": self.currency,
            "total_calculated_cost": round(self.total_calculated_cost, 6),
            "sessions_processed": self.sessions_processed,
            "sessions_non_calculable": self.sessions_non_calculable,
            "files_failed": self.files_failed,
            "by_day": [asdict(d) for d in self.by_day],
            "by_model": [asdict(m) for m in self.by_model],
            "sessions": [s.to_dict() for s in self.sessions],
            "warnings": [w.to_dict() for w in self.warnings],
            "discovery": self.discovery,
            "integrity": self.integrity,
            "pricing_meta": self.pricing_meta,
            "disclaimer": self.disclaimer,
        }
