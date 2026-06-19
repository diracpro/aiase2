"""Cost engine (PRD §4 P0 Cost Engine, §8).

A cost is CALCULATED only when ALL of these hold:
  - the model is recognized in the local pricing table,
  - input_tokens is present,
  - output_tokens is present,
  - a configured price exists.

Otherwise the result carries an explicit non-calculable status and NO cost
numbers. We never infer tokens from text, and an incomplete session never shows
a cost as if it were exact.
"""
from __future__ import annotations

from .models import CostResult, CostStatus, Session, Warning, WarningType
from .pricing import PricingTable


def compute_cost(session: Session, pricing: PricingTable) -> CostResult:
    if not session.model:
        return CostResult(CostStatus.UNKNOWN_MODEL)

    price = pricing.lookup(session.model)
    if price is None:
        return CostResult(CostStatus.PRICE_NOT_CONFIGURED)

    if not session.has_tokens:
        return CostResult(CostStatus.TOKENS_MISSING)

    input_cost, output_cost = price.cost_for(
        session.input_tokens or 0, session.output_tokens or 0
    )
    return CostResult(
        status=CostStatus.CALCULATED,
        input_cost=round(input_cost, 6),
        output_cost=round(output_cost, 6),
        total_cost=round(input_cost + output_cost, 6),
        currency=pricing.currency,
    )


def apply_costs(sessions: list[Session], pricing: PricingTable) -> list[Warning]:
    """Attach a CostResult to each session. Returns extra warnings (stale prices,
    non-calculable reasons) for surfacing in the report."""
    warnings: list[Warning] = []
    for s in sessions:
        result = compute_cost(s, pricing)
        s.cost = result

        if result.status == CostStatus.CALCULATED:
            price = pricing.lookup(s.model)
            if price:
                stale = pricing.staleness_warning(price)
                if stale:
                    warnings.append(stale)
                    s.warnings.append(stale)
        elif result.status == CostStatus.UNKNOWN_MODEL:
            w = Warning(
                WarningType.UNKNOWN_MODEL,
                f"Modelo desconocido o ausente para la sesión {s.session_id}.",
                s.model or s.session_id,
            )
            warnings.append(w)
            s.warnings.append(w)
        elif result.status == CostStatus.PRICE_NOT_CONFIGURED:
            w = Warning(
                WarningType.PRICE_MISSING,
                f"Sin precio configurado para el modelo '{s.model}'.",
                s.model,
            )
            warnings.append(w)
            s.warnings.append(w)
        elif result.status == CostStatus.TOKENS_MISSING:
            w = Warning(
                WarningType.TOKENS_MISSING,
                f"Sesión {s.session_id} sin tokens: no calculable.",
                s.session_id,
            )
            warnings.append(w)
            s.warnings.append(w)

    return warnings
