# Twitch Authenticator

## Twitch OAuth and Eventsub Client

In the [twitch module](./src/twitch/) you can find a raw implementation of the applications credentials oauth flow and the eventsub websocket service that do not depend on any external libraries.

The [app](./src/app.py) is the main entrypoint for the twitch related logic

## AMQP and RabbitMQ

Since I will use the notifications elsewhere and I am using RabbitMQ at work (although in Go) I have also implemented a Rabbit sink and consumer (the latter mainly used to test the former) to subscribe and receive the eventsub notifications from outside.

You can find those in the [rabbit examples](./examples/rabbit/)

## Usage

> Usage documentation was written by Cursor (and checked by me).

### Requirements

Python 3.10 or newer (the codebase uses modern typing syntax). Install dependencies from the repository root:

> My current working version is 3.14

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For tests:

```bash
pip install -r requirements-dev.txt
```

### Configuration

1. Copy [config/examples/twitch_config.example.json](./config/examples/twitch_config.example.json) to `config/twitch_config.json` and edit `scopes`, `oauth_redirect_uri`, and each subscription under `events` (types, versions, and `condition` fields must match [Twitch EventSub](https://dev.twitch.tv/docs/eventsub/) expectations).

2. Create a Twitch application in the [developer console](https://dev.twitch.tv/console/apps). Set the OAuth redirect URL to the same value as `oauth_redirect_uri` in your JSON (the example uses `http://localhost:4343/oauth/callback`).

3. Provide credentials via environment variables or a `.env` file. The loader prefers `config/.env` if it exists; otherwise it loads the `.env` in the project root (next to `config/`). Required variables:

   - `TWITCH_CLIENT_ID`
   - `TWITCH_CLIENT_SECRET`

Subscription `condition` fields use **numeric user IDs**, not display names or channel login names. Twitch’s own UI shows the login (the channel URL slug), not that internal ID. Look up the numbers with any Twitch **user ID finder** or **user ID lookup** site you are comfortable using: enter the channel login and paste the returned numeric IDs into `twitch_config.json`. For example, [StreamWeasels’ username → ID converter](https://www.streamweasels.com/tools/convert-twitch-username-to-user-id/).

### Running `main.py`

From the repository root (activate `.venv` if you use one):

```bash
python main.py
python main.py --use-rabbitmq
python main.py --use-websockets
python main.py --use-rabbitmq --use-websockets
python main.py --help
```

- **Default:** each EventSub notification is printed on stdout (JSON payload).
- **`--use-rabbitmq`:** also publishes to RabbitMQ using [`config/amqp_config.json`](./config/amqp_config.json). Copy [config/examples/amqp_config.example.json](./config/examples/amqp_config.example.json) there and adjust broker URL / exchange as needed.
- **`--use-websockets`:** also starts the WebSocket broadcaster using [`config/ws_config.json`](./config/ws_config.json). Copy [config/examples/ws_config.example.json](./config/examples/ws_config.example.json) there and adjust `host` / `port`. Clients choose which notification “channels” (opaque strings, typically Twitch subscription types such as `channel.chat.message`) to subscribe to after connecting. A minimal subscriber is [examples/websocket/subscriber_chat_message.py](./examples/websocket/subscriber_chat_message.py).

### Examples

Standalone demos (same config layout as above):

- [examples/rabbit/](./examples/rabbit/) — RabbitMQ publisher and consumer.
- [examples/websocket/](./examples/websocket/) — WebSocket broadcaster and chat subscriber client.

### Makefile and tests

```bash
make setup   # create .venv and pip install -r requirements-dev.txt
make test    # pytest
```

Set `TWITCH_DEBUG=1` for more verbose application logging.