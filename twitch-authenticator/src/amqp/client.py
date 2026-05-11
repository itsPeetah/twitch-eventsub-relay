from __future__ import annotations

import json
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
        self._connection = await aio_pika.connect_robust(self._config.url)
        self._channel = await self._connection.channel()
        self._exchanges.clear()
        self._queues.clear()

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
