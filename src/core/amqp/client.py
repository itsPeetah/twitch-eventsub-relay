from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractRobustQueue

from .config import AmqpConfig


class AmqpClient:
    """
    Async AMQP session using ``aio_pika`` (non-blocking under asyncio).

    Publisher helpers: :meth:`declare_topic_exchange`, :meth:`publish_json`.
    Consumer helpers: :meth:`declare_queue`, :meth:`bind_queue`,
    :meth:`set_qos_prefetch`, :meth:`basic_consume`.

    Use one instance per asyncio loop; do not share across threads.

    Logging is done by callers (e.g. :class:`~src.rabbit.RabbitAsyncPublisher`)
    using the application logger from :class:`~src.logger.AppLogger`.

    Initial TCP connect uses :attr:`~src.amqp.config.AmqpConfig.reconnect_delay`,
    :attr:`~src.amqp.config.AmqpConfig.reconnect_backoff`, and
    :attr:`~src.amqp.config.AmqpConfig.reconnect_max_retries` so startup can wait for
    the broker (``connect_robust`` still handles drops after the session is up).
    """

    def __init__(self, config: AmqpConfig) -> None:
        self._config = config
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None
        self._exchanges: dict[str, AbstractExchange] = {}
        self._queues: dict[str, AbstractRobustQueue] = {}

    @property
    def config(self) -> AmqpConfig:
        return self._config

    @property
    def default_exchange(self) -> str:
        return self._config.exchange

    async def connect(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return
        await self._connect_with_retries()
        self._exchanges.clear()
        self._queues.clear()

    async def _connect_with_retries(self) -> None:
        cfg = self._config
        log = logging.getLogger(__name__)
        delay = cfg.reconnect_delay
        attempt = 0
        last_exc: BaseException | None = None

        while True:
            attempt += 1
            conn: aio_pika.RobustConnection | None = None
            try:
                conn = await aio_pika.connect_robust(cfg.url)
                ch = await conn.channel()
                self._connection = conn
                self._channel = ch
                if attempt > 1:
                    log.info("amqp connected after %s failed attempt(s)", attempt - 1)
                return
            except BaseException as exc:
                last_exc = exc
                if conn is not None and not conn.is_closed:
                    await conn.close()
                if (
                    cfg.reconnect_max_retries is not None
                    and attempt >= 1 + cfg.reconnect_max_retries
                ):
                    log.error(
                        "amqp connect failed after %s attempt(s); giving up",
                        attempt,
                    )
                    assert last_exc is not None
                    raise last_exc
                wait_s = min(delay, cfg.reconnect_max_delay)
                cap = (
                    "unlimited"
                    if cfg.reconnect_max_retries is None
                    else str(1 + cfg.reconnect_max_retries)
                )
                log.warning(
                    "amqp connect failed (attempt %s of %s max): %s; retrying in %.2fs",
                    attempt,
                    cap,
                    exc,
                    wait_s,
                )
                await asyncio.sleep(wait_s)
                delay = min(delay * cfg.reconnect_backoff, cfg.reconnect_max_delay)

    async def close(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._exchanges.clear()
        self._queues.clear()

    def _require_channel(self) -> aio_pika.RobustChannel:
        if self._channel is None:
            raise RuntimeError("AmqpClient.connect() must be awaited first")
        return self._channel

    # --- Publisher-oriented -------------------------------------------------

    async def declare_topic_exchange(
        self,
        *,
        exchange: str | None = None,
        durable: bool = True,
    ) -> AbstractExchange:
        """Declare a topic exchange (idempotent). Returns the exchange handle."""
        ch = self._require_channel()
        name = exchange if exchange is not None else self._config.exchange
        ex = await ch.declare_exchange(name, ExchangeType.TOPIC, durable=durable)
        self._exchanges[name] = ex
        return ex

    async def publish_json(
        self,
        routing_key: str,
        payload: object,
        *,
        exchange: str | None = None,
        persistent: bool = True,
    ) -> None:
        """Publish JSON as UTF-8 with ``content_type=application/json``."""
        ex_name = exchange if exchange is not None else self._config.exchange
        ex = self._exchanges.get(ex_name)
        if ex is None:
            raise RuntimeError(
                f"Exchange {ex_name!r} is not declared; call declare_topic_exchange first"
            )

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        delivery_mode = (
            aio_pika.DeliveryMode.PERSISTENT
            if persistent
            else aio_pika.DeliveryMode.NOT_PERSISTENT
        )
        msg = aio_pika.Message(
            body,
            content_type="application/json",
            delivery_mode=delivery_mode,
        )
        await ex.publish(msg, routing_key=routing_key)

    # --- Consumer-oriented --------------------------------------------------

    async def declare_queue(
        self,
        queue: str,
        *,
        durable: bool = True,
        exclusive: bool = False,
        auto_delete: bool = False,
    ) -> AbstractRobustQueue:
        ch = self._require_channel()
        q = await ch.declare_queue(
            queue,
            durable=durable,
            exclusive=exclusive,
            auto_delete=auto_delete,
        )
        self._queues[queue] = q
        return q

    async def bind_queue(
        self,
        queue: str,
        routing_key: str,
        *,
        exchange: str | None = None,
    ) -> None:
        ex_name = exchange if exchange is not None else self._config.exchange
        ex = self._exchanges.get(ex_name)
        if ex is None:
            raise RuntimeError(
                f"Exchange {ex_name!r} is not declared; call declare_topic_exchange first"
            )
        q = self._queues.get(queue)
        if q is None:
            raise RuntimeError(
                f"Queue {queue!r} is not declared; call declare_queue first"
            )
        await q.bind(ex, routing_key=routing_key)

    async def set_qos_prefetch(
        self, prefetch_count: int, *, global_qos: bool = False
    ) -> None:
        await self._require_channel().set_qos(
            prefetch_count=prefetch_count,
            global_=global_qos,
        )

    async def basic_consume(
        self,
        queue: str,
        on_message_callback: Callable[
            [AbstractIncomingMessage],
            Awaitable[object],
        ],
        *,
        auto_ack: bool = False,
        consumer_tag: str | None = None,
    ) -> str:
        q = self._queues.get(queue)
        if q is None:
            raise RuntimeError(
                f"Queue {queue!r} is not declared; call declare_queue first"
            )
        return await q.consume(
            on_message_callback,
            no_ack=auto_ack,
            consumer_tag=consumer_tag,
        )
