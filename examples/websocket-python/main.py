"""
Forward Twitch EventSub notifications to subscribers over WebSockets.

Clients connect and send JSON such as
``{"op": "subscribe", "channels": ["channel.chat.message"]}`` to receive matching
events (channel strings are opaque to the server).

Run from anywhere (repo root is detected automatically), e.g.:

``python examples/websocket-python/main.py``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.aioloop import AppLifecycle
from src.core.logger import AppLogger
from src.core.twitch import EventHandler
from src.core.websockets import EventSubWebSocketBroadcaster, load_ws_config
from src.app import TwitchApp

_CONFIG_DIR = _PROJECT_ROOT / "config"


async def main() -> None:
    app_log = AppLogger.create(_PROJECT_ROOT, name="twitch_authenticator_websocket")
    logger = app_log.logger
    ws_cfg = load_ws_config(_CONFIG_DIR / "ws_config.json")

    bridge = EventSubWebSocketBroadcaster(ws_cfg, logger=app_log.sub("websockets"))

    app = TwitchApp(
        config_path=_CONFIG_DIR / "twitch_config.json",
        token_db_path=_PROJECT_ROOT / "tokens.sqlite",
        logger=logger,
        handlers=EventHandler(bridge.handle_event),
    )

    async with AppLifecycle() as ctl:
        try:
            await ctl.run_interruptible(
                asyncio.gather(
                    bridge.run(),
                    app.run(),
                )
            )
        finally:
            await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
