"""
Consume Twitch EventSub chat messages from RabbitMQ (asyncio + aio-pika).

Declares a durable queue bound to the exchange from ``config/amqp_config.json`` with
routing key ``channel.chat.message`` (topic exchange).

Signal-driven shutdown matches ``rabbitmain.py`` in this directory.

Run from anywhere (repo root is detected automatically), e.g.:

``python examples/rabbitmq/rabbitconsumer.py``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import RabbitConsumer, load_amqp_config
from src.aioloop import AppLifecycle
from src.logger import AppLogger

_CONFIG_DIR = _PROJECT_ROOT / "config"


async def main() -> None:
    app_log = AppLogger.create(_PROJECT_ROOT, name="twitch_authenticator_rabbit_consumer")
    amqp_cfg = load_amqp_config(_CONFIG_DIR / "amqp_config.json")
    consumer = RabbitConsumer(amqp_cfg, logger=app_log.sub("consumer"))
    async with AppLifecycle() as ctl:
        try:
            await ctl.run_interruptible(consumer.run())
        finally:
            await consumer.close()


if __name__ == "__main__":
    asyncio.run(main())
