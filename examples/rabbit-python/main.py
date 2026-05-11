"""
Like ``main.py``, but forwards EventSub notifications to RabbitMQ.

Publishing uses asyncio + aio-pika: notifications are scheduled onto an
:class:`asyncio.Queue` from the EventSub coroutine and drained by an async worker
that awaits :meth:`AmqpClient.publish_json`, so the WebSocket loop never blocks on
the broker. Only the configured topic exchange is declared; no queues or
consumers are registered here.

SIGINT / SIGTERM (when supported) cancel :meth:`~src.rabbit.RabbitAsyncPublisher.run`
and :meth:`TwitchApp.run`; :meth:`~src.rabbit.RabbitAsyncPublisher.close` drains
the worker and closes the broker — same pattern as ``rabbitmq_consumer.py`` in this
directory.

Run from anywhere (repo root is detected automatically), e.g.:

``python examples/rabbit-python/main.py``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.amqp import load_amqp_config
from src.core.aioloop import AppLifecycle
from src.core.logger import AppLogger
from src.core.rabbit import RabbitAsyncPublisher
from src.core.twitch import EventHandler
from src.app import TwitchApp

_CONFIG_DIR = _PROJECT_ROOT / "config"


async def main() -> None:
    app_log = AppLogger.create(_PROJECT_ROOT, name="twitch_authenticator_rabbitmq")
    logger = app_log.logger
    amqp_cfg = load_amqp_config(_CONFIG_DIR / "amqp_config.json")

    bridge = RabbitAsyncPublisher(amqp_cfg, logger=app_log.sub("rabbitmq"))

    app = TwitchApp(
        config_path=_CONFIG_DIR / "twitch_config.json",
        token_db_path=_PROJECT_ROOT / "tokens.sqlite",
        logger=logger,
        handlers=EventHandler(bridge.publish_event),
    )

    async with AppLifecycle() as ctl:
        try:
            await ctl.run_interruptible(
                asyncio.gather(
                    bridge.run(),
                    app.run(),
                )
            )
        finally:
            await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
