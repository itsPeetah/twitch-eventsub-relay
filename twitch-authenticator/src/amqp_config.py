from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AmqpConfig:
    url: str
    exchange: str


def load_amqp_config(json_path: Path) -> AmqpConfig:
    """Load RabbitMQ connection settings from ``amqp_config.json``."""
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    url = str(raw.get("url", "")).strip()
    if not url:
        raise ValueError(f"{json_path} must include a non-empty 'url' string")

    exchange_raw = raw.get("exchange", "twitch_eventsub")
    exchange = str(exchange_raw).strip() if exchange_raw else "twitch_eventsub"
    if not exchange:
        exchange = "twitch_eventsub"

    return AmqpConfig(url=url, exchange=exchange)
