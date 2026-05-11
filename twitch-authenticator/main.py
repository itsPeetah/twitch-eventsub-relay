import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from src import OAuthManager, TwitchEventSub, EventHandler, load_twitch_app_config

_APP_DIR = Path(__file__).resolve().parent

def print_eventsub_event(event_type: str, payload: object) -> None:
    """Default business sink: print each EventSub notification to stdout."""
    print(f"[event] {event_type} {json.dumps(payload, ensure_ascii=False)}")


async def main(logger: logging.Logger):
    config_path = _APP_DIR / "config.json"
    config = load_twitch_app_config(config_path)

    logger.debug(
        "loaded config: %d event subscription(s), scopes=%s",
        len(config.events),
        list(config.scopes),
    )

    oauth = OAuthManager(config, logger, token_db=_APP_DIR / "tokens.sqlite")
    handler = EventHandler(print_eventsub_event)
    twitch = TwitchEventSub(config, oauth, handler, logger)

    await asyncio.gather(
        twitch.connect(),
    )


def _configure_logging() -> None:
    level = logging.DEBUG if os.environ.get("TWITCH_DEBUG") else logging.INFO
    fmt = logging.Formatter("%(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    file_handler = logging.FileHandler(
        _APP_DIR / "twitch.log", mode="w", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


if __name__ == "__main__":
    _configure_logging()
    logger = logging.getLogger("twitch_authenticator")
    asyncio.run(main(logger))
