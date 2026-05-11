"""
Consume Twitch EventSub chat messages from RabbitMQ (asyncio + aio-pika).

Declares a durable queue bound to the exchange from ``amqp_config.json`` with
routing key ``channel.chat.message`` (topic exchange).
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
from pathlib import Path

from aio_pika.abc import AbstractIncomingMessage

from src import AmqpClient, AmqpConfig, load_amqp_config

_APP_DIR = Path(__file__).resolve().parent

ROUTING_KEY = "channel.chat.message"
QUEUE_NAME = "twitch_eventsub.channel.chat.message"


class RabbitConsumer:
    """Bind a durable queue and run an async consume loop until cancelled."""

    def __init__(
        self,
        *,
        amqp_config_path: Path | str,
        queue_name: str = QUEUE_NAME,
        routing_key: str = ROUTING_KEY,
        prefetch_count: int = 10,
    ) -> None:
        self._amqp_config_path = Path(amqp_config_path)
        self._queue_name = queue_name
        self._routing_key = routing_key
        self._prefetch_count = prefetch_count
        self._client: AmqpClient | None = None

    async def run(self) -> None:
        amqp_cfg = load_amqp_config(self._amqp_config_path)
        self._client = AmqpClient(amqp_cfg)
        await self._client.connect()

        shutdown = asyncio.Event()
        loop = asyncio.get_running_loop()
        installed_signals: list[int] = []
        for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
            if sig is None:
                continue
            try:
                loop.add_signal_handler(sig, shutdown.set)
                installed_signals.append(sig)
            except (NotImplementedError, RuntimeError, ValueError):
                pass

        try:
            await self._setup(amqp_cfg)
            if installed_signals:
                await shutdown.wait()
            else:
                await asyncio.Future()
        finally:
            for sig in installed_signals:
                try:
                    loop.remove_signal_handler(sig)
                except (NotImplementedError, RuntimeError, ValueError):
                    pass
            await self._shutdown()

    async def _setup(self, amqp_cfg: AmqpConfig) -> None:
        assert self._client is not None
        await self._client.declare_topic_exchange()
        await self._client.declare_queue(self._queue_name, durable=True)
        await self._client.bind_queue(self._queue_name, self._routing_key)
        await self._client.set_qos_prefetch(self._prefetch_count)

        await self._client.basic_consume(
            self._queue_name,
            self._on_message,
            auto_ack=False,
        )
        print(
            f"Consuming queue={self._queue_name!r} exchange={amqp_cfg.exchange!r} "
            f"routing_key={self._routing_key!r} (Ctrl+C to stop)",
            file=sys.stderr,
        )

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process():
            text = message.body.decode("utf-8")
            try:
                parsed = json.loads(text)
                print(json.dumps(parsed, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                print(text, file=sys.stdout)

    async def _shutdown(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


async def main() -> None:
    consumer = RabbitConsumer(amqp_config_path=_APP_DIR / "amqp_config.json")
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
