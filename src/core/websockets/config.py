from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WsConfig:
    host: str
    port: int


def load_ws_config(json_path: Path) -> WsConfig:
    """Load WebSocket bind settings from JSON (e.g. ``config/ws_config.json``)."""
    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    host = str(raw.get("host", "")).strip()
    if not host:
        raise ValueError(f"{json_path} must include a non-empty 'host' string")

    port_raw = raw.get("port")
    try:
        port = int(port_raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{json_path} must include integer 'port'") from e

    if not (1 <= port <= 65535):
        raise ValueError(f"{json_path}: port must be between 1 and 65535, got {port}")

    return WsConfig(host=host, port=port)
