from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class AmqpConfig:
    url: str
    #: Seconds to wait after a failed connect before the first retry.
    reconnect_delay: float = 1.0
    #: Multiply the wait after each subsequent failure (capped by ``reconnect_max_delay``).
    reconnect_backoff: float = 2.0
    #: ``None`` = retry until connect succeeds. ``0`` = a single attempt (no retry).
    #: ``N`` = up to ``N`` retries after the first failure (``1 + N`` attempts total).
    reconnect_max_retries: int | None = None
    #: Upper bound on seconds between retry attempts.
    reconnect_max_delay: float = 60.0


def load_amqp_config(json_path: Path) -> AmqpConfig:
    """Load RabbitMQ connection settings from JSON (e.g. ``config/amqp_config.json``)."""
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    url = str(raw.get("url", "")).strip()
    if not url:
        raise ValueError(f"{json_path} must include a non-empty 'url' string")

    reconnect_delay = _float_opt(raw, "reconnect_delay", 1.0, json_path, min_value=0.0)
    if reconnect_delay <= 0:
        raise ValueError(f"{json_path}: reconnect_delay must be positive, got {reconnect_delay}")

    reconnect_backoff = _float_opt(raw, "reconnect_backoff", 2.0, json_path, min_value=1.0)
    if reconnect_backoff < 1.0:
        raise ValueError(
            f"{json_path}: reconnect_backoff must be >= 1.0, got {reconnect_backoff}"
        )

    reconnect_max_retries = _int_or_none_opt(raw, "reconnect_max_retries", json_path)

    reconnect_max_delay = _float_opt(
        raw, "reconnect_max_delay", 60.0, json_path, min_value=0.0
    )
    if reconnect_max_delay < reconnect_delay:
        raise ValueError(
            f"{json_path}: reconnect_max_delay ({reconnect_max_delay}) must be "
            f">= reconnect_delay ({reconnect_delay})"
        )

    return AmqpConfig(
        url=url,
        reconnect_delay=reconnect_delay,
        reconnect_backoff=reconnect_backoff,
        reconnect_max_retries=reconnect_max_retries,
        reconnect_max_delay=reconnect_max_delay,
    )


def _float_opt(
    raw: dict[str, Any],
    key: str,
    default: float,
    json_path: Path,
    *,
    min_value: float,
) -> float:
    if key not in raw:
        return default
    v = raw[key]
    try:
        out = float(v)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{json_path}: {key!r} must be a number") from e
    if out < min_value:
        raise ValueError(f"{json_path}: {key!r} must be >= {min_value}, got {out}")
    return out


def _int_or_none_opt(raw: dict[str, Any], key: str, json_path: Path) -> int | None:
    if key not in raw:
        return None
    v = raw[key]
    if v is None:
        return None
    try:
        n = int(v)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{json_path}: {key!r} must be an integer or null") from e
    if n < 0:
        raise ValueError(f"{json_path}: {key!r} must be >= 0, got {n}")
    return n


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
