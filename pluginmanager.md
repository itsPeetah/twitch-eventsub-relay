# Plugins (implemented)

- **Core:** [`src/core/plugins/`](./src/core/plugins/) — [`EventSubPlugin`](./src/core/plugins/base.py): `handle(event_type, payload)`, optional Rabbit [`DeclareJob`](./src/core/rabbit/publisher.py) list, injected `EventSubWebSocketBroadcaster` / `RabbitAsyncPublisher` (either may be `None`).
- **Apps:** [`src/apps/plugins/`](./src/apps/plugins/) — [`DefaultEventSubSinkPlugin`](./src/apps/plugins/default_sink.py): default topic exchange + publish/broadcast; WebSocket channels use prefix `eventsub::`.
- **Entry:** [`twitch_cli.py`](./twitch_cli.py) registers that plugin for every run.
