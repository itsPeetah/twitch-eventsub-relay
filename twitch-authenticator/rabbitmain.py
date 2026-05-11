"""
Like ``main.py``, but forwards EventSub notifications to RabbitMQ.

Publishing uses asyncio + aio-pika: notifications are scheduled onto an
:class:`asyncio.Queue` from the EventSub coroutine and drained by an async worker
that awaits :meth:`AmqpClient.publish_json`, so the WebSocket loop never blocks on
the broker. Only the configured topic exchange is declared; no queues or
consumers are registered here.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from src import AmqpClient, AmqpConfig, EventHandler, TwitchApp, load_amqp_config
from src.logging_setup import get_logger

_APP_DIR = Path(__file__).resolve().parent


class RabbitAsyncPublisher:
    """
    Bridges sync :class:`EventHandler` callbacks into async publishes: each call
    schedules a put on an :class:`asyncio.Queue`; :meth:`worker` awaits broker I/O.
    """

    def __init__(self, client: AmqpClient, *, logger: logging.Logger) -> None:
        self._client = client
        self._logger = logger
        self._queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    def publish_event(self, event_type: str, payload: object) -> None:
        self._logger.debug("publishing event type=%s payload=%s", event_type, payload)
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
            self._logger.exception("failed to enqueue message for RabbitMQ")

    async def worker(self) -> None:
        while True:
            event_type, payload = await self._queue.get()
            try:
                await self._client.publish_json(event_type, payload)
            except Exception:
                self._logger.exception(
                    "rabbitmq publish failed event_type=%s", event_type
                )


async def main() -> None:
    logger = get_logger("twitch_authenticator_rabbitmq", _APP_DIR / "twitch.log")
    amqp_cfg = load_amqp_config(_APP_DIR / "amqp_config.json")

    client = AmqpClient(amqp_cfg)
    await client.connect()
    await client.declare_topic_exchange()
    logger.info(
        "rabbitmq publisher ready (async publish-only, exchange=%s type=topic durable)",
        client.default_exchange,
    )

    publisher = RabbitAsyncPublisher(client, logger=logger)
    worker_task = asyncio.create_task(publisher.worker())

    app = TwitchApp(
        config_path=_APP_DIR / "twitch_config.json",
        token_db_path=_APP_DIR / "tokens.sqlite",
        logger=logger,
        handler=EventHandler(publisher.publish_event),
    )
    try:
        await app.run()
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
