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

Compose attaches **`rabbitmq`** and **`twitch_eventsub`** to a bridge network **`stream_tools`** so service DNS names (`rabbitmq`, `twitch_eventsub`) resolve between containers.

**NO_LOGS and file logging**

[`docker-compose.yml`](docker-compose.yml) sets **`NO_LOGS=1`** on **`twitch_eventsub`** so log output goes to **stderr only** and nothing is written under `logs/` (good for small disks, e.g. a Raspberry Pi). Behavior is implemented in [`src/logger/app_logger.py`](src/logger/app_logger.py) (`AppLogger`); [`docker-entrypoint.sh`](docker-entrypoint.sh) skips creating `/app/logs` when `NO_LOGS=1`.

To **persist timestamped log files** instead: remove `NO_LOGS` from Compose (or set it to something other than `1`), add volume `- ./logs:/app/logs` under `twitch_eventsub`, and run `mkdir -p logs` on the host. Override via `.env` only works if Compose passes the variable—either keep `NO_LOGS` in [`docker-compose.yml`](docker-compose.yml) or add it under `environment:` from your override file.

**One-time setup**

1. Edit Compose configs under **[`config/docker/`](./config/docker/)** (mounted read-only at `/app/config` in the container):
   - [`config/docker/twitch_config.json`](./config/docker/twitch_config.json) — replace placeholder Twitch IDs and subscriptions (`YOUR_*`).
   - [`config/docker/amqp_config.json`](./config/docker/amqp_config.json) — defaults target the Compose **`rabbitmq`** service (`rabbitmq:5672` inside the network).
   - [`config/docker/ws_config.json`](./config/docker/ws_config.json) — listens on **`0.0.0.0`** so published port **8765** works from the host.
   Templates also appear as [`config/examples/*.docker.example.json`](./config/examples/).
2. Copy `.env.example` to `.env` next to `docker-compose.yml` and set `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET`. Optionally put secrets in **`config/docker/.env`** instead; `load_twitch_app_config` prefers `.env` beside the mounted JSON (`config/docker/.env` on the host).
3. Ensure Twitch app OAuth redirect matches **`oauth_redirect_uri`** in `config/docker/twitch_config.json` (typically `http://localhost:4343/oauth/callback`).
4. Create an empty token DB file so the bind mount stays a file (not a directory): `touch tokens.sqlite`

**Smoke checks** (from the repository root; optional before a full stack run)

1. **Compose file + image build**

   ```bash
   docker compose config -q && docker compose build twitch_eventsub
   ```

2. **App container imports** (checks the Dockerfile and Python dependencies)

   ```bash
   docker compose run --rm --no-deps twitch_eventsub python -c "import src; print('import ok')"
   ```

3. **RabbitMQ** (network + healthcheck)

   ```bash
   docker compose up -d rabbitmq && docker compose exec rabbitmq rabbitmq-diagnostics -q ping && echo "rabbitmq ok"
   ```

   Stop when finished:

   ```bash
   docker compose down
   ```

4. **Full stack** (needs real setup): `.env` with Twitch credentials, edited [`config/docker/`](./config/docker/) JSON files, and `touch tokens.sqlite`. Default Compose uses **`NO_LOGS=1`** (no `./logs` volume); add `mkdir -p logs` and a logs bind mount only if you turn file logging back on (see **NO_LOGS and file logging** above). Then:

   ```bash
   docker compose up --build
   ```

After setup, use the same command for normal runs.

**If you see `Connect call failed ('127.0.0.1', 5672)` or similar inside `twitch_eventsub`:** the app container’s **`localhost` is not RabbitMQ**. Ensure [`config/docker/amqp_config.json`](./config/docker/amqp_config.json) uses hostname **`rabbitmq`** (see [config/examples/amqp_config.docker.example.json](./config/examples/amqp_config.docker.example.json)). On your **host machine**, clients still use `localhost:5672` thanks to port publishing.

**If WebSocket clients on the host cannot connect** while logs show `ws://127.0.0.1:8765/`: bind inside the container is loopback-only. Ensure [`config/docker/ws_config.json`](./config/docker/ws_config.json) sets `"host": "0.0.0.0"` (default in repo). [`EventSubWebSocketBroadcaster`](src/websockets/server.py) logs a **warning** at startup when `host` is loopback-only so this mistake is obvious in stderr/logs.

**If you run on a Raspberry Pi (or any remote machine) and connect from a laptop:** use the Pi’s **LAN IP**, not `localhost` — e.g. `ws://192.168.1.42:8765/` from the laptop (find the IP with `hostname -I` on the Pi). Ensure **`ws_config.json`** uses **`"host": "0.0.0.0"`** (Compose ships [`config/docker/ws_config.json`](./config/docker/ws_config.json) that way). If you run **`main.py` directly on the Pi**, [`config/ws_config.json`](./config/ws_config.json) is often copied from [ws_config.example.json](./config/examples/ws_config.example.json), which defaults to **`127.0.0.1`** and blocks remote clients until you change it. Open the firewall if needed: e.g. `sudo ufw allow 8765/tcp`. Compose publishes **`0.0.0.0:8765`** so Docker listens on all interfaces on the Pi (see [`docker-compose.yml`](docker-compose.yml)).

Use **interactive** TTY (`stdin_open` / `tty` are enabled in Compose) for first-time OAuth: the app prints the Twitch authorize URL to stdout; complete login in your browser. Published ports:

| Port | Service |
|------|---------|
| **4343** | OAuth callback (must match `oauth_redirect_uri` port) |
| **8765** | EventSub WebSocket broadcaster (`ws://localhost:8765/` on same machine; `ws://<Pi-LAN-IP>:8765/` from a laptop) |
| **5672** | RabbitMQ AMQP (`amqp://guest:guest@localhost:5672/` from host) |
| **15672** | RabbitMQ management UI (optional) |

Downstream apps on the host connect to **8765** and **5672** via `localhost`. Attach extra consumer containers to **`networks: [stream_tools]`** (see [`docker-compose.yml`](docker-compose.yml)) and use hostname **`rabbitmq`** for AMQP or **`twitch_eventsub`** for WebSockets (`8765`) without publishing ports on those consumers unless you need host access.

To use an external broker instead of the bundled RabbitMQ, remove or stop the `rabbitmq` service, point [`config/docker/amqp_config.json`](./config/docker/amqp_config.json) at your broker, and drop `depends_on` / healthcheck coupling from `twitch_eventsub` in your own override file.

### Makefile and tests

```bash
make setup   # create .venv and pip install -r requirements-dev.txt
make test    # pytest
```

Set **`TWITCH_DEBUG=1`** for more verbose application logging. Set **`NO_LOGS=1`** to skip timestamped files under `logs/` (stderr only); see [`src/logger/app_logger.py`](src/logger/app_logger.py). Compose enables this by default on **`twitch_eventsub`** ([`docker-compose.yml`](docker-compose.yml)); use the same variable when running **`main.py`** locally. [`docker-entrypoint.sh`](docker-entrypoint.sh) respects `NO_LOGS` in the container.