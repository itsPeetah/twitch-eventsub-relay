from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

from .core.twitch import (
    EventHandler,
    OAuthManager,
    TwitchEventSub,
    combine_event_handlers,
    load_twitch_app_config,
    normalize_event_handlers,
)


class TwitchApp:
    """
    Wires Twitch OAuth, persisted tokens, and EventSub into :meth:`run`.

    ``handlers`` receive each notification as ``(event_type, payload)`` (see
    :class:`~src.twitch.event_handler.EventHandler`).
    """

    def __init__(
        self,
        config_path: Path | str,
        token_db_path: Path | str,
        logger: logging.Logger,
        handlers: EventHandler | Sequence[EventHandler],
    ):
        self.config_path = Path(config_path)
        self.token_db_path = Path(token_db_path)
        self.logger = logger
        self.handlers: tuple[EventHandler, ...] = normalize_event_handlers(handlers)

    async def run(self) -> None:
        config = load_twitch_app_config(self.config_path)

        self.logger.debug(
            "loaded config: %d event subscription(s), scopes=%s",
            len(config.events),
            list(config.scopes),
        )

        oauth = OAuthManager(config, self.logger, token_db=self.token_db_path)
        event_handler = (
            self.handlers[0]
            if len(self.handlers) == 1
            else combine_event_handlers(*self.handlers)
        )
        twitch = TwitchEventSub(config, oauth, event_handler, self.logger)

        await asyncio.gather(
            twitch.connect(),
        )
