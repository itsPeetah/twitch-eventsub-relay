"""
WebSocket sink for EventSub: clients subscribe to arbitrary channel strings.

Client → server (JSON text):

- ``{"op": "subscribe", "channels": ["eventsub::channel.chat.message", ...]}`` (opaque strings; ``main.py`` uses the ``eventsub::`` prefix via ``src.apps.plugins``.)
- ``{"op": "unsubscribe", "channels": [...]}``
- ``{"op": "list"}`` → server replies ``{"op": "list", "channels": [...]}``

Server → client (notifications):

- ``{"event_type": "<channel_string>", "payload": ...}`` (same string used for subscription routing, e.g. ``eventsub::channel.chat.message`` when using the default sink plugin.)

Call :meth:`EventSubWebSocketBroadcaster.handle_event` from the same asyncio loop
as :meth:`EventSubWebSocketBroadcaster.run` (matches Twitch EventSub integration).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from websockets.asyncio.server import ServerConnection, serve

from .config import WsConfig
from .registry import ChannelSubscriptionRegistry


class EventSubWebSocketBroadcaster:
    """
    Runs a WebSocket server and broadcasts EventSub notifications to subscribers.

    Uses an internal queue so :meth:`handle_event` never blocks the Twitch coroutine.
    """

    def __init__(self, ws_config: WsConfig, *, logger: logging.Logger) -> None:
        self._cfg = ws_config
        self._logger = logger
        self._registry = ChannelSubscriptionRegistry()
        self._queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        self._broadcast_worker_task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        async def conn_handler(ws: ServerConnection) -> None:
            await self._connection_loop(ws)

        bind_host = self._cfg.host
        if bind_host in ("127.0.0.1", "localhost", "::1"):
            self._logger.warning(
                "websocket bound to %s — only this machine can connect; "
                "set ws_config host to 0.0.0.0 for LAN/remote clients",
                bind_host,
            )

        async with serve(
            conn_handler,
            bind_host,
            self._cfg.port,
        ):
            self._logger.info(
                "websocket eventsub sink listening ws://%s:%s/ "
                "(broadcast worker starting)",
                bind_host,
                self._cfg.port,
            )
            self._broadcast_worker_task = asyncio.create_task(self._broadcast_worker())
            try:
                await asyncio.Future()
            finally:
                if self._broadcast_worker_task is not None:
                    self._broadcast_worker_task.cancel()
                    try:
                        await self._broadcast_worker_task
                    except asyncio.CancelledError:
                        pass
                    self._broadcast_worker_task = None

    async def close(self) -> None:
        """Server stops when the :meth:`run` task is cancelled (e.g. ``gather`` teardown)."""

    def handle_event(self, event_type: str, payload: object) -> None:
        self._logger.debug(
            "websocket enqueue event_type=%s payload=%s", event_type, payload
        )
        task = asyncio.create_task(self._enqueue(event_type, payload))
        task.add_done_callback(self._log_enqueue_failure)

    async def _enqueue(self, event_type: str, payload: object) -> None:
        await self._queue.put((event_type, payload))

    def _log_enqueue_failure(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            self._logger.exception("failed to enqueue websocket broadcast")

    async def _broadcast_worker(self) -> None:
        while True:
            event_type, payload = await self._queue.get()
            await self._broadcast(event_type, payload)

    async def _broadcast(self, event_type: str, payload: object) -> None:
        peers = self._registry.peers_for(event_type)
        if not peers:
            return
        msg = json.dumps(
            {"event_type": event_type, "payload": payload},
            ensure_ascii=False,
        )
        for ws in list(peers):
            if not isinstance(ws, ServerConnection):
                continue
            try:
                await ws.send(msg)
            except Exception:
                self._logger.exception(
                    "websocket send failed event_type=%s peer=%s",
                    event_type,
                    getattr(ws, "remote_address", None),
                )
                self._registry.remove_connection(ws)

    async def _connection_loop(self, ws: ServerConnection) -> None:
        peer = ws.remote_address
        self._logger.info("websocket client connected peer=%s", peer)
        try:
            async for raw in ws:
                await self._dispatch_client_message(ws, raw)
        except Exception:
            self._logger.debug("websocket client recv ended peer=%s", peer, exc_info=True)
        finally:
            self._registry.remove_connection(ws)
            self._logger.info("websocket client disconnected peer=%s", peer)

    async def _dispatch_client_message(
        self,
        ws: ServerConnection,
        raw: Any,
    ) -> None:
        if not isinstance(raw, str):
            self._logger.debug("ignore non-text ws frame from %s", ws.remote_address)
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self._logger.debug("invalid json from ws %s", ws.remote_address)
            return

        if not isinstance(data, dict):
            return

        op = data.get("op")
        if op == "subscribe":
            chans = data.get("channels")
            if isinstance(chans, list):
                names = [str(c) for c in chans]
                self._registry.subscribe(ws, names)
                self._logger.info(
                    "websocket subscribe peer=%s channels=%s",
                    ws.remote_address,
                    names,
                )
            return

        if op == "unsubscribe":
            chans = data.get("channels")
            if isinstance(chans, list):
                names = [str(c) for c in chans]
                self._registry.unsubscribe(ws, names)
                self._logger.info(
                    "websocket unsubscribe peer=%s channels=%s",
                    ws.remote_address,
                    names,
                )
            return

        if op == "list":
            subs = sorted(self._registry.channels_for(ws))
            await ws.send(json.dumps({"op": "list", "channels": subs}))
            self._logger.info(
                "websocket list peer=%s subscriptions=%s",
                ws.remote_address,
                subs,
            )
            return

        self._logger.debug("unknown ws op=%r from %s", op, ws.remote_address)
