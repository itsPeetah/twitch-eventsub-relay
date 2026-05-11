"""
Top-level package for Mali's overengineered stream tools.

Low-level, reusable building blocks (Twitch EventSub client, AMQP, WebSockets,
logging, asyncio lifecycle, etc.) live under :mod:`src.core`.

Higher-level application compositions can live under :mod:`src.apps`.
"""

from . import core, apps  # re-export namespaces

__all__ = ["core", "apps"]

