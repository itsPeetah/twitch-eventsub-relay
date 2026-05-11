"""
Consume Twitch EventSub chat messages from RabbitMQ.

Declares a durable queue bound to the exchange from ``amqp_config.json`` with
routing key ``channel.chat.message`` (topic exchange).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pika

from src import load_amqp_config

_APP_DIR = Path(__file__).resolve().parent

ROUTING_KEY = "channel.chat.message"
QUEUE_NAME = "twitch_eventsub.channel.chat.message"


def main() -> None:
    amqp = load_amqp_config(_APP_DIR / "amqp_config.json")

    connection = pika.BlockingConnection(pika.URLParameters(amqp.url))
    channel = connection.channel()

    channel.exchange_declare(
        exchange=amqp.exchange,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.queue_bind(
        exchange=amqp.exchange,
        queue=QUEUE_NAME,
        routing_key=ROUTING_KEY,
    )
    channel.basic_qos(prefetch_count=10)

    def on_message(
        ch: pika.channel.Channel,
        method: pika.spec.Basic.Deliver,
        properties: pika.spec.BasicProperties,
        body: bytes,
    ) -> None:
        text = body.decode("utf-8")
        try:
            parsed = json.loads(text)
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(text, file=sys.stdout)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)
    print(
        f"Consuming queue={QUEUE_NAME!r} exchange={amqp.exchange!r} "
        f"routing_key={ROUTING_KEY!r} (Ctrl+C to stop)",
        file=sys.stderr,
    )
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
