"""Stateful asyncio app lifecycle: signal-driven shutdown coordination."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Awaitable
from types import TracebackType


class AppLifecycle:
    """
    Stateful shutdown coordination for ``asyncio.run`` entrypoints.

    Holds the shared :class:`asyncio.Event`, installed signal numbers, and helpers
    to run work until interrupted by shutdown (see :meth:`run_interruptible`).

    Use as ``async with AppLifecycle() as lifecycle:`` to register handlers on
    entry and remove them on exit; :meth:`install` and :meth:`remove` stay
    available for custom lifetimes.
    """

    def __init__(self) -> None:
        self._shutdown = asyncio.Event()
        self._installed_signals: list[int] = []
        self._install_attempted = False

    async def __aenter__(self) -> AppLifecycle:
        self.install()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.remove()

    @property
    def shutdown(self) -> asyncio.Event:
        return self._shutdown

    @property
    def signals_installed(self) -> bool:
        return bool(self._installed_signals)

    def install(self) -> None:
        """
        Register SIGINT / SIGTERM to set :attr:`shutdown` when supported.

        Idempotent until :meth:`remove` is called. Must run inside a running
        event loop.
        """
        if self._install_attempted:
            return
        self._install_attempted = True
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
            if sig is None:
                continue
            try:
                loop.add_signal_handler(sig, self._shutdown.set)
                self._installed_signals.append(sig)
            except (NotImplementedError, RuntimeError, ValueError):
                pass

    def remove(self) -> None:
        """Remove handlers registered by :meth:`install`."""
        if not self._installed_signals:
            self._install_attempted = False
            return
        loop = asyncio.get_running_loop()
        for sig in self._installed_signals:
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, RuntimeError, ValueError):
                pass
        self._installed_signals.clear()
        self._install_attempted = False

    async def run_interruptible(self, main: Awaitable[None]) -> None:
        """
        Run ``main`` concurrently with :attr:`shutdown` when signals were
        installed; cancel whichever finishes second. If none were installed,
        simply ``await main``.
        """
        if not self.signals_installed:
            await main
            return

        main_task = asyncio.ensure_future(main)
        stop_task = asyncio.create_task(self._shutdown.wait())
        _, pending = await asyncio.wait(
            {main_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        await asyncio.gather(main_task, stop_task, return_exceptions=True)
        if main_task.cancelled():
            return
        try:
            exc = main_task.exception()
        except asyncio.CancelledError:
            return
        if exc is None:
            return
        # gather()/children often finish with CancelledError when we cancel after stop;
        # that is expected shutdown, not an application failure.
        if isinstance(exc, asyncio.CancelledError):
            return
        raise exc
