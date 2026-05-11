import asyncio
import json
from pathlib import Path

from core import EventHandler, TwitchApp
from core.aioloop import ShutdownLoop
from core.logging_setup import get_logger

_APP_DIR = Path(__file__).resolve().parent


def print_eventsub_event(event_type: str, payload: object) -> None:
    """Default business sink: print each EventSub notification to stdout."""
    print(f"[event] {event_type} {json.dumps(payload, ensure_ascii=False)}")


async def main() -> None:
    logger = get_logger("twitch_authenticator", _APP_DIR / "twitch.log")
    app = TwitchApp(
        config_path=_APP_DIR / "twitch_config.json",
        token_db_path=_APP_DIR / "tokens.sqlite",
        logger=logger,
        handler=EventHandler(print_eventsub_event),
    )
    async with ShutdownLoop() as ctl:
        await ctl.race_with_shutdown(app.run())


if __name__ == "__main__":
    asyncio.run(main())
