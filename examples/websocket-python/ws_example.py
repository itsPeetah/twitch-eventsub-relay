#!/usr/bin/env python3
"""
Standalone WebSocket client example: connect to a broadcaster and subscribe to one channel.

No imports from this repository. Uses the ``eventsub::`` prefix plus subscription type
(e.g. ``eventsub::channel.chat.message``) so it matches servers that namespace EventSub
channels that way (see ``src.apps.plugins.default_sink``).

Requirements: ``pip install websockets`` (see repo ``requirements.txt``).

Example::

    python ws_example.py
    python ws_example.py --uri ws://192.168.1.10:8765/
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import socket
import sys
from urllib.parse import urlparse

from websockets.asyncio.client import connect

# Same convention as src.apps.plugins.default_sink.WEBSOCKET_CHANNEL_PREFIX
_EVENTSUB_CHANNEL_PREFIX = "eventsub::"
_DEFAULT_CHAT_CHANNEL = f"{_EVENTSUB_CHANNEL_PREFIX}channel.chat.message"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Subscribe to one WebSocket channel and print JSON messages.",
    )
    p.add_argument(
        "--uri",
        default="ws://127.0.0.1:8765/",
        help="WebSocket server URL",
    )
    p.add_argument(
        "--channel",
        default=_DEFAULT_CHAT_CHANNEL,
        help="Opaque channel string to subscribe to",
    )
    return p.parse_args()


def _tcp_kwargs(uri: str) -> dict:
    host = urlparse(uri).hostname
    if not host:
        return {}
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        return {}
    return {"family": socket.AF_INET}


async def _run(args: argparse.Namespace) -> None:
    tcp_kw = _tcp_kwargs(args.uri)
    print(
        f"Connecting to {args.uri!r} (tcp: {tcp_kw or 'default'})",
        file=sys.stderr,
    )

    async with connect(args.uri, **tcp_kw) as ws:
        await ws.send(
            json.dumps({"op": "subscribe", "channels": [args.channel]}),
        )
        print(
            f"Subscribed to {args.channel!r}; Ctrl+C to exit.",
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


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
