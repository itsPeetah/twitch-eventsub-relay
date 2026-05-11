"""
Like ``main.py``, but forwards EventSub notifications to RabbitMQ.

The AMQP side is **publisher-only**: it opens a connection, obtains a channel,
and sends ``basic_publish``. It does **not** declare queues, bind queues, or
call ``basic_consume`` / ``start_consuming`` — nothing listens for broker
deliveries. On startup the client declares the configured exchange with
``exchange_declare`` (idempotent: creates a durable topic exchange if missing);
it does not declare queues or bindings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from pathlib import Path
from typing import Any, cast

import pika

from src import EventHandler, TwitchApp, load_amqp_config
from src.logging_setup import get_logger

_APP_DIR = Path(__file__).resolve().parent


class RabbitEventSink:
    """
    Publisher-only RabbitMQ client: enqueues EventSub payloads for ``basic_publish``
    on a worker thread so the asyncio EventSub loop stays non-blocking.
    No consumption: no queues, bindings, or ``basic_consume``. Ensures the
    outbound exchange exists via ``exchange_declare``, then only ``basic_publish``.
    """

    _STOP = object()

    def __init__(
        self,
        connection_url: str,
        *,
        exchange: str,
        logger: logging.Logger,
    ):
        self._url = connection_url
        self._exchange = exchange
        self._logger = logger
        self._q: queue.Queue[Any] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._worker,
            name="rabbitmq-eventsub-sink",
            daemon=True,
        )
        self._thread.start()

    def _worker(self) -> None:
        conn: pika.BlockingConnection | None = None
        try:
            conn = pika.BlockingConnection(pika.URLParameters(self._url))
            ch = conn.channel()
            ch.exchange_declare(
                exchange=self._exchange,
                exchange_type="topic",
                durable=True,
            )
            self._logger.info(
                "rabbitmq publisher ready (publish-only, exchange=%s type=topic durable)",
                self._exchange,
            )
            while True:
                item = self._q.get()
                if item is self._STOP:
                    break
                event_type, payload = cast(tuple[str, object], item)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                ch.basic_publish(
                    exchange=self._exchange,
                    routing_key=event_type,
                    body=body,
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=pika.DeliveryMode.Persistent,
                    ),
                )
        except Exception:
            self._logger.exception("rabbitmq worker failed")
            raise
        finally:
            if conn is not None and conn.is_open:
                conn.close()

    def publish_event(self, event_type: str, payload: object) -> None:
        self._logger.debug("publishing event type=%s payload=%s", event_type, payload)
        self._q.put((event_type, payload))

    def stop(self) -> None:
        self._q.put(self._STOP)
        if self._thread is not None:
            self._thread.join(timeout=10)


def main() -> None:
    logger = get_logger("twitch_authenticator_rabbitmq", _APP_DIR / "twitch.log")
    amqp = load_amqp_config(_APP_DIR / "amqp_config.json")

    sink = RabbitEventSink(amqp.url, exchange=amqp.exchange, logger=logger)
    sink.start()

    app = TwitchApp(
        config_path=_APP_DIR / "twitch_config.json",
        token_db_path=_APP_DIR / "tokens.sqlite",
        logger=logger,
        handler=EventHandler(sink.publish_event),
    )
    try:
        asyncio.run(app.run())
    finally:
        sink.stop()


if __name__ == "__main__":
    main()
