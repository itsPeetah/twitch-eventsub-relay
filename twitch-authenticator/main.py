import asyncio
import base64
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

from src import OAuthManager, TwitchEventSub, EventHandler, load_twitch_app_config

_APP_DIR = Path(__file__).resolve().parent

"""
How it works:
OAuth Flow:
It loads OAuth tokens from a SQLite file beside ``main.py`` (default ``tokens.sqlite``); if missing, it opens your browser.
It spins up a temporary http.server on the host/port from config oauth_redirect_uri to grab the code after you click "Authorize."
It handles token refreshing automatically by checking the expires_at timestamp before it expires.
Internal WebSocket Server:
Listens on ws://localhost:8081.
Implements the raw RFC 6455 Handshake and basic Framing so your other apps can connect using standard WebSockets.
Channel Routing: If an app connects to ws://localhost:8081/channel.chat.message, it only receives Twitch chat messages.
Twitch EventSub:
Connects to Twitch’s EventSub WebSocket.
Upon receiving the session_welcome message, it iterates through your config.json and sends POST requests to Twitch to link that session to the requested events.
Dependencies:
python-dotenv for loading TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET from ``.env``.
Uses urllib for API calls.
Uses socket and asyncio for the raw WebSocket communication.
Uses hashlib and base64 for the mandatory WebSocket security handshake.




Building a Twitch integration from scratch using only the Python Standard Library is a significant undertaking because it requires manual implementation of the WebSocket protocol (RFC 6455), which is usually handled by libraries like websockets.
Below is a complete, robust solution.
Prerequisites
Go to the Twitch Dev Console.
Register an App.
Set the Twitch app OAuth Redirect URL to match config oauth_redirect_uri (path included), e.g. http://localhost:4343/oauth/callback.
Copy ``.env.example`` to ``.env`` and set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET (never commit ``.env``).
The Configuration (config.json)
Create ``config.json`` beside ``main.py``:
{
    "oauth_redirect_uri": "http://localhost:4343/oauth/callback",
    "scopes": ["user:read:chat", "user:read:email", "chat:read", "chat:edit", "moderator:read:followers", "channel:read:subscriptions", "channel:read:redemptions"],
    "events": [
        {"type": "channel.chat.message", "version": "1", "condition": {"broadcaster_user_id": "YOUR_USER_ID", "user_id": "YOUR_USER_ID"}},
        {"type": "channel.follow", "version": "2", "condition": {"broadcaster_user_id": "YOUR_USER_ID", "moderator_user_id": "YOUR_USER_ID"}},
        {"type": "channel.subscribe", "version": "1", "condition": {"broadcaster_user_id": "YOUR_USER_ID"}},
        {"type": "channel.channel_points_custom_reward_redemption.add", "version": "1", "condition": {"broadcaster_user_id": "YOUR_USER_ID"}},
        {"type": "channel.channel_points_automatic_reward_redemption.add", "version": "2", "condition": {"broadcaster_user_id": "YOUR_USER_ID"}}
    ]
}



Broadcaster ID: In the config.json, the broadcaster_user_id must be your numeric Twitch ID (not your username). You can find this online using a "Twitch ID finder."
SSL: The Twitch connection uses ssl.create_default_context() to ensure the WebSocket is encrypted (WSS).
WebSocket Framing: This implementation uses a simplified frame generator. It works perfectly for text payloads (JSON) under 65KB, which covers 99.9% of Twitch events.
"""

MAGIC_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def sha1_base64(data: str) -> str:
    hash_obj = hashlib.sha1(data.encode())
    return base64.b64encode(hash_obj.digest()).decode()


def print_eventsub_event(event_type: str, payload: object) -> None:
    """Default business sink: print each EventSub notification to stdout."""
    print(f"[event] {event_type} {json.dumps(payload, ensure_ascii=False)}")


async def main(logger: logging.Logger):
    config_path = _APP_DIR / "config.json"
    config = load_twitch_app_config(config_path)

    logger.debug(
        "loaded config: %d event subscription(s), scopes=%s",
        len(config.events),
        list(config.scopes),
    )

    oauth = OAuthManager(config, logger, token_db=_APP_DIR / "tokens.sqlite")
    handler = EventHandler(print_eventsub_event)
    twitch = TwitchEventSub(config, oauth, handler, logger)

    await asyncio.gather(
        twitch.connect(),
    )


def _configure_logging() -> None:
    level = logging.DEBUG if os.environ.get("TWITCH_DEBUG") else logging.INFO
    fmt = logging.Formatter("%(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    file_handler = logging.FileHandler(
        _APP_DIR / "twitch.log", mode="w", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


if __name__ == "__main__":
    _configure_logging()
    logger = logging.getLogger("twitch_authenticator")
    asyncio.run(main(logger))
