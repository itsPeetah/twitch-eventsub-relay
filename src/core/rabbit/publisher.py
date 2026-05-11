from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass

from aio_pika import ExchangeType

from ..amqp import AmqpClient, AmqpConfig
from ..amqp.config import redacted_amqp_url


@dataclass(frozen=True)
class DeclareJob:
    """Broker exchange declaration to run after :meth:`AmqpClient.connect`."""
    name: str
    type: ExchangeType | str


@dataclass(frozen=True)
class PublishJob:
    """One JSON publish to ``exchange`` using ``routing_key`` (AMQP routing key)."""

    exchange: str
    routing_key: str
    payload: object


class RabbitAsyncPublisher:
    """
    Bridges sync ``EventHandler`` callbacks into async publishes:
    each call schedules a put on an :class:`asyncio.Queue`; a background task drains
    the queue and awaits :meth:`AmqpClient.publish_json`. The handler's first
    argument is used as the AMQP routing key (often EventSub subscription type).

    :meth:`run` connects, starts that worker, then blocks until cancelled.
    :meth:`close` cancels the worker and closes the AMQP client.

    Register exchange declarations with :meth:`register_declare_job`; they run
    right after connect, or immediately if the client is already connected.
    """

    def __init__(
        self,
        amqp_config: AmqpConfig,
        *,
        logger: logging.Logger,
    ) -> None:
        self._client = AmqpClient(amqp_config)
        self._logger = logger
        self._queue: asyncio.Queue[PublishJob] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._declare_job_queue: deque[DeclareJob] = deque()
        self._declare_lock = asyncio.Lock()
        self._connected = False

    async def run(self) -> None:
        await self._ensure_started()
        await asyncio.Future()

    async def _ensure_started(self) -> None:
        if self._worker_task is not None:
            return
        self._logger.info(
            "rabbitmq connecting broker=%s",
            redacted_amqp_url(self._client.config.url),
        )
        await self._client.connect()
        await self._drain_declare_jobs_locked()
        self._connected = True
        self._logger.info("rabbitmq publisher ready (async publish-only)")
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
        self._connected = False
        await self._client.close()
        self._logger.info("rabbitmq publisher stopped")

    @property
    def client(self) -> AmqpClient:
        return self._client

    def register_declare_job(self, name: str, type: ExchangeType | str) -> None:
        """Queue an exchange declaration (default declare options). Runs after connect, or immediately if already connected."""
        job = DeclareJob(name=name, type=type)
        self._declare_job_queue.append(job)
        if self._connected:
            asyncio.create_task(self._drain_declare_jobs_locked())

    async def _drain_declare_jobs_locked(self) -> None:
        async with self._declare_lock:
            while self._declare_job_queue:
                job = self._declare_job_queue.popleft()
                await self._run_declare_job(job)

    async def _run_declare_job(self, job: DeclareJob) -> None:
        await self._client.declare_exchange(job.name, job.type)

    def publish_event(self, routing_key: str, payload: object, *, exchange: str) -> None:
        self._logger.debug("publishing routing_key=%s payload=%s", routing_key, payload)
        task = asyncio.create_task(
            self._enqueue(
                PublishJob(exchange=exchange, routing_key=routing_key, payload=payload)
            )
        )
        task.add_done_callback(self._log_enqueue_failure)

    async def _enqueue(self, job: PublishJob) -> None:
        await self._queue.put(job)

    def _log_enqueue_failure(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            self._logger.exception("failed to enqueue message for RabbitMQ")

    async def _publish_worker(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._client.publish_json(
                    job.routing_key,
                    job.payload,
                    exchange=job.exchange,
                )
            except Exception:
                self._logger.exception(
                    "rabbitmq publish failed routing_key=%s", job.routing_key
                )
