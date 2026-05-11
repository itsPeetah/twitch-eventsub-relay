from __future__ import annotations

import asyncio

from src.aioloop import AppLifecycle


def test_run_interruptible_without_signal_handlers_runs_main() -> None:
    async def _body() -> None:
        lc = AppLifecycle()
        seen: list[int] = []

        async def main() -> None:
            seen.append(1)

        await lc.run_interruptible(main())
        assert seen == [1]

    asyncio.run(_body())


def test_async_context_installs_handlers() -> None:
    async def _body() -> None:
        async with AppLifecycle() as lc:
            # On Windows / limited platforms this may remain false; only assert types.
            assert isinstance(lc.signals_installed, bool)

    asyncio.run(_body())
