"""
Consume Twitch EventSub messages from RabbitMQ (asyncio + aio-pika).

Each process declares its own queue (unique name, durable and auto-deleted when
it disconnects) bound to the topic
exchange using the EventSub subscription type as the routing key (default
``channel.chat.message``). Multiple consumers then each receive a copy of every
matching message. Connection settings are built as an
:class:`src.amqp.config.AmqpConfig` instance in code (no JSON file).

Signal-driven shutdown matches ``main.py`` in this directory.

Run from anywhere (repo root is detected automatically), e.g.:

``python examples/rabbit-python/rabbitmq_consumer.py``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import AmqpConfig, RabbitConsumer
from src.aioloop import AppLifecycle
from src.logger import AppLogger

# Twitch EventSub subscription type; must match the publisher routing key.
EVENT_TYPE = "channel.chat.message"
HOST="0.0.0.0"

def example_consumer_amqp_config() -> AmqpConfig:
    """Broker reachable from this machine (edit host/port/credentials as needed)."""
    host = HOST
    port = 5672
    user = "guest"
    password = "guest"
    url = f"amqp://{user}:{password}@{host}:{port}/"
    return AmqpConfig(
        url=url,
        exchange="twitch_eventsub",
        reconnect_delay=1.0,
        reconnect_backoff=2.0,
        reconnect_max_retries=None,
        reconnect_max_delay=60.0,
    )


async def main() -> None:
    amqp_cfg = example_consumer_amqp_config()

    app_log = AppLogger.create(
        _PROJECT_ROOT, name="twitch_authenticator_rabbit_consumer"
    )
    consumer = RabbitConsumer(
        amqp_cfg,
        logger=app_log.sub("consumer"),
        routing_key=EVENT_TYPE,
    )
    async with AppLifecycle() as ctl:
        try:
            await ctl.run_interruptible(consumer.run())
        finally:
            await consumer.close()


if __name__ == "__main__":
    asyncio.run(main())
