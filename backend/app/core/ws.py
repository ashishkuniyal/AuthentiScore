"""
AuthentiScore — WebSocket Connection Manager
=============================================

Per-user WebSocket connections with:
  - Token authentication at connect time (S5)
  - Per-user message routing (no broadcast to all)
  - Thread-safe notifications from sync worker threads (C1)
  - Graceful disconnect / dead-socket pruning (C3)

Usage from async context:
    from app.core.ws import manager
    await manager.send_to_user(user_id, payload_dict)

Usage from sync (worker-thread) context:
    from app.core.ws import notify_user_threadsafe
    notify_user_threadsafe(user_id, payload_dict)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Per-user WebSocket manager."""

    def __init__(self) -> None:
        # user_id → set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ─────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────

    def capture_loop(self) -> None:
        """Call from FastAPI lifespan (async context) to capture the event loop."""
        self._loop = asyncio.get_event_loop()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self._connections.setdefault(user_id, set()).add(websocket)
        logger.debug("WS connected: user=%s total=%d", user_id, self._total())

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        conns = self._connections.get(user_id, set())
        conns.discard(websocket)
        if not conns:
            self._connections.pop(user_id, None)
        logger.debug("WS disconnected: user=%s remaining=%d", user_id, self._total())

    def _total(self) -> int:
        return sum(len(s) for s in self._connections.values())

    # ─────────────────────────────────────────────────────────
    # Sending
    # ─────────────────────────────────────────────────────────

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a JSON message to all sockets belonging to *user_id*."""
        conns = list(self._connections.get(user_id, set()))
        dead: list[WebSocket] = []
        payload = json.dumps(message, default=str)
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    # ─────────────────────────────────────────────────────────
    # Thread-safe notifications from sync worker threads (C1)
    # ─────────────────────────────────────────────────────────

    def notify_user_threadsafe(self, user_id: str, message: dict) -> None:
        """
        Enqueue a notification from a sync worker thread.
        Requires capture_loop() to have been called during startup.
        """
        if self._loop is None or self._loop.is_closed():
            logger.warning("WS loop not available; notification dropped: %s", message)
            return
        future = asyncio.run_coroutine_threadsafe(
            self.send_to_user(user_id, message),
            self._loop,
        )
        # Log failures without blocking the worker thread
        def _on_done(f: "asyncio.Future") -> None:
            exc = f.exception()
            if exc:
                logger.warning("WS notify failed for user=%s: %s", user_id, exc)

        future.add_done_callback(_on_done)


# Global singleton
manager = ConnectionManager()


def notify_user_threadsafe(user_id: str, message: dict) -> None:
    """Module-level convenience wrapper for sync worker threads."""
    manager.notify_user_threadsafe(user_id, message)
