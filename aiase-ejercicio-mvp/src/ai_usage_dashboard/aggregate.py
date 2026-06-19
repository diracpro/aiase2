"""Aggregations for the dashboard (PRD §4).

Per-day and per-model spend include ONLY calculable sessions. Non-calculable
sessions are excluded from cost totals and reported separately (counts + reasons).
"""
from __future__ import annotations

from .models import DayAggregate, ModelAggregate, Session


def aggregate(sessions: list[Session]) -> dict:
    by_day: dict[str, DayAggregate] = {}
    by_model: dict[str, ModelAggregate] = {}
    total = 0.0
    non_calculable = 0

    for s in sessions:
        calculable = bool(s.cost and s.cost.is_calculable)
        day_key = s.day or "sin_fecha"
        model_key = s.model or "desconocido"

        day = by_day.setdefault(day_key, DayAggregate(day=day_key))
        model = by_model.setdefault(model_key, ModelAggregate(model=model_key))

        if calculable:
            cost = s.cost.total_cost or 0.0
            total += cost
            day.total_cost += cost
            day.calculable_sessions += 1
            model.total_cost += cost
            model.input_tokens += s.input_tokens or 0
            model.output_tokens += s.output_tokens or 0
            model.calculable_sessions += 1
        else:
            non_calculable += 1
            day.non_calculable_sessions += 1
            model.non_calculable_sessions += 1

    for d in by_day.values():
        d.total_cost = round(d.total_cost, 6)
    for m in by_model.values():
        m.total_cost = round(m.total_cost, 6)

    return {
        "total_calculated_cost": round(total, 6),
        "sessions_processed": len(sessions),
        "sessions_non_calculable": non_calculable,
        "by_day": sorted(by_day.values(), key=lambda d: d.day),
        "by_model": sorted(by_model.values(), key=lambda m: m.total_cost, reverse=True),
    }
