from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .twitch import EventHandler, OAuthManager, TwitchEventSub, load_twitch_app_config


class TwitchApp:
    def __init__(
        self,
        config_path: Path | str,
        token_db_path: Path | str,
        logger: logging.Logger,
        handler: EventHandler,
    ):
        self.config_path = Path(config_path)
        self.token_db_path = Path(token_db_path)
        self.logger = logger
        self.handler = handler

    async def run(self) -> None:
        config = load_twitch_app_config(self.config_path)

        self.logger.debug(
            "loaded config: %d event subscription(s), scopes=%s",
            len(config.events),
            list(config.scopes),
        )

        oauth = OAuthManager(config, self.logger, token_db=self.token_db_path)
        twitch = TwitchEventSub(config, oauth, self.handler, self.logger)

        await asyncio.gather(
            twitch.connect(),
        )
