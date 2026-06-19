"""Claude Code transcript scanner (PRD §4 P0 Scanner + resilience).

Claude Code stores sessions as JSONL transcripts (typically under
~/.claude/projects/<encoded-cwd>/<session-id>.jsonl). Each line is a JSON object;
assistant lines carry `message.model` and `message.usage.{input_tokens,
output_tokens}` plus a `timestamp`.

Guarantees:
- Files are opened READ-ONLY; nothing is written to source paths.
- A failing file never aborts the run: it yields a Warning and processing
  continues (PRD §4 acceptance, §7 KPI >=95%).
- Tokens are read only when present; we never infer tokens from text.
- Cache token fields are intentionally NOT summed (PRD §6: cache billing not
  represented).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from .config import Config
from .models import Session, Warning, WarningType


def find_transcripts(config: Config) -> list[Path]:
    """All *.jsonl transcript files under configured read paths."""
    files: list[Path] = []
    for root in config.read_paths:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".jsonl":
            files.append(root)
            continue
        files.extend(sorted(root.rglob("*.jsonl")))
    return files


def _extract_usage(message: dict) -> tuple[Optional[int], Optional[int]]:
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None, None
    inp = usage.get("input_tokens")
    out = usage.get("output_tokens")
    inp = inp if isinstance(inp, int) else None
    out = out if isinstance(out, int) else None
    return inp, out


def parse_transcript(path: Path) -> tuple[Optional[Session], list[Warning]]:
    """Parse a single transcript file into one Session.

    Returns (session, warnings). `session` is None only if the file could not be
    read at all. Per-line JSON errors are tolerated and counted.
    """
    warnings: list[Warning] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:  # read-only
            lines = f.readlines()
    except OSError as exc:
        return None, [
            Warning(WarningType.FILE_UNREADABLE, f"No se pudo leer: {exc}", str(path))
        ]

    session_id: Optional[str] = None
    started_at: Optional[str] = None
    model_output_tokens: dict[str, int] = {}
    models_seen: list[str] = []  # ordered, even when usage is absent
    total_input = 0
    total_output = 0
    saw_tokens = False
    message_count = 0
    bad_lines = 0
    recognized_lines = 0

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            bad_lines += 1
            continue
        if not isinstance(obj, dict):
            bad_lines += 1
            continue

        recognized_lines += 1
        session_id = session_id or obj.get("sessionId") or obj.get("session_id")
        ts = obj.get("timestamp") or obj.get("ts")
        if ts and (started_at is None or str(ts) < started_at):
            started_at = str(ts)

        otype = obj.get("type") or obj.get("role")
        if otype in ("user", "assistant"):
            message_count += 1

        message = obj.get("message")
        if isinstance(message, dict):
            model = message.get("model")
            if model and model not in models_seen:
                models_seen.append(model)
            inp, out = _extract_usage(message)
            if inp is not None or out is not None:
                saw_tokens = True
                total_input += inp or 0
                total_output += out or 0
                if model:
                    model_output_tokens[model] = (
                        model_output_tokens.get(model, 0) + (out or 0)
                    )

    if recognized_lines == 0:
        warnings.append(
            Warning(
                WarningType.UNKNOWN_FORMAT,
                "Archivo sin líneas JSON reconocibles.",
                str(path),
            )
        )
    if bad_lines:
        warnings.append(
            Warning(
                WarningType.FILE_CORRUPT,
                f"{bad_lines} línea(s) ilegibles/corruptas omitidas.",
                str(path),
            )
        )

    # Dominant model = the one that produced the most output tokens; if no token
    # data exists, fall back to the last model seen so the session is reported as
    # "tokens_faltantes" rather than "modelo_desconocido".
    model: Optional[str] = None
    if model_output_tokens:
        model = max(model_output_tokens.items(), key=lambda kv: kv[1])[0]
    elif models_seen:
        model = models_seen[-1]

    session = Session(
        session_id=session_id or path.stem,
        source_file=str(path),
        started_at=started_at,
        model=model,
        input_tokens=total_input if saw_tokens else None,
        output_tokens=total_output if saw_tokens else None,
        message_count=message_count,
        summary=f"{message_count} mensajes",
        warnings=list(warnings),
    )
    return session, warnings


def scan(config: Config) -> tuple[list[Session], list[Warning], int]:
    """Scan all transcripts. Returns (sessions, global_warnings, files_failed)."""
    sessions: list[Session] = []
    global_warnings: list[Warning] = []
    files_failed = 0

    for path in find_transcripts(config):
        try:
            session, warnings = parse_transcript(path)
        except Exception as exc:  # last-resort guard: one file never breaks the run
            files_failed += 1
            global_warnings.append(
                Warning(
                    WarningType.FILE_CORRUPT,
                    f"Error inesperado al procesar: {exc}",
                    str(path),
                )
            )
            continue
        if session is None:
            files_failed += 1
            global_warnings.extend(warnings)
            continue
        sessions.append(session)
        global_warnings.extend(warnings)

    return sessions, global_warnings, files_failed
