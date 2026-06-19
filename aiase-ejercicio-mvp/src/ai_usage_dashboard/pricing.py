"""Pricing table governance (PRD §6).

Loads a LOCAL, versioned pricing table. Never fetches over the network.
- Unknown model -> price_not_configured.
- Missing/stale consulted_at date -> warning (but price still usable).
- Only raw API rates; no plans/subscriptions/discounts/cache billing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .models import Warning, WarningType

DEFAULT_TABLE = Path(__file__).parent / "pricing" / "pricing_table.json"


@dataclass
class ModelPrice:
    provider: str
    model: str
    input_price: float   # price per unit
    output_price: float
    unit: str            # e.g. "per_mtok"
    source: str
    consulted_at: Optional[str]

    def _per_token(self, price: float) -> float:
        if self.unit == "per_mtok":
            return price / 1_000_000
        if self.unit == "per_ktok":
            return price / 1_000
        if self.unit == "per_token":
            return price
        raise ValueError(f"Unidad de precio desconocida: {self.unit}")

    def cost_for(self, input_tokens: int, output_tokens: int) -> tuple[float, float]:
        return (
            input_tokens * self._per_token(self.input_price),
            output_tokens * self._per_token(self.output_price),
        )


class PricingTable:
    def __init__(self, raw: dict, *, today: Optional[str] = None):
        self.schema_version = raw.get("schema_version", 1)
        self.currency = raw.get("currency", "USD")
        self.stale_after_days = raw.get("default_stale_after_days", 120)
        self._today = today  # injectable for deterministic tests/offline runs
        self._by_key: dict[str, ModelPrice] = {}
        for entry in raw.get("models", []):
            mp = ModelPrice(
                provider=entry["provider"],
                model=entry["model"],
                input_price=entry["input_price"],
                output_price=entry["output_price"],
                unit=entry.get("unit", raw.get("unit", "per_mtok")),
                source=entry.get("source", ""),
                consulted_at=entry.get("consulted_at"),
            )
            self._register(mp.model, mp)
            for alias in entry.get("aliases", []):
                self._register(alias, mp)

    def _register(self, key: str, mp: ModelPrice) -> None:
        self._by_key[self._norm(key)] = mp

    @staticmethod
    def _norm(name: str) -> str:
        return name.strip().lower()

    @classmethod
    def load(cls, path: Optional[Path] = None, *, today: Optional[str] = None) -> "PricingTable":
        path = Path(path) if path else DEFAULT_TABLE
        with open(path, "r", encoding="utf-8") as f:  # local file only
            return cls(json.load(f), today=today)

    def lookup(self, model: Optional[str]) -> Optional[ModelPrice]:
        if not model:
            return None
        return self._by_key.get(self._norm(model))

    def staleness_warning(self, mp: ModelPrice) -> Optional[Warning]:
        if not mp.consulted_at:
            return Warning(
                WarningType.PRICE_STALE,
                f"Precio de '{mp.model}' sin fecha de consulta.",
                source=mp.model,
            )
        try:
            consulted = date.fromisoformat(mp.consulted_at)
        except ValueError:
            return Warning(
                WarningType.PRICE_STALE,
                f"Fecha de consulta inválida para '{mp.model}': {mp.consulted_at}.",
                source=mp.model,
            )
        today = date.fromisoformat(self._today) if self._today else date.today()
        age = (today - consulted).days
        if age > self.stale_after_days:
            return Warning(
                WarningType.PRICE_STALE,
                f"Precio de '{mp.model}' vencido: {age} días desde la consulta "
                f"({mp.consulted_at}).",
                source=mp.model,
            )
        return None

    def meta(self) -> dict:
        sources = sorted({mp.source for mp in self._by_key.values() if mp.source})
        dates = sorted({mp.consulted_at for mp in self._by_key.values() if mp.consulted_at})
        return {
            "schema_version": self.schema_version,
            "currency": self.currency,
            "models_count": len({id(mp) for mp in self._by_key.values()}),
            "sources": sources,
            "consulted_dates": dates,
            "stale_after_days": self.stale_after_days,
        }
