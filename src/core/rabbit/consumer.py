from __future__ import annotations

import asyncio
import json
import logging
import secrets
import sys
from typing import TextIO

from aio_pika.abc import AbstractIncomingMessage

from ..amqp.client import AmqpClient
from ..amqp.config import AmqpConfig, redacted_amqp_url

DEFAULT_CHAT_ROUTING_KEY = "channel.chat.message"
DEFAULT_CHAT_QUEUE_NAME = "twitch_eventsub.channel.chat.message"


def _ephemeral_consumer_queue_name() -> str:
    """Unique queue name per consumer instance (for fan-out via separate queues)."""
    return f"twitch_eventsub.{secrets.token_hex(4)}"


class RabbitConsumer:
    """
    AMQP consumer: declare queue, binding, then consume until cancelled.

    ``routing_key`` is the Twitch EventSub subscription type used when publishing
    to the topic exchange (same string as the publisher's routing key).

    If ``queue_name`` is omitted, each instance declares its own durable,
    auto-delete queue (unique name) so multiple consumers each receive a copy of
    matching messages; durable avoids RabbitMQ’s deprecated transient non-exclusive
    queue mode. Pass an explicit ``queue_name`` (for example
    :data:`DEFAULT_CHAT_QUEUE_NAME`) to share one queue and load-balance across
    consumers instead.

    Incoming JSON bodies are pretty-printed to ``out_stream``; non-JSON payloads are
    written as raw text. Operational messages use ``logger``.

    Call :meth:`AmqpClient.declare_exchange` (or a ``declare_*_exchange`` helper) on
    :attr:`client` before :meth:`run` if the binding target does not already exist.
    """

    def __init__(
        self,
        amqp_config: AmqpConfig,
        *,
        logger: logging.Logger,
        queue_name: str | None = None,
        routing_key: str = DEFAULT_CHAT_ROUTING_KEY,
        prefetch_count: int = 10,
        out_stream: TextIO | None = None,
    ) -> None:
        self._client = AmqpClient(amqp_config)
        self._logger = logger
        if queue_name is None:
            self._queue_name = _ephemeral_consumer_queue_name()
            # Durable + auto_delete: unique queue per process, removed when the
            # consumer disconnects; durable avoids deprecated transient_nonexcl_queues.
            self._queue_durable = True
            self._queue_auto_delete = True
        else:
            self._queue_name = queue_name
            self._queue_durable = True
            self._queue_auto_delete = False
        self._routing_key = routing_key
        self._prefetch_count = prefetch_count
        self._out_stream = out_stream if out_stream is not None else sys.stdout
        self._consume_started = False

    @property
    def client(self) -> AmqpClient:
        return self._client

    async def run(self, *, exchange: str) -> None:
        await self._ensure_started(exchange)
        await asyncio.Future()

    async def _ensure_started(self, exchange: str) -> None:
        if self._consume_started:
            return
        self._logger.info(
            "rabbitmq consumer connecting broker=%s exchange=%r",
            redacted_amqp_url(self._client.config.url),
            exchange,
        )
        await self._client.connect()
        await self._setup(exchange)
        self._consume_started = True

    async def close(self) -> None:
        self._logger.info("rabbitmq consumer disconnecting")
        await self._client.close()
        self._logger.info("rabbitmq consumer stopped")

    async def _setup(self, exchange: str) -> None:
        await self._client.declare_queue(
            self._queue_name,
            durable=self._queue_durable,
            auto_delete=self._queue_auto_delete,
        )
        await self._client.bind_queue(
            self._queue_name,
            self._routing_key,
            exchange=exchange,
        )
        await self._client.set_qos_prefetch(self._prefetch_count)

        await self._client.basic_consume(
            self._queue_name,
            self._on_message,
            auto_ack=False,
        )
        self._logger.info(
            "rabbitmq consumer ready queue=%r exchange=%r routing_key=%r "
            "(cancel task to stop)",
            self._queue_name,
            exchange,
            self._routing_key,
        )

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process():
            text = message.body.decode("utf-8")
            try:
                parsed = json.loads(text)
                print(
                    json.dumps(parsed, ensure_ascii=False, indent=2),
                    file=self._out_stream,
                )
            except json.JSONDecodeError:
                print(text, file=self._out_stream)
