# Examples

Run scripts with an explicit path from the repository root (each script’s docstring notes path handling).

## Alternate EventSub entrypoints

Each loads Twitch config from the repo `config/` directory like root [`main.py`](../main.py), but only **one** sink:

| Script | Purpose |
|--------|---------|
| [`rabbit-python/main.py`](./rabbit-python/main.py) | EventSub → RabbitMQ only (`load_amqp_config` / JSON under `config/`). |
| [`websocket-python/main.py`](./websocket-python/main.py) | EventSub → WebSocket broadcaster only (`load_ws_config` / JSON under `config/`). |

## Small demos

Broker or WebSocket settings are built in code—no `amqp_config.json` / `ws_config.json` required for the demos themselves.

- [`rabbit-python/rabbitmq_consumer.py`](./rabbit-python/rabbitmq_consumer.py) — AMQP consumer ([`AmqpConfig`](../src/core/amqp/config.py) in code). Pair with a publisher (root `main.py --use-rabbitmq` or `rabbit-python/main.py`).
- [`websocket-python/subscriber_chat_message.py`](./websocket-python/subscriber_chat_message.py) — WebSocket client ([`WsConfig`](../src/core/websockets/config.py) in code). Pair with root `main.py --use-websockets` or `websocket-python/main.py`.
- [`websocket-web/`](./websocket-web/) — static page in the browser; serve over HTTP (see [README there](./websocket-web/README.md)). Connects to the broadcaster started by one of the processes above.
