"""
Like ``main.py``, but forwards EventSub notifications to RabbitMQ.

Publishing uses asyncio + aio-pika: notifications are scheduled onto an
:class:`asyncio.Queue` from the EventSub coroutine and drained by an async worker
that awaits :meth:`AmqpClient.publish_json`, so the WebSocket loop never blocks on
the broker. Only the configured topic exchange is declared; no queues or
consumers are registered here.

SIGINT / SIGTERM (when supported) stop :meth:`TwitchApp.run`, drain the publish
worker, and close the broker connection—same pattern as :mod:`rabbitconsumer`.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

from src import AmqpClient, AmqpConfig, EventHandler, TwitchApp, load_amqp_config
from src.logging_setup import get_logger

_APP_DIR = Path(__file__).resolve().parent


class RabbitAsyncPublisher:
    """
    Bridges sync :class:`EventHandler` callbacks into async publishes: each call
    schedules a put on an :class:`asyncio.Queue`; :meth:`worker` awaits broker I/O.

    Call :meth:`setup` before starting :meth:`worker` (connects, declares the topic
    exchange, logs readiness—same role as :meth:`RabbitConsumer._setup`).
    """

    def __init__(self, amqp_config: AmqpConfig, *, logger: logging.Logger) -> None:
        self._client = AmqpClient(amqp_config)
        self._logger = logger
        self._queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    async def setup(self) -> None:
        await self._client.connect()
        await self._client.declare_topic_exchange()
        self._logger.info(
            "rabbitmq publisher ready (async publish-only, exchange=%s "
            "type=topic durable)",
            self._client.default_exchange,
        )

    async def close(self) -> None:
        await self._client.close()

    def publish_event(self, event_type: str, payload: object) -> None:
        self._logger.debug("publishing event type=%s payload=%s", event_type, payload)
        task = asyncio.create_task(self._enqueue(event_type, payload))
        task.add_done_callback(self._log_enqueue_failure)

    async def _enqueue(self, event_type: str, payload: object) -> None:
        await self._queue.put((event_type, payload))

    def _log_enqueue_failure(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            self._logger.exception("failed to enqueue message for RabbitMQ")

    async def worker(self) -> None:
        while True:
            event_type, payload = await self._queue.get()
            try:
                await self._client.publish_json(event_type, payload)
            except Exception:
                self._logger.exception(
                    "rabbitmq publish failed event_type=%s", event_type
                )


async def main() -> None:
    logger = get_logger("twitch_authenticator_rabbitmq", _APP_DIR / "twitch.log")
    amqp_cfg = load_amqp_config(_APP_DIR / "amqp_config.json")

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

    bridge = RabbitAsyncPublisher(amqp_cfg, logger=logger)
    worker_task: asyncio.Task[None] | None = None

    app = TwitchApp(
        config_path=_APP_DIR / "twitch_config.json",
        token_db_path=_APP_DIR / "tokens.sqlite",
        logger=logger,
        handler=EventHandler(bridge.publish_event),
    )

    try:
        await bridge.setup()
        worker_task = asyncio.create_task(bridge.worker())

        if installed_signals:
            app_task = asyncio.create_task(app.run())
            stop_task = asyncio.create_task(shutdown.wait())
            done, pending = await asyncio.wait(
                {app_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            await asyncio.gather(app_task, stop_task, return_exceptions=True)
            if not app_task.cancelled() and (exc := app_task.exception()):
                raise exc
        else:
            await app.run()
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        for sig in installed_signals:
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, RuntimeError, ValueError):
                pass
        await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
