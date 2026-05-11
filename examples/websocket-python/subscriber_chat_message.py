"""
Example WebSocket **subscriber**: connects to the EventSub WS broadcaster and
subscribes only to ``channel.chat.message``.

Dial settings are built as a :class:`src.websockets.config.WsConfig` instance in code
(no JSON file).

Start the broadcaster first, e.g.::

    python examples/websocket-python/main.py

Then in another terminal::

    python examples/websocket-python/subscriber_chat_message.py

For literal IPv4 hosts, ``family=socket.AF_INET`` is passed to asyncio.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from websockets.asyncio.client import connect

from src import WsConfig

CHAT_CHANNEL = "channel.chat.message"
HOST="0.0.0.0"


def example_subscriber_ws_config() -> WsConfig:
    """Host/port of the running broadcaster (edit for your LAN / Pi)."""
    return WsConfig(host=HOST, port=8765)


def _create_connection_kwargs(uri: str) -> dict:
    host = urlparse(uri).hostname
    if not host:
        return {}
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        return {}
    return {"family": socket.AF_INET}


async def main() -> None:
    ws_cfg = example_subscriber_ws_config()
    uri = f"ws://{ws_cfg.host}:{ws_cfg.port}/"
    tcp_kw = _create_connection_kwargs(uri)
    print(f"Connecting to {uri!r} (tcp kwargs: {tcp_kw or 'default'})", file=sys.stderr)

    async with connect(uri, **tcp_kw) as ws:
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
