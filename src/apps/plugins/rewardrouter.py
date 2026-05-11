from __future__ import annotations

import logging

from aio_pika import ExchangeType

from src.core.plugins import EventSubPlugin
from src.core.rabbit import DeclareJob, RabbitAsyncPublisher
from src.core.websockets import EventSubWebSocketBroadcaster

logger = logging.getLogger(__name__)

# EventSub ``subscription_type`` for custom channel points reward redemptions.
CHANNEL_POINTS_REDEMPTION_EVENT_TYPE = (
    "channel.channel_points_custom_reward_redemption.add"
)

# RabbitMQ
EXCHANGE_REWARD_REDEMPTION = "reward::redemption"
EXCHANGE_REWARD_REDEMPTIONS = "reward::redemptions"

# WebSocket channels
WS_REWARD_REDEMPTIONS = "reward::redemptions"
WS_REWARD_REDEMPTIONS_TITLE_PREFIX = "reward::redemptions::"


def _reward_title(event: dict) -> str | None:
    """Reward title from a ``channel.channel_points_custom_reward_redemption.add`` event."""
    reward = event.get("reward")
    if not isinstance(reward, dict):
        return None
    title = reward.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


class RewardRouterPlugin(EventSubPlugin):
    """
    Routes ``channel.channel_points_custom_reward_redemption.add`` only.

    **RabbitMQ**

    - Topic :data:`EXCHANGE_REWARD_REDEMPTION` — routing key = reward title.
    - Fanout :data:`EXCHANGE_REWARD_REDEMPTIONS` — full redemption payload (routing key ignored).

    **WebSocket**

    - Broadcast on :data:`WS_REWARD_REDEMPTIONS`.
    - Broadcast on ``reward::redemptions::<title>`` (see :data:`WS_REWARD_REDEMPTIONS_TITLE_PREFIX`).
    """

    def __init__(
        self,
        ws: EventSubWebSocketBroadcaster | None,
        rabbit: RabbitAsyncPublisher | None,
    ) -> None:
        declare_jobs: tuple[DeclareJob, ...] | None = None
        if rabbit is not None:
            declare_jobs = (
                DeclareJob(EXCHANGE_REWARD_REDEMPTION, ExchangeType.TOPIC),
                DeclareJob(EXCHANGE_REWARD_REDEMPTIONS, ExchangeType.FANOUT),
            )
        super().__init__(ws, rabbit, declare_jobs=declare_jobs)

    def handle(self, event_type: str, payload: object) -> None:
        if event_type != CHANNEL_POINTS_REDEMPTION_EVENT_TYPE:
            return
        if not isinstance(payload, dict):
            logger.debug("rewardrouter skip non-dict payload")
            return

        title = _reward_title(payload)
        if title is None:
            logger.debug("rewardrouter skip redemption without reward.title")
            return

        self.publish_rabbit(title, payload, exchange=EXCHANGE_REWARD_REDEMPTION)
        self.publish_rabbit("", payload, exchange=EXCHANGE_REWARD_REDEMPTIONS)

        self.broadcast_websocket(WS_REWARD_REDEMPTIONS, payload)
        self.broadcast_websocket(
            f"{WS_REWARD_REDEMPTIONS_TITLE_PREFIX}{title}",
            payload,
        )
