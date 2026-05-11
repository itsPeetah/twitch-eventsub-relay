from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import TextIO

from aio_pika.abc import AbstractIncomingMessage

from ..amqp import AmqpClient, AmqpConfig
from ..amqp.config import redacted_amqp_url

DEFAULT_CHAT_ROUTING_KEY = "channel.chat.message"
DEFAULT_CHAT_QUEUE_NAME = "twitch_eventsub.channel.chat.message"


class RabbitConsumer:
    """
    AMQP consumer: declare exchange, queue, binding, then consume until cancelled.

    Incoming JSON bodies are pretty-printed to ``out_stream``; non-JSON payloads are
    written as raw text. Operational messages use ``logger``.
    """

    def __init__(
        self,
        amqp_config: AmqpConfig,
        *,
        logger: logging.Logger,
        queue_name: str = DEFAULT_CHAT_QUEUE_NAME,
        routing_key: str = DEFAULT_CHAT_ROUTING_KEY,
        prefetch_count: int = 10,
        out_stream: TextIO | None = None,
    ) -> None:
        self._client = AmqpClient(amqp_config)
        self._logger = logger
        self._queue_name = queue_name
        self._routing_key = routing_key
        self._prefetch_count = prefetch_count
        self._out_stream = out_stream if out_stream is not None else sys.stdout
        self._consume_started = False

    async def run(self) -> None:
        await self._ensure_started()
        await asyncio.Future()

    async def _ensure_started(self) -> None:
        if self._consume_started:
            return
        self._logger.info(
            "rabbitmq consumer connecting broker=%s exchange=%r",
            redacted_amqp_url(self._client.config.url),
            self._client.default_exchange,
        )
        await self._client.connect()
        await self._setup()
        self._consume_started = True

    async def close(self) -> None:
        self._logger.info("rabbitmq consumer disconnecting")
        await self._client.close()
        self._logger.info("rabbitmq consumer stopped")

    async def _setup(self) -> None:
        await self._client.declare_topic_exchange()
        await self._client.declare_queue(self._queue_name, durable=True)
        await self._client.bind_queue(self._queue_name, self._routing_key)
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
            self._client.default_exchange,
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
