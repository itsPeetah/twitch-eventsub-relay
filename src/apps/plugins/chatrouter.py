from __future__ import annotations

import logging

from aio_pika import ExchangeType

from src.core.plugins import EventSubPlugin
from src.core.rabbit import DeclareJob, RabbitAsyncPublisher
from src.core.websockets import EventSubWebSocketBroadcaster

logger = logging.getLogger(__name__)

CHAT_MESSAGE_EVENT_TYPE = "channel.chat.message"

# RabbitMQ
EXCHANGE_CHAT_COMMANDS = "chat::commands"
EXCHANGE_CHAT_MESSAGES = "chat::messages"

# WebSocket subscription channels (opaque strings)
WS_CHAT_COMMANDS_PREFIX = "chat::commands::"
WS_CHAT_MESSAGES_CHANNEL = "chat::messages"


def _extract_chat_text(event: dict) -> str:
    """Plain text from a ``channel.chat.message`` EventSub ``event`` object."""
    msg = event.get("message")
    if not isinstance(msg, dict):
        return ""
    if isinstance(msg.get("text"), str):
        return msg["text"]
    fragments = msg.get("fragments")
    if isinstance(fragments, list):
        parts: list[str] = []
        for frag in fragments:
            if (
                isinstance(frag, dict)
                and frag.get("type") == "text"
                and isinstance(frag.get("text"), str)
            ):
                parts.append(frag["text"])
        return "".join(parts)
    return ""


def _command_token(text: str) -> str | None:
    """
    Return the leading ``!command`` token (e.g. ``!clip``), or ``None`` if this is
    not treated as a chat command (no ``!``, or ``!`` only / empty body).
    """
    s = text.strip()
    if not s.startswith("!"):
        return None
    token = s.split(None, 1)[0]
    if len(token) < 2:
        return None
    return token


class ChatRouterPlugin(EventSubPlugin):
    """
    Routes ``channel.chat.message`` events only; ignores all other EventSub types.

    **RabbitMQ**

    - Command messages (leading ``!token``): JSON publish to topic exchange
      :data:`EXCHANGE_CHAT_COMMANDS` with routing key = that token (e.g. ``!clip``).
    - Every chat message: JSON publish to fanout exchange :data:`EXCHANGE_CHAT_MESSAGES`
      (routing key is ignored for fanout)—including command lines.

    **WebSocket**

    - Commands: also broadcast on ``chat::commands::<token>`` (e.g. ``chat::commands::!clip``).
    - Every chat message: broadcast on :data:`WS_CHAT_MESSAGES_CHANNEL`—including command lines.
    """

    def __init__(
        self,
        ws: EventSubWebSocketBroadcaster | None,
        rabbit: RabbitAsyncPublisher | None,
    ) -> None:
        declare_jobs: tuple[DeclareJob, ...] | None = None
        if rabbit is not None:
            declare_jobs = (
                DeclareJob(EXCHANGE_CHAT_COMMANDS, ExchangeType.TOPIC),
                DeclareJob(EXCHANGE_CHAT_MESSAGES, ExchangeType.FANOUT),
            )
        super().__init__(ws, rabbit, declare_jobs=declare_jobs)

    def handle(self, event_type: str, payload: object) -> None:
        if event_type != CHAT_MESSAGE_EVENT_TYPE:
            return
        if not isinstance(payload, dict):
            logger.debug("chatrouter skip non-dict payload")
            return

        text = _extract_chat_text(payload)
        cmd = _command_token(text)

        if cmd is not None:
            self.publish_rabbit(cmd, payload, exchange=EXCHANGE_CHAT_COMMANDS)
            self.broadcast_websocket(f"{WS_CHAT_COMMANDS_PREFIX}{cmd}", payload)
        
        self.publish_rabbit("", payload, exchange=EXCHANGE_CHAT_MESSAGES)
        self.broadcast_websocket(WS_CHAT_MESSAGES_CHANNEL, payload)
