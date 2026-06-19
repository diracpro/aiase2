"""Path configuration and write policy (PRD §2, §5).

This module is the single source of truth for:
- which paths may be READ,
- the single path that may be WRITTEN,
- which source paths are FORBIDDEN for writing.

`assert_write_allowed()` is the guard every writer must call before touching disk.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _home() -> Path:
    return Path(os.path.expanduser("~"))


# Source paths that must NEVER be written to (PRD §2 Output Policy).
def forbidden_write_roots() -> list[Path]:
    h = _home()
    return [
        h / ".claude",
        h / ".codex",
        h / ".config" / "claude",
        h / ".config" / "codex",
        h / ".claude" / "skills",
    ]


DEFAULT_OUTPUT_DIR = Path("/tmp/ai-usage-dashboard")


@dataclass
class Config:
    """Resolved runtime configuration.

    read_paths: directories/files the scanner may read (default: ~/.claude).
    output_dir: the ONLY directory writes are allowed into.
    codex_paths / skills_paths: read-only, P1 discovery only.
    offline: when True (default) any network use is treated as a violation.
    allow_persistent_logs: persistent logs only ever go to output_dir.
    """

    read_paths: list[Path] = field(default_factory=lambda: [_home() / ".claude"])
    codex_paths: list[Path] = field(default_factory=lambda: [_home() / ".codex"])
    skills_paths: list[Path] = field(
        default_factory=lambda: [_home() / ".claude" / "skills"]
    )
    output_dir: Path = DEFAULT_OUTPUT_DIR
    offline: bool = True
    allow_persistent_logs: bool = False
    allow_snippets: bool = False  # PRD §5: only with explicit user opt-in

    def __post_init__(self) -> None:
        self.read_paths = [Path(p).expanduser() for p in self.read_paths]
        self.codex_paths = [Path(p).expanduser() for p in self.codex_paths]
        self.skills_paths = [Path(p).expanduser() for p in self.skills_paths]
        self.output_dir = Path(self.output_dir).expanduser()
        self._validate_output_dir()

    def _validate_output_dir(self) -> None:
        out = self.output_dir.resolve()
        for forbidden in forbidden_write_roots():
            f = forbidden.resolve()
            if out == f or _is_relative_to(out, f):
                raise ValueError(
                    f"Ruta de salida no permitida: {out} está dentro de una ruta "
                    f"fuente protegida ({f})."
                )

    def assert_write_allowed(self, target: Path) -> Path:
        """Raise unless `target` is inside output_dir and outside every source root.

        Returns the resolved absolute target path on success.
        """
        target = Path(target).expanduser()
        # Resolve against output_dir if relative.
        if not target.is_absolute():
            target = self.output_dir / target
        resolved = target.resolve()
        out = self.output_dir.resolve()

        if not (resolved == out or _is_relative_to(resolved, out)):
            raise PermissionError(
                f"Escritura rechazada: {resolved} está fuera de la ruta de salida "
                f"permitida ({out})."
            )
        for forbidden in forbidden_write_roots():
            f = forbidden.resolve()
            if resolved == f or _is_relative_to(resolved, f):
                raise PermissionError(
                    f"Escritura rechazada: {resolved} toca una ruta fuente "
                    f"protegida ({f})."
                )
        return resolved

    def is_read_path_allowed(self, target: Path) -> bool:
        resolved = Path(target).expanduser().resolve()
        allowed = self.read_paths + self.codex_paths + self.skills_paths
        for root in allowed:
            r = root.resolve()
            if resolved == r or _is_relative_to(resolved, r):
                return True
        return False


def _is_relative_to(path: Path, root: Path) -> bool:
    """Backport of Path.is_relative_to for safety across versions."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
