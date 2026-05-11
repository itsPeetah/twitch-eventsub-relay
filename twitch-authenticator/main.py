import asyncio
import json
from pathlib import Path

from src import EventHandler, TwitchApp
from src.logging_setup import get_logger

_APP_DIR = Path(__file__).resolve().parent


def print_eventsub_event(event_type: str, payload: object) -> None:
    """Default business sink: print each EventSub notification to stdout."""
    print(f"[event] {event_type} {json.dumps(payload, ensure_ascii=False)}")


if __name__ == "__main__":
    logger = get_logger("twitch_authenticator", _APP_DIR / "twitch.log")
    app = TwitchApp(
        config_path=_APP_DIR / "twitch_config.json",
        token_db_path=_APP_DIR / "tokens.sqlite",
        logger=logger,
        handler=EventHandler(print_eventsub_event),
    )
    asyncio.run(app.run())
