from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

DEFAULT_OAUTH_REDIRECT_URI = "http://localhost:4343/oauth/callback"


@dataclass(frozen=True)
class EventSubSubscription:
    type: str
    version: str
    condition: dict[str, Any]


@dataclass(frozen=True)
class TwitchAppConfig:
    client_id: str
    client_secret: str
    oauth_redirect_uri: str
    scopes: tuple[str, ...]
    events: tuple[EventSubSubscription, ...]


def load_twitch_app_config(
    json_path: Path,
    *,
    dotenv_path: Path | None = None,
) -> TwitchAppConfig:
    """Load ``twitch_config.json`` and credentials from ``.env`` (via python-dotenv)."""
    env_path = dotenv_path if dotenv_path is not None else json_path.parent / ".env"
    load_dotenv(env_path)

    client_id = os.environ.get("TWITCH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            "Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in the environment or .env "
            f"(expected near {env_path})"
        )

    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    oauth_redirect_uri = raw.get("oauth_redirect_uri") or DEFAULT_OAUTH_REDIRECT_URI
    scopes_raw = raw.get("scopes")
    if not scopes_raw:
        raise ValueError("twitch_config.json must include a non-empty 'scopes' array")
    events_raw = raw.get("events")
    if not events_raw:
        raise ValueError("twitch_config.json must include a non-empty 'events' array")

    events = tuple(
        EventSubSubscription(
            type=e["type"],
            version=e["version"],
            condition=dict(e["condition"]),
        )
        for e in events_raw
    )

    return TwitchAppConfig(
        client_id=client_id,
        client_secret=client_secret,
        oauth_redirect_uri=oauth_redirect_uri,
        scopes=tuple(scopes_raw),
        events=events,
    )
