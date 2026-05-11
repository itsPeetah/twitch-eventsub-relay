import asyncio
import base64
import json
import logging
import secrets
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .oauth_manager import OAuthManager
from .event_handler import EventHandler

WS_FIN = 0x80
WS_OP_CONT = 0x0
WS_OP_TEXT = 0x1
WS_OP_BINARY = 0x2
WS_OP_CLOSE = 0x8
WS_OP_PING = 0x9
WS_OP_PONG = 0xA

_WS_OP_NAMES = {
    WS_OP_CONT: "CONT",
    WS_OP_TEXT: "TEXT",
    WS_OP_BINARY: "BINARY",
    WS_OP_CLOSE: "CLOSE",
    WS_OP_PING: "PING",
    WS_OP_PONG: "PONG",
}


def _parse_wss_url(url: str) -> tuple[str, int, str]:
    u = urlparse(url)
    host = u.hostname
    if not host:
        raise ValueError(f"Invalid WebSocket URL: {url!r}")
    port = u.port or (443 if u.scheme in ("wss", "https") else 80)
    path = u.path or "/"
    if u.query:
        path = f"{path}?{u.query}"
    return host, port, path


def _build_masked_frame(opcode: int, payload: bytes, fin: bool = True) -> bytes:
    b0 = (WS_FIN if fin else 0) | (opcode & 0x0F)
    length = len(payload)
    mask_bit = 0x80
    if length < 126:
        header = bytes([b0, mask_bit | length])
    elif length < 65536:
        header = bytes([b0, mask_bit | 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([b0, mask_bit | 127]) + length.to_bytes(8, "big")
    key = secrets.token_bytes(4)
    masked = bytes(b ^ key[i % 4] for i, b in enumerate(payload))
    return header + key + masked


class TwitchEventSub:
    def __init__(
        self,
        config,
        oauth: OAuthManager,
        event_handler: EventHandler,
        logger: logging.Logger,
    ):
        self.config = config
        self.oauth = oauth
        self.event_handler = event_handler
        self.logger = logger
        self.session_id = None

    async def connect(self):
        url = "wss://eventsub.wss.twitch.tv/ws"
        self.logger.debug("connect() starting with url=%s", url)
        while True:
            next_url = await self._connect_once(url)
            if next_url:
                self.logger.info("following session_reconnect")
                url = next_url
                continue
            break

    async def _connect_once(self, wss_url: str) -> str | None:
        await asyncio.to_thread(self.oauth.get_token)

        host, port, path = _parse_wss_url(wss_url)
        self.logger.debug("tcp+tls %s:%s path=%s", host, port, path)
        ctx = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(
            host, port, ssl=ctx, server_hostname=host
        )

        key = base64.b64encode(secrets.token_bytes(16)).decode()
        headers = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        writer.write(headers.encode())
        await writer.drain()

        handshake = await reader.readuntil(b"\r\n\r\n")
        first_line = handshake.split(b"\r\n", 1)[0].decode("latin-1")
        parts = first_line.split(None, 2)
        if len(parts) < 2 or parts[1] != "101":
            writer.close()
            await writer.wait_closed()
            raise ConnectionError(f"WebSocket handshake failed: {first_line!r}")

        self.logger.debug("websocket handshake ok: %s", first_line)

        fragment: bytes | None = None

        try:
            while True:
                byte1_b = await reader.readexactly(1)
                byte2_b = await reader.readexactly(1)
                byte1 = byte1_b[0]
                byte2 = byte2_b[0]

                fin = bool(byte1 & WS_FIN)
                opcode = byte1 & 0x0F
                if byte1 & 0x70:
                    raise ConnectionError("Unexpected RSV bits in WebSocket frame")

                masked = bool(byte2 & 0x80)
                length = byte2 & 0x7F
                if length == 126:
                    length = int.from_bytes(await reader.readexactly(2), "big")
                elif length == 127:
                    length = int.from_bytes(await reader.readexactly(8), "big")

                if masked:
                    mask_key = await reader.readexactly(4)
                    raw_payload = await reader.readexactly(length)
                    payload = bytes(
                        raw_payload[i] ^ mask_key[i % 4] for i in range(len(raw_payload))
                    )
                else:
                    payload = await reader.readexactly(length)

                self.logger.debug(
                    "ws frame fin=%s opcode=%s(%s) len=%s masked=%s",
                    fin,
                    opcode,
                    _WS_OP_NAMES.get(opcode, "?"),
                    len(payload),
                    masked,
                )

                if opcode == WS_OP_PING:
                    self.logger.debug("replying with pong len=%s", len(payload))
                    writer.write(_build_masked_frame(WS_OP_PONG, payload))
                    await writer.drain()
                    continue
                if opcode == WS_OP_PONG:
                    continue
                if opcode == WS_OP_CLOSE:
                    code = 0
                    if len(payload) >= 2:
                        code = int.from_bytes(payload[:2], "big")
                    self.logger.info("WebSocket closed by server (code %s)", code)
                    return None

                if opcode == WS_OP_BINARY:
                    raise ConnectionError("Unexpected binary WebSocket frame")
                if opcode == WS_OP_TEXT:
                    if fragment is not None:
                        raise ConnectionError(
                            "New text frame before fragmented message finished"
                        )
                    fragment = payload
                elif opcode == WS_OP_CONT:
                    if fragment is None:
                        raise ConnectionError("Continuation without start")
                    fragment = fragment + payload
                else:
                    raise ConnectionError(f"Unsupported WebSocket opcode {opcode}")

                if not fin:
                    continue

                text = fragment.decode("utf-8")
                fragment = None
                msg = json.loads(text)
                reconnect = await self.handle_message(msg)
                if reconnect:
                    writer.close()
                    await writer.wait_closed()
                    return reconnect
        except asyncio.IncompleteReadError:
            self.logger.info("WebSocket connection closed (EOF)")
            return None
        finally:
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def handle_message(self, msg: dict) -> str | None:
        meta = msg.get("metadata", {})
        msg_type = meta.get("message_type")
        self.logger.debug(
            "eventsub message_type=%s id=%s",
            msg_type,
            meta.get("message_id"),
        )

        if msg_type == "session_welcome":
            self.session_id = msg["payload"]["session"]["id"]
            self.logger.info("EventSub connected session_id=%s", self.session_id)
            await self.subscribe_all_async()
            return None

        if msg_type == "notification":
            event_type = msg["metadata"]["subscription_type"]
            event_data = msg["payload"]["event"]
            self.logger.debug("notification subscription_version=%s", meta.get("subscription_version"))
            self.logger.info(
                "notification type=%s payload=%s",
                event_type,
                json.dumps(event_data, ensure_ascii=False),
            )
            self.event_handler.handle_event(event_type, event_data)
            return None

        if msg_type == "session_reconnect":
            url = msg["payload"]["session"].get("reconnect_url")
            self.logger.info("session_reconnect url=%s", url)
            return url

        if msg_type == "revocation":
            sub = msg["payload"]["subscription"]
            self.logger.warning(
                "subscription revoked type=%s status=%s",
                sub.get("type"),
                sub.get("status"),
            )
            return None

        if msg_type == "session_keepalive":
            self.logger.debug("session_keepalive")
            return None

        self.logger.debug("unhandled eventsub message_type=%s", msg_type)
        return None

    async def subscribe_all_async(self):
        self.logger.debug(
            "subscribe_all_async: %d event(s) session_id=%s",
            len(self.config.get("events", [])),
            self.session_id,
        )
        token = await asyncio.to_thread(self.oauth.get_token)
        tasks = [
            asyncio.to_thread(self._subscribe_one, token, event)
            for event in self.config["events"]
        ]
        await asyncio.gather(*tasks)

    def _subscribe_one(self, token: str, event: dict):
        self.logger.debug(
            "eventsub POST subscribe type=%s version=%s condition=%s",
            event.get("type"),
            event.get("version"),
            event.get("condition"),
        )
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
                self.logger.info("Subscribed to %s", event["type"])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")
            self.logger.error(
                "subscribe failed type=%s HTTP %s: %s",
                event["type"],
                e.code,
                err_body,
            )
