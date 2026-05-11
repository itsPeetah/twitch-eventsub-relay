from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class AmqpConfig:
    url: str
    exchange: str


def load_amqp_config(json_path: Path) -> AmqpConfig:
    """Load RabbitMQ connection settings from JSON (e.g. ``config/amqp_config.json``)."""
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


def redacted_amqp_url(url: str) -> str:
    """Broker endpoint without credentials (safe for application logs)."""
    try:
        p = urlparse(url)
        host = p.hostname or ""
        port = p.port
        if port is not None:
            return f"{p.scheme}://{host}:{port}/"
        return f"{p.scheme}://{host}/"
    except Exception:
        return "<amqp>"
