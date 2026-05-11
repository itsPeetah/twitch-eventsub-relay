"""
Example WebSocket **subscriber**: connects to ``examples/websocket/main.py`` and
subscribes only to ``channel.chat.message``.

Start the broadcaster first::

    python examples/websocket/main.py

Then in another terminal::

    python examples/websocket/subscriber_chat_message.py

Uses bind settings from ``config/ws_config.json`` (same as the server example).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from websockets.asyncio.client import connect

from src import load_ws_config

_CONFIG_DIR = _PROJECT_ROOT / "config"

CHAT_CHANNEL = "channel.chat.message"


async def main() -> None:
    ws_cfg = load_ws_config(_CONFIG_DIR / "ws_config.json")
    uri = f"ws://{ws_cfg.host}:{ws_cfg.port}/"

    async with connect(uri) as ws:
        await ws.send(
            json.dumps({"op": "subscribe", "channels": [CHAT_CHANNEL]}),
        )
        print(
            f"Subscribed to {CHAT_CHANNEL!r}; waiting for messages (Ctrl+C to exit).",
            file=sys.stderr,
        )
        async for raw in ws:
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                print(raw, flush=True)
                continue
            print(json.dumps(msg, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
