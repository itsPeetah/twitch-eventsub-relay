from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractExchange

from .config import AmqpConfig


class AmqpClient:
    """
    Async AMQP session using ``aio_pika`` (non-blocking under asyncio).

    Publisher helpers: :meth:`declare_exchange`, :meth:`publish_json`.

    Use one instance per asyncio loop; do not share across threads.

    Logging is done by callers (e.g. :class:`~src.core.rabbit.RabbitAsyncPublisher`)
    using the application logger from :class:`~src.core.logger.AppLogger`.

    Initial TCP connect uses :attr:`~src.core.amqp.config.AmqpConfig.reconnect_delay`,
    :attr:`~src.core.amqp.config.AmqpConfig.reconnect_backoff`, and
    :attr:`~src.core.amqp.config.AmqpConfig.reconnect_max_retries` so startup can wait for
    the broker (``connect_robust`` still handles drops after the session is up).
    """

    def __init__(self, config: AmqpConfig) -> None:
        self._config = config
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None
        self._exchanges: dict[str, AbstractExchange] = {}

    @property
    def config(self) -> AmqpConfig:
        return self._config

    async def connect(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return
        await self._connect_with_retries()
        self._exchanges.clear()

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

    def _require_channel(self) -> aio_pika.RobustChannel:
        if self._channel is None:
            raise RuntimeError("AmqpClient.connect() must be awaited first")
        return self._channel

    async def declare_exchange(
        self,
        name: str,
        exchange_type: ExchangeType | str,
        *,
        durable: bool = True,
        auto_delete: bool = False,
        internal: bool = False,
        passive: bool = False,
        arguments: dict[str, Any] | None = None,
    ) -> AbstractExchange:
        """Declare an exchange of any standard AMQP type (idempotent)."""
        ch = self._require_channel()
        ex = await ch.declare_exchange(
            name,
            exchange_type,
            durable=durable,
            auto_delete=auto_delete,
            internal=internal,
            passive=passive,
            arguments=arguments,
        )
        self._exchanges[name] = ex
        return ex

    async def publish_json(
        self,
        routing_key: str,
        payload: object,
        *,
        exchange: str,
        persistent: bool = True,
    ) -> None:
        """Publish JSON as UTF-8 with ``content_type=application/json``."""
        ex = self._exchanges.get(exchange)
        if ex is None:
            raise RuntimeError(
                f"Exchange {exchange!r} is not declared; call declare_exchange first"
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
