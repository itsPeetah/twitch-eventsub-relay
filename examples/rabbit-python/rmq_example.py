#!/usr/bin/env python3
"""
Standalone RabbitMQ consumer example: JSON messages from a topic exchange (asyncio + aio-pika).

No imports from this repository. Pair with any publisher that declares the exchange
(e.g. ``twitch_eventsub`` topic) and publishes with your chosen routing key.

Defaults match common EventSub bridges: exchange ``twitch_eventsub``, routing key
``channel.chat.message``. Each run creates a durable, auto-delete queue and binds
it so multiple processes each get a copy of matching messages.

Requirements: ``pip install aio-pika`` (see repo ``requirements.txt``).

Example::

    python rmq_example.py
    python rmq_example.py --url amqp://guest:guest@rabbitmq:5672/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Consume from a RabbitMQ topic exchange (passive declare).",
    )
    p.add_argument(
        "--url",
        default="amqp://guest:guest@127.0.0.1:5672/",
        help="AMQP connection URI",
    )
    p.add_argument(
        "--exchange",
        default="twitch_eventsub",
        help="Topic exchange name (must already exist on the broker)",
    )
    p.add_argument(
        "--routing-key",
        default="channel.chat.message",
        dest="routing_key",
        help="Routing key / subscription type to bind",
    )
    return p.parse_args()


async def _run(args: argparse.Namespace) -> None:
    conn = await aio_pika.connect_robust(args.url)
    try:
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=10)
        qname = f"twitch_eventsub.{secrets.token_hex(4)}"
        queue = await ch.declare_queue(qname, durable=True, auto_delete=True)
        ex = await ch.declare_exchange(args.exchange, ExchangeType.TOPIC, passive=True)
        await queue.bind(ex, routing_key=args.routing_key)

        print(
            f"queue={qname!r} exchange={args.exchange!r} routing_key={args.routing_key!r}; "
            "Ctrl+C to exit",
            file=sys.stderr,
        )

        async def on_message(message: AbstractIncomingMessage) -> None:
            async with message.process():
                text = message.body.decode("utf-8")
                try:
                    parsed = json.loads(text)
                    print(json.dumps(parsed, ensure_ascii=False, indent=2))
                except json.JSONDecodeError:
                    print(text)

        await queue.consume(on_message, no_ack=False)
        await asyncio.Future()
    finally:
        await conn.close()


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
