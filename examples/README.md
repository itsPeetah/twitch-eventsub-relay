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

The browser demo [`websocket-web/`](./websocket-web/) pairs with the WebSocket server started by [`twitch_cli.py --use-websockets`](../twitch_cli.py) at the same host/port.
