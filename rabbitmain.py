"""
Like ``main.py``, but forwards EventSub notifications to RabbitMQ.

Publishing uses asyncio + aio-pika: notifications are scheduled onto an
:class:`asyncio.Queue` from the EventSub coroutine and drained by an async worker
that awaits :meth:`AmqpClient.publish_json`, so the WebSocket loop never blocks on
the broker. Only the configured topic exchange is declared; no queues or
consumers are registered here.

SIGINT / SIGTERM (when supported) cancel :meth:`RabbitAsyncPublisher.run` and
:meth:`TwitchApp.run`; :meth:`RabbitAsyncPublisher.close` drains the worker and
closes the broker—same pattern as :mod:`rabbitconsumer`.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from core import AmqpClient, AmqpConfig, EventHandler, TwitchApp, load_amqp_config
from core.aioloop import ShutdownLoop
from core.logging_setup import get_logger

_APP_DIR = Path(__file__).resolve().parent


class RabbitAsyncPublisher:
    """
    Bridges sync :class:`EventHandler` callbacks into async publishes: each call
    schedules a put on an :class:`asyncio.Queue`; a background task drains the
    queue and awaits :meth:`AmqpClient.publish_json`.

    :meth:`run` connects, declares the exchange, starts that worker, then blocks
    until cancelled (same “long‑running session” shape as :meth:`TwitchApp.run`).
    :meth:`close` cancels the worker and closes the AMQP client.
    """

    def __init__(self, amqp_config: AmqpConfig, *, logger: logging.Logger) -> None:
        self._client = AmqpClient(amqp_config)
        self._logger = logger
        self._queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        await self._ensure_amqp_and_worker()
        await asyncio.Future()

    async def _ensure_amqp_and_worker(self) -> None:
        if self._worker_task is not None:
            return
        await self._client.connect()
        await self._client.declare_topic_exchange()
        self._logger.info(
            "rabbitmq publisher ready (async publish-only, exchange=%s "
            "type=topic durable)",
            self._client.default_exchange,
        )
        self._worker_task = asyncio.create_task(self._publish_worker())

    async def close(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        await self._client.close()

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

    async def _publish_worker(self) -> None:
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

    bridge = RabbitAsyncPublisher(amqp_cfg, logger=logger)

    app = TwitchApp(
        config_path=_APP_DIR / "twitch_config.json",
        token_db_path=_APP_DIR / "tokens.sqlite",
        logger=logger,
        handler=EventHandler(bridge.publish_event),
    )

    async with ShutdownLoop() as ctl:
        try:
            await ctl.race_with_shutdown(
                asyncio.gather(
                    bridge.run(),
                    app.run(),
                )
            )
        finally:
            await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
