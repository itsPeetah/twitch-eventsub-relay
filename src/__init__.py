"""
Library surface for Twitch EventSub, optional RabbitMQ publishing, and WebSocket broadcast.

Typical flow: build :class:`~src.app.TwitchApp` with one or more
:class:`~src.twitch.event_handler.EventHandler` sinks (stdout, :class:`~src.rabbit.publisher.RabbitAsyncPublisher`,
:class:`~src.websockets.server.EventSubWebSocketBroadcaster`), optionally gathered alongside ``bridge.run()`` like ``main.py`` does.

Configuration loaders read JSON under ``config/``: :func:`~src.amqp.config.load_amqp_config`,
:func:`~src.websockets.config.load_ws_config`, :func:`~src.twitch.app_config.load_twitch_app_config`.
"""

from .amqp import AmqpClient, AmqpConfig, load_amqp_config
from .app import TwitchApp
from .rabbit import RabbitAsyncPublisher, RabbitConsumer
from .websockets import EventSubWebSocketBroadcaster, WsConfig, load_ws_config
from .twitch import (
    combine_event_handlers,
    EventHandler,
    EventSubSubscription,
    OAuthManager,
    OAuthTokenDatabase,
    TwitchAppConfig,
    TwitchEventSub,
    load_twitch_app_config,
    normalize_event_handlers,
)

__all__ = [
    "AmqpClient",
    "AmqpConfig",
    "combine_event_handlers",
    "EventSubWebSocketBroadcaster",
    "EventHandler",
    "EventSubSubscription",
    "OAuthManager",
    "OAuthTokenDatabase",
    "RabbitAsyncPublisher",
    "RabbitConsumer",
    "TwitchApp",
    "TwitchAppConfig",
    "TwitchEventSub",
    "load_amqp_config",
    "load_twitch_app_config",
    "load_ws_config",
    "normalize_event_handlers",
    "WsConfig",
]
