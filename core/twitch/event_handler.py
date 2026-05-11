from typing import Any, Callable


class EventHandler:
    def __init__(self, handle_func: Callable[..., Any]):
        self._handle_func = handle_func
    def handle_event(self, event_type: Any, event_data: Any):
        self._handle_func(event_type, event_data)
