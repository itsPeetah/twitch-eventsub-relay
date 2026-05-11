import asyncio
import base64
import json
import secrets
import ssl
import urllib.error
import urllib.request

from .oauth_manager import OAuthManager
from .event_handler import EventHandler


class TwitchEventSub:
    def __init__(self, config, oauth: OAuthManager, event_handler: EventHandler):
        self.config = config
        self.oauth = oauth
        self.event_handler = event_handler
        self.session_id = None

    async def connect(self):
        ctx = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(
            "eventsub.wss.twitch.tv", 443, ssl=ctx
        )

        key = base64.b64encode(secrets.token_bytes(16)).decode()
        headers = (
            "GET /ws HTTP/1.1\r\n"
            "Host: eventsub.wss.twitch.tv\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        writer.write(headers.encode())
        await writer.drain()

        await reader.readuntil(b"\r\n\r\n")

        while True:
            byte1 = await reader.read(1)
            if not byte1:
                break
            byte2 = await reader.read(1)
            length = byte2[0] & 127
            if length == 126:
                length = int.from_bytes(await reader.read(2), "big")
            elif length == 127:
                length = int.from_bytes(await reader.read(8), "big")

            payload = await reader.readexactly(length)
            msg = json.loads(payload.decode())
            await self.handle_message(msg)

    async def handle_message(self, msg):
        msg_type = msg.get("metadata", {}).get("message_type")

        if msg_type == "session_welcome":
            self.session_id = msg["payload"]["session"]["id"]
            print(f"[*] EventSub Connected. Session: {self.session_id}")
            self.subscribe_all()

        elif msg_type == "notification":
            event_type = msg["metadata"]["subscription_type"]
            event_data = msg["payload"]["event"]
            print(f"[Event] Received {event_type}")
            self.event_handler.handle_event(event_type, event_data)

    def subscribe_all(self):
        token = self.oauth.get_token()
        for event in self.config["events"]:
            body = json.dumps(
                {
                    "type": event["type"],
                    "version": event["version"],
                    "condition": event["condition"],
                    "transport": {
                        "method": "websocket",
                        "session_id": self.session_id,
                    },
                }
            ).encode()

            req = urllib.request.Request(
                "https://api.twitch.tv/helix/eventsub/subscriptions",
                data=body,
                headers={
                    "Client-ID": self.config["client_id"],
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req):
                    print(f"[*] Subscribed to {event['type']}")
            except urllib.error.HTTPError as e:
                print(f"[!] Error subscribing to {event['type']}: {e.read().decode()}")
