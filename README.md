# Twitch Authenticator

## Twitch OAuth and Eventsub Client

In the [twitch module](./src/twitch/) you can find a raw implementation of the applications credentials oauth flow and the eventsub websocket service that do not depend on any external libraries.

The [app](./src/app.py) is the main entrypoint for the twitch related logic

## AMQP and RabbitMQ

Since I will use the notifications elsewhere and I am using RabbitMQ at work (although in Go) I have also implemented a Rabbit sink and consumer (the latter mainly used to test the former) to subscribe and receive the eventsub notifications from outside. Published messages use the EventSub subscription type as the topic routing key (for example `channel.chat.message`).

Implementation: [`src/rabbit/`](./src/rabbit/). Runnable samples: [`examples/rabbit-python/`](./examples/rabbit-python/).

## Usage

> Usage documentation was written by Cursor (and checked by me).

**What to run**

| What | Where | Role |
|------|--------|------|
| **Primary application** | [`main.py`](./main.py) at the **repository root** | Twitch OAuth + EventSub; optional stdout, RabbitMQ, and WebSocket broadcaster via flags (see below). |
| **Example programs** | [`examples/`](./examples/) | Alternate entrypoints (their own `main.py` scripts) and small subscriber/publisher demos. They are **not** the same file as root `main.py`. |

If docs say `python main.py`, that means the root file **after** `cd` to the repo root unless a path like `examples/rabbit-python/main.py` is given explicitly.

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

### Primary application (root `main.py`)

From the **repository root** (activate `.venv` if you use one). This is [`./main.py`](./main.py), not the `main.py` files under `examples/`.

```bash
python main.py
python main.py --use-rabbitmq
python main.py --use-websockets
python main.py --use-rabbitmq --use-websockets
python main.py --help
```

- **Default:** each EventSub notification is printed on stdout (JSON payload).
- **`--use-rabbitmq`:** also publishes to RabbitMQ using [`config/amqp_config.json`](./config/amqp_config.json). Copy [config/examples/amqp_config.example.json](./config/examples/amqp_config.example.json) there and adjust broker URL / exchange as needed. Optional keys **`reconnect_delay`**, **`reconnect_backoff`**, **`reconnect_max_retries`** (`null` = retry until the broker is up), and **`reconnect_max_delay`** control the initial TCP connect loop in [`AmqpClient`](src/amqp/client.py) when RabbitMQ is not ready yet.
- **`--use-websockets`:** also starts the WebSocket broadcaster using [`config/ws_config.json`](./config/ws_config.json). Copy [config/examples/ws_config.example.json](./config/examples/ws_config.example.json) there and adjust `host` / `port`. Clients choose which notification “channels” (opaque strings, typically Twitch subscription types such as `channel.chat.message`) to subscribe to after connecting.

To try **downstream** consumers (Rabbit subscriber, WebSocket subscriber, browser UI), use the [examples](#examples) section; those scripts are separate processes from root `main.py`.

### Examples

These live under [`examples/`](./examples/). Run them with an explicit path (from repo root or elsewhere—each example’s docstring notes path handling).

**Alternate EventSub entrypoints** (each loads Twitch config from the repo `config/` directory like root `main.py`, but only one sink):

| Script | Purpose |
|--------|---------|
| [`examples/rabbit-python/main.py`](./examples/rabbit-python/main.py) | EventSub → RabbitMQ only (`load_amqp_config` / JSON under `config/`). |
| [`examples/websocket-python/main.py`](./examples/websocket-python/main.py) | EventSub → WebSocket broadcaster only (`load_ws_config` / JSON under `config/`). |

**Small demos** (broker or WS settings built in code—no `amqp_config.json` / `ws_config.json` required for the demo itself):

- [`examples/rabbit-python/rabbitmq_consumer.py`](./examples/rabbit-python/rabbitmq_consumer.py) — AMQP consumer example ([`AmqpConfig`](src/amqp/config.py) in code). Pair with a publisher (root `main.py --use-rabbitmq` or `examples/rabbit-python/main.py`).
- [`examples/websocket-python/subscriber_chat_message.py`](./examples/websocket-python/subscriber_chat_message.py) — WebSocket client example ([`WsConfig`](src/websockets/config.py) in code). Pair with root `main.py --use-websockets` or `examples/websocket-python/main.py`.
- [`examples/websocket-web/`](./examples/websocket-web/) — static page in the browser; serve over HTTP (see README there). Connects to the broadcaster started by one of the processes above.

### Docker Compose (full stack)

Runs RabbitMQ, publishes EventSub notifications to AMQP, and exposes the WebSocket broadcaster. The `twitch_eventsub` service runs **repository root** `main.py` with `python main.py --use-rabbitmq --use-websockets` (see [`docker-compose.yml`](docker-compose.yml)).

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

**If you see `Connect call failed ('172.x.x.x', 5672)` or `Connection refused` to the `rabbitmq` service:** the broker often logs **`started TCP listener on [::]:5672`** while clients use **IPv4**. Compose mounts [`docker/rabbitmq/10-docker-compat.conf`](docker/rabbitmq/10-docker-compat.conf) so AMQP listens on **`0.0.0.0:5672`** and **`guest`** is allowed from other containers (`loopback_users.guest = false`). Recreate the RabbitMQ container after changing that file: `docker compose up -d --force-recreate rabbitmq`.

**If WebSocket clients on the host cannot connect** while logs show `ws://127.0.0.1:8765/`: bind inside the container is loopback-only. Ensure [`config/docker/ws_config.json`](./config/docker/ws_config.json) sets `"host": "0.0.0.0"` (default in repo). [`EventSubWebSocketBroadcaster`](src/websockets/server.py) logs a **warning** at startup when `host` is loopback-only so this mistake is obvious in stderr/logs.

**If you run on a Raspberry Pi (or any remote machine) and connect from a laptop:** use the Pi’s **LAN IP**, not `localhost` — e.g. `ws://192.168.1.42:8765/` from the laptop (find the IP with `hostname -I` on the Pi). Ensure **`ws_config.json`** uses **`"host": "0.0.0.0"`** (Compose ships [`config/docker/ws_config.json`](./config/docker/ws_config.json) that way). If you run **repository root** `main.py` directly on the Pi, [`config/ws_config.json`](./config/ws_config.json) is often copied from [ws_config.example.json](./config/examples/ws_config.example.json), which defaults to **`127.0.0.1`** and blocks remote clients until you change it. Open the firewall if needed: e.g. `sudo ufw allow 8765/tcp`. Compose publishes **`0.0.0.0:8765`** so Docker listens on all interfaces on the Pi (see [`docker-compose.yml`](docker-compose.yml)).

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

Set **`TWITCH_DEBUG=1`** for more verbose application logging. Set **`NO_LOGS=1`** to skip timestamped files under `logs/` (stderr only); see [`src/logger/app_logger.py`](src/logger/app_logger.py). Compose enables this by default on **`twitch_eventsub`** ([`docker-compose.yml`](docker-compose.yml)); use the same variable when running **root** `main.py` locally. [`docker-entrypoint.sh`](docker-entrypoint.sh) respects `NO_LOGS` in the container.