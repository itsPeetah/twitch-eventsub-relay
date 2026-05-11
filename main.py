import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from aio_pika import ExchangeType

from src.core.amqp import load_amqp_config
from src.core.aioloop import AppLifecycle
from src.core.logger import AppLogger
from src.core.rabbit import RabbitAsyncPublisher
from src.core.twitch import EventHandler
from src.core.websockets import EventSubWebSocketBroadcaster, load_ws_config
from src.app import TwitchApp

_APP_DIR = Path(__file__).resolve().parent
_CONFIG_DIR = _APP_DIR / "config"

_DEFAULT_PUBLISH_EXCHANGE = "twitch_eventsub"


def print_eventsub_event(event_type: str, payload: object) -> None:
    """Default business sink: print each EventSub notification to stdout."""
    print(f"[event] {event_type} {json.dumps(payload, ensure_ascii=False)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Twitch EventSub WebSocket client (OAuth + subscriptions).",
    )
    parser.add_argument(
        "--use-rabbitmq",
        action="store_true",
        help="Also publish notifications to RabbitMQ (uses config/amqp_config.json).",
    )
    parser.add_argument(
        "--use-websockets",
        action="store_true",
        help="Also broadcast notifications over WebSocket (uses config/ws_config.json).",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    app_log = AppLogger.create(_APP_DIR, name="twitch_client")
    logger = app_log.logger

    handlers: list[EventHandler] = [EventHandler(print_eventsub_event)]
    rabbit: RabbitAsyncPublisher | None = None
    ws_broadcast: EventSubWebSocketBroadcaster | None = None

    if args.use_rabbitmq:
        amqp_cfg = load_amqp_config(_CONFIG_DIR / "amqp_config.json")
        rabbit = RabbitAsyncPublisher(
            amqp_cfg,
            logger=app_log.sub("rabbitmq_sink"),
        )
        rabbit.register_declare_job(_DEFAULT_PUBLISH_EXCHANGE, ExchangeType.TOPIC)
        handlers.append(
            EventHandler(
                lambda et, pl: rabbit.publish_event(
                    et, pl, exchange=_DEFAULT_PUBLISH_EXCHANGE
                )
            )
        )

    if args.use_websockets:
        ws_cfg = load_ws_config(_CONFIG_DIR / "ws_config.json")
        ws_broadcast = EventSubWebSocketBroadcaster(
            ws_cfg,
            logger=app_log.sub("websocket_server"),
        )
        handlers.append(EventHandler(ws_broadcast.handle_event))

    app = TwitchApp(
        config_path=_CONFIG_DIR / "twitch_config.json",
        token_db_path=_APP_DIR / "tokens.sqlite",
        logger=logger,
        handlers=handlers,
    )

    to_gather: list[Any] = []
    if rabbit is not None:
        to_gather.append(rabbit.run())
    if ws_broadcast is not None:
        to_gather.append(ws_broadcast.run())
    to_gather.append(app.run())

    async with AppLifecycle() as lifecycle:
        try:
            await lifecycle.run_interruptible(asyncio.gather(*to_gather))
        finally:
            if rabbit is not None:
                await rabbit.close()
            if ws_broadcast is not None:
                await ws_broadcast.close()


if __name__ == "__main__":
    asyncio.run(main())
