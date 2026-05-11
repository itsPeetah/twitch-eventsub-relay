# Examples

Standalone scripts you can copy into **downstream apps**—they only use PyPI packages (`aio-pika`, `websockets`), not `src.*`.

| Script | Purpose |
|--------|---------|
| [`rabbit-python/rmq_example.py`](./rabbit-python/rmq_example.py) | Subscribe to a topic exchange (defaults: `twitch_eventsub`, routing key `channel.chat.message`). Expects the exchange to exist. |
| [`websocket-python/ws_example.py`](./websocket-python/ws_example.py) | WebSocket client; subscribes to `eventsub::channel.chat.message` by default. |

Run from the script’s directory or pass paths from the repo root, e.g.:

```bash
python examples/rabbit-python/rmq_example.py --help
python examples/websocket-python/ws_example.py --help
```

Browser demos (serve over HTTP, see each folder’s README):

- [`websocket-web/`](./websocket-web/) — chat-only viewer for `eventsub::channel.chat.message`.
- [`websocket-web/plugins/`](./websocket-web/plugins/) — subscribe to all plugin channel patterns and inspect JSON payloads.
