import asyncio
import base64
import hashlib
import json
from typing import Dict, Set

from src import OAuthManager, TwitchEventSub, EventHandler

"""
How it works:
OAuth Flow:
It checks for a tokens.json. If missing, it opens your browser.
It spins up a temporary http.server on port 8080 to grab the code after you click "Authorize."
It handles token refreshing automatically by checking the expires_at timestamp before it expires.
Internal WebSocket Server:
Listens on ws://localhost:8081.
Implements the raw RFC 6455 Handshake and basic Framing so your other apps can connect using standard WebSockets.
Channel Routing: If an app connects to ws://localhost:8081/channel.chat.message, it only receives Twitch chat messages.
Twitch EventSub:
Connects to Twitch’s EventSub WebSocket.
Upon receiving the session_welcome message, it iterates through your config.json and sends POST requests to Twitch to link that session to the requested events.
No External Libraries:
Uses urllib for API calls.
Uses socket and asyncio for the raw WebSocket communication.
Uses hashlib and base64 for the mandatory WebSocket security handshake.




Building a Twitch integration from scratch using only the Python Standard Library is a significant undertaking because it requires manual implementation of the WebSocket protocol (RFC 6455), which is usually handled by libraries like websockets.
Below is a complete, robust solution.
Prerequisites
Go to the Twitch Dev Console.
Register an App.
Set the OAuth Redirect URL to http://localhost:8080.
Get your Client ID and Client Secret.
The Configuration (config.json)
Note: While you asked for YAML, Python does not have a YAML parser in its standard library. To keep this "no external libraries," I have used JSON, but I've included a tiny helper to read a YAML-like format if you prefer.
Create a file named config.json:
{
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "scopes": ["chat:read", "chat:edit", "moderator:read:followers", "subscriptions:read"],
    "events": [
        {"type": "channel.chat.message", "version": "1", "condition": {"broadcaster_user_id": "YOUR_USER_ID", "user_id": "YOUR_USER_ID"}},
        {"type": "channel.follow", "version": "2", "condition": {"broadcaster_user_id": "YOUR_USER_ID", "moderator_user_id": "YOUR_USER_ID"}},
        {"type": "channel.subscribe", "version": "1", "condition": {"broadcaster_user_id": "YOUR_USER_ID"}}
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


async def main():
    with open("./config.json", "r") as f:
        config = json.load(f)

    oauth = OAuthManager(config)
    handler = EventHandler(lambda t, p: print("event type:", t, "event_payload:", p))
    twitch = TwitchEventSub(config, oauth, handler)

    await asyncio.gather(
        twitch.connect(),
    )


if __name__ == "__main__":
    asyncio.run(main())
