from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from ..rabbit import DeclareJob, RabbitAsyncPublisher
from ..twitch import EventHandler
from ..websockets import EventSubWebSocketBroadcaster


class EventSubPlugin(ABC):
    """
    EventSub notification plugin: implements :meth:`handle` like a sink callable.

    Subclasses receive the WebSocket broadcaster and Rabbit publisher (either may be
    ``None`` when that integration is disabled). Optional :class:`DeclareJob`
    instances are registered on the publisher when ``rabbit`` is not ``None``.
    """

    def __init__(
        self,
        ws: EventSubWebSocketBroadcaster | None,
        rabbit: RabbitAsyncPublisher | None,
        *,
        declare_jobs: Sequence[DeclareJob] | None = None,
    ) -> None:
        self._ws = ws
        self._rabbit = rabbit
        if declare_jobs is not None and rabbit is not None:
            for job in declare_jobs:
                rabbit.register_declare_job(job.name, job.type)

    @property
    def ws(self) -> EventSubWebSocketBroadcaster | None:
        return self._ws

    @property
    def rabbit(self) -> RabbitAsyncPublisher | None:
        return self._rabbit

    @abstractmethod
    def handle(self, event_type: str, payload: object) -> None:
        """Called for each EventSub notification (same contract as other sinks)."""

    def publish_rabbit(self, routing_key: str, payload: object, *, exchange: str) -> None:
        """Publish via RabbitMQ if a publisher was injected; otherwise no-op."""
        if self._rabbit is not None:
            self._rabbit.publish_event(routing_key, payload, exchange=exchange)

    def broadcast_websocket(self, event_type: str, payload: object) -> None:
        """Enqueue a WebSocket broadcast if a broadcaster was injected; otherwise no-op."""
        if self._ws is not None:
            self._ws.handle_event(event_type, payload)

    @staticmethod
    def as_event_handlers(*plugins: EventSubPlugin) -> tuple[EventHandler, ...]:
        """Wrap each plugin's :meth:`~EventSubPlugin.handle` in an :class:`~src.core.twitch.EventHandler`."""
        return tuple(EventHandler(p.handle) for p in plugins)
