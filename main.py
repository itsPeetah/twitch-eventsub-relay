import asyncio
import json
from pathlib import Path

from src import EventHandler, TwitchApp
from src.aioloop import AppLifecycle
from src.logger import AppLogger

_APP_DIR = Path(__file__).resolve().parent
_CONFIG_DIR = _APP_DIR / "config"


def print_eventsub_event(event_type: str, payload: object) -> None:
    """Default business sink: print each EventSub notification to stdout."""
    print(f"[event] {event_type} {json.dumps(payload, ensure_ascii=False)}")


async def main() -> None:
    logger = AppLogger.create(_APP_DIR, name="twitch_authenticator")
    app = TwitchApp(
        config_path=_CONFIG_DIR / "twitch_config.json",
        token_db_path=_APP_DIR / "tokens.sqlite",
        logger=logger,
        handler=EventHandler(print_eventsub_event),
    )
    async with AppLifecycle() as lifecycle:
        await lifecycle.run_interruptible(app.run())


if __name__ == "__main__":
    asyncio.run(main())
