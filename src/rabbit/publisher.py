from __future__ import annotations

import asyncio
import logging

from ..amqp import AmqpClient, AmqpConfig
from ..amqp.config import redacted_amqp_url


class RabbitAsyncPublisher:
    """
    Bridges sync ``EventHandler`` callbacks into async publishes:
    each call schedules a put on an :class:`asyncio.Queue`; a background task drains
    the queue and awaits :meth:`AmqpClient.publish_json`.

    :meth:`run` connects, declares the exchange, starts that worker, then blocks until
    cancelled. :meth:`close` cancels the worker and closes the AMQP client.
    """

    def __init__(self, amqp_config: AmqpConfig, *, logger: logging.Logger) -> None:
        self._client = AmqpClient(amqp_config)
        self._logger = logger
        self._queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        await self._ensure_started()
        await asyncio.Future()

    async def _ensure_started(self) -> None:
        if self._worker_task is not None:
            return
        self._logger.info(
            "rabbitmq connecting broker=%s exchange=%r",
            redacted_amqp_url(self._client.config.url),
            self._client.default_exchange,
        )
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
        self._logger.info("rabbitmq publisher disconnecting")
        await self._client.close()
        self._logger.info("rabbitmq publisher stopped")

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
