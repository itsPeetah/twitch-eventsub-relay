# Twitch Authenticator

## Twitch OAuth and Eventsub Client

In the [twitch module](./src/twitch/) you can find a raw implementation of the applications credentials oauth flow and the eventsub websocket service that do not depend on any external libraries.

The [app](./src/app.py) is the main entrypoint for the twitch related logic

## AMQP and RabbitMQ

Since I will use the notifications elsewhere and I am using RabbitMQ at work (although in Go) I have also implemented a Rabbit sink and consumer (the latter mainly used to test the former) to subscribe and receive the eventsub notifications from outside. Published messages use the EventSub subscription type as the topic routing key (for example `channel.chat.message`).

You can find those in the [rabbit examples](./examples/rabbit-python/).

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

   Optional key **`oauth_callback_listen_host`**: HTTP bind address for the local OAuth callback server only. Omit it for normal desktop runs (the bind host is taken from `oauth_redirect_uri`). For Docker, keep `oauth_redirect_uri` as registered with Twitch (often `http://localhost:4343/oauth/callback`) and set `"oauth_callback_listen_host": "0.0.0.0"` so published port **4343** reaches the process inside the container. See [config/examples/twitch_config.docker.example.json](./config/examples/twitch_config.docker.example.json).

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
- **`--use-websockets`:** also starts the WebSocket broadcaster using [`config/ws_config.json`](./config/ws_config.json). Copy [config/examples/ws_config.example.json](./config/examples/ws_config.example.json) there and adjust `host` / `port`. Clients choose which notification “channels” (opaque strings, typically Twitch subscription types such as `channel.chat.message`) to subscribe to after connecting. A minimal Python subscriber is [examples/websocket-python/subscriber_chat_message.py](./examples/websocket-python/subscriber_chat_message.py); a small browser UI lives under [examples/websocket-web/](./examples/websocket-web/) (see its README).

### Examples

Standalone demos (same config layout as above):

- [examples/rabbit-python/](./examples/rabbit-python/) — RabbitMQ publisher (`main.py`) and chat consumer (`rabbitmq_consumer.py`).
- [examples/websocket-python/](./examples/websocket-python/) — WebSocket broadcaster (`main.py`) and chat subscriber client (`subscriber_chat_message.py`).
- [examples/websocket-web/](./examples/websocket-web/) — static page that connects to the broadcaster and renders chat (serve over HTTP; see README there).

### Docker Compose (full stack)

Runs RabbitMQ, publishes EventSub notifications to AMQP, and exposes the WebSocket broadcaster (`main.py --use-rabbitmq --use-websockets`).

**Files:** [`Dockerfile`](Dockerfile), [`docker-entrypoint.sh`](docker-entrypoint.sh), [`docker-compose.yml`](docker-compose.yml), [`.env.example`](.env.example).

Compose attaches **`rabbitmq`** and **`twitch_eventsub`** to a bridge network **`stream_tools`** so service DNS names (`rabbitmq`, `twitch_eventsub`) resolve between containers. Application logs go under **`./logs`** on the host (mounted at `/app/logs`; ensure that directory exists and is writable by the container user if logging fails).

**One-time setup**

1. Edit Compose-specific configs under **[`docker/config/`](./docker/config/)** (mounted read-only at `/app/config` in the container):
   - [`docker/config/twitch_config.json`](./docker/config/twitch_config.json) — replace placeholder Twitch IDs and subscriptions (`YOUR_*`).
   - [`docker/config/amqp_config.json`](./docker/config/amqp_config.json) — defaults target the Compose **`rabbitmq`** service (`rabbitmq:5672` inside the network).
   - [`docker/config/ws_config.json`](./docker/config/ws_config.json) — listens on **`0.0.0.0`** so published port **8765** works from the host.
   Snapshot templates also live under [`config/examples/`](./config/examples/) (`*.docker.example.json`) if you want to reset from copies.
2. Copy `.env.example` to `.env` next to `docker-compose.yml` and set `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET`. Optionally put secrets in **`docker/config/.env`** instead; `load_twitch_app_config` prefers `config/.env` beside the mounted JSON (`docker/config/.env` on the host).
3. Ensure Twitch app OAuth redirect matches **`oauth_redirect_uri`** in `docker/config/twitch_config.json` (typically `http://localhost:4343/oauth/callback`).
4. Create an empty token DB file so the bind mount stays a file (not a directory): `touch tokens.sqlite`
5. Create the logs directory on the host: `mkdir -p logs`

**Run**

```bash
docker compose up --build
```

**If you see `Connect call failed ('127.0.0.1', 5672)` or similar inside `twitch_eventsub`:** the app container’s **`localhost` is not RabbitMQ**. Ensure [`docker/config/amqp_config.json`](./docker/config/amqp_config.json) uses hostname **`rabbitmq`** (see [config/examples/amqp_config.docker.example.json](./config/examples/amqp_config.docker.example.json)). On your **host machine**, clients still use `localhost:5672` thanks to port publishing.

**If WebSocket clients on the host cannot connect** while logs show `ws://127.0.0.1:8765/`: bind inside the container is loopback-only. Ensure [`docker/config/ws_config.json`](./docker/config/ws_config.json) sets `"host": "0.0.0.0"` (default in repo).

Use **interactive** TTY (`stdin_open` / `tty` are enabled in Compose) for first-time OAuth: the app prints the Twitch authorize URL to stdout; complete login in your browser. Published ports:

| Port | Service |
|------|---------|
| **4343** | OAuth callback (must match `oauth_redirect_uri` port) |
| **8765** | EventSub WebSocket broadcaster (`ws://localhost:8765/` from host) |
| **5672** | RabbitMQ AMQP (`amqp://guest:guest@localhost:5672/` from host) |
| **15672** | RabbitMQ management UI (optional) |

Downstream apps on the host connect to **8765** and **5672** via `localhost`. Attach extra consumer containers to **`networks: [stream_tools]`** (see [`docker-compose.yml`](docker-compose.yml)) and use hostname **`rabbitmq`** for AMQP or **`twitch_eventsub`** for WebSockets (`8765`) without publishing ports on those consumers unless you need host access.

To use an external broker instead of the bundled RabbitMQ, remove or stop the `rabbitmq` service, point [`docker/config/amqp_config.json`](./docker/config/amqp_config.json) at your broker, and drop `depends_on` / healthcheck coupling from `twitch_eventsub` in your own override file.

### Makefile and tests

```bash
make setup   # create .venv and pip install -r requirements-dev.txt
make test    # pytest
```

Set `TWITCH_DEBUG=1` for more verbose application logging.