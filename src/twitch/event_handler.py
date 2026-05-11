"""Composable sinks for Twitch EventSub ``(event_type, event_data)`` callbacks."""

from collections.abc import Sequence
from typing import Any, Callable


class EventHandler:
    """Thin adapter around a callable ``handle_func(event_type, event_data)``."""

    def __init__(self, handle_func: Callable[..., Any]):
        self._handle_func = handle_func

    def handle_event(self, event_type: Any, event_data: Any):
        self._handle_func(event_type, event_data)


def combine_event_handlers(*handlers: EventHandler) -> EventHandler:
    """Return a single handler that forwards to each handler in order."""
    hs: tuple[EventHandler, ...] = tuple(handlers)
    if not hs:
        raise ValueError("combine_event_handlers requires at least one handler")
    if len(hs) == 1:
        return hs[0]

    def forward(event_type: Any, event_data: Any) -> None:
        for h in hs:
            h.handle_event(event_type, event_data)

    return EventHandler(forward)


def normalize_event_handlers(
    handlers: EventHandler | Sequence[EventHandler],
) -> tuple[EventHandler, ...]:
    """Return a non-empty tuple of handlers (wrap a single handler or validate a sequence)."""
    if isinstance(handlers, EventHandler):
        return (handlers,)
    t = tuple(handlers)
    if not t:
        raise ValueError("at least one EventHandler is required")
    return t
