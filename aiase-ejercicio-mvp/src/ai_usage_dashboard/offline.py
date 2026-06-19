"""Offline guard (PRD §2 Network, §7, §8).

During analysis the network is disabled by default. We enforce this by replacing
socket creation with a guard that raises on any attempt to open a connection.
This makes "0 network calls during analysis" a testable, technical guarantee
rather than a convention.

Loopback (127.0.0.1 / ::1) is *not* opened by the scanner; the localhost server
runs as a separate step (`serve`) outside the analysis guard.
"""
from __future__ import annotations

import contextlib
import socket


class NetworkAccessError(RuntimeError):
    """Raised when code attempts network access while offline mode is active."""


class _GuardedSocket(socket.socket):
    def connect(self, *args, **kwargs):  # pragma: no cover - exercised via tests
        raise NetworkAccessError(
            "Acceso a red bloqueado durante el análisis (modo offline)."
        )

    def connect_ex(self, *args, **kwargs):  # pragma: no cover
        raise NetworkAccessError(
            "Acceso a red bloqueado durante el análisis (modo offline)."
        )


@contextlib.contextmanager
def network_disabled(active: bool = True):
    """Context manager that blocks outbound socket connections while active."""
    if not active:
        yield
        return

    original_socket = socket.socket
    original_getaddrinfo = socket.getaddrinfo
    socket.socket = _GuardedSocket  # type: ignore[assignment]

    def _blocked_getaddrinfo(*args, **kwargs):
        raise NetworkAccessError(
            "Resolución DNS bloqueada durante el análisis (modo offline)."
        )

    socket.getaddrinfo = _blocked_getaddrinfo  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]
