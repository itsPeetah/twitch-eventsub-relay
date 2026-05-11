from __future__ import annotations

from aio_pika import ExchangeType

from src.core.plugins import EventSubPlugin
from src.core.rabbit import DeclareJob, RabbitAsyncPublisher
from src.core.websockets import EventSubWebSocketBroadcaster

DEFAULT_PUBLISH_EXCHANGE = "twitch_eventsub"

# WebSocket subscription channel is ``{WEBSOCKET_CHANNEL_PREFIX}{subscription_type}``.
WEBSOCKET_CHANNEL_PREFIX = "eventsub::"


class DefaultEventSubSinkPlugin(EventSubPlugin):
    """
    Pass-through sink: publishes every notification to RabbitMQ (topic exchange)
    and broadcasts over WebSocket—each side is skipped when that dependency was not
    injected (``None``).

    WebSocket clients must subscribe using :data:`WEBSOCKET_CHANNEL_PREFIX` before the
    EventSub subscription type (e.g. ``eventsub::channel.chat.message``).
    """

    def __init__(
        self,
        ws: EventSubWebSocketBroadcaster | None,
        rabbit: RabbitAsyncPublisher | None,
        *,
        publish_exchange: str = DEFAULT_PUBLISH_EXCHANGE,
    ) -> None:
        declare_jobs = (DeclareJob(publish_exchange, ExchangeType.TOPIC),)
        super().__init__(ws, rabbit, declare_jobs=declare_jobs)
        self._publish_exchange = publish_exchange

    def handle(self, event_type: str, payload: object) -> None:
        self.publish_rabbit(event_type, payload, exchange=self._publish_exchange)
        self.broadcast_websocket(f"{WEBSOCKET_CHANNEL_PREFIX}{event_type}", payload)

