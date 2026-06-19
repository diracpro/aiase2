"""Codex & Skills discovery (PRD §4 P1, §5).

Informational only: detect installed tools and list basic metadata. We DO NOT
compute costs for Codex/Skills in the MVP unless verifiable model+tokens+price
exist (they generally do not here, so cost is always omitted).

All reads are read-only and limited to authorized discovery paths.
"""
from __future__ import annotations

from pathlib import Path

from .config import Config


def _safe_listdir(path: Path, limit: int = 200) -> list[str]:
    try:
        return sorted(p.name for p in list(path.iterdir())[:limit])
    except OSError:
        return []


def discover_codex(config: Config) -> dict:
    detected = False
    paths_read: list[str] = []
    notes: list[str] = []
    for p in config.codex_paths:
        if p.exists():
            detected = True
            paths_read.append(str(p))
            cfg = p / "config.toml"
            if cfg.exists():
                notes.append("config detectada")
            sessions_dir = p / "sessions"
            if sessions_dir.exists():
                notes.append("actividad observada (carpeta de sesiones)")
    return {
        "tool": "codex",
        "detected": detected,
        "paths_read": paths_read,
        "notes": notes,
        "cost": None,
        "cost_note": "No se calcula costo para Codex en el MVP (sin datos verificables).",
    }


def discover_skills(config: Config) -> dict:
    detected = False
    paths_read: list[str] = []
    skills: list[str] = []
    for p in config.skills_paths:
        if p.exists():
            detected = True
            paths_read.append(str(p))
            for entry in _safe_listdir(p):
                skills.append(entry)
    return {
        "tool": "skills",
        "detected": detected,
        "paths_read": paths_read,
        "skills_installed": sorted(set(skills)),
        "cost": None,
        "cost_note": "No se calcula costo para Skills en el MVP (solo metadata).",
    }


def discover(config: Config) -> dict:
    return {
        "codex": discover_codex(config),
        "skills": discover_skills(config),
    }
