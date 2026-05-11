"""
Forward Twitch EventSub notifications to subscribers over WebSockets.

Clients connect and send JSON such as
``{"op": "subscribe", "channels": ["channel.chat.message"]}`` to receive matching
events (channel strings are opaque to the server).

Run from anywhere (repo root is detected automatically), e.g.:

``python examples/websocket/main.py``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import EventHandler, EventSubWebSocketBroadcaster, TwitchApp, load_ws_config
from src.aioloop import AppLifecycle
from src.logger import AppLogger

_CONFIG_DIR = _PROJECT_ROOT / "config"


async def main() -> None:
    logger = AppLogger.create(_PROJECT_ROOT, name="twitch_authenticator_websocket")
    ws_cfg = load_ws_config(_CONFIG_DIR / "ws_config.json")

    bridge = EventSubWebSocketBroadcaster(ws_cfg, logger=logger)

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
