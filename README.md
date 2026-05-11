# Mali's Overengineered Stream Tools

## Twitch OAuth and Eventsub Client

In the [twitch module](./src/twitch/) you can find a raw implementation of the applications credentials oauth flow and the eventsub websocket service that do not depend on any external libraries.

The [app](./src/app.py) is the main entrypoint for the twitch related logic

## AMQP and RabbitMQ

Since I will use the notifications elsewhere and I am using RabbitMQ at work (although in Go) I have also implemented a Rabbit sink and consumer (the latter mainly used to test the former) to subscribe and receive the eventsub notifications from outside. Published messages use the EventSub subscription type as the topic routing key (for example `channel.chat.message`).

Implementation: [`src/rabbit/`](./src/rabbit/). Runnable samples: [`examples/README.md`](./examples/README.md).

## Usage

> Usage documentation was written by Cursor (and checked by me).

**What to run**

| What                    | Where                                             | Role                                                                                                                                        |
| ----------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Primary application** | `[main.py](./main.py)` at the **repository root** | Twitch OAuth + EventSub; optional stdout, RabbitMQ, and WebSocket broadcaster via flags (see below).                                        |
| **Example programs**    | [`examples/README.md`](./examples/README.md)      | Alternate entrypoints (their own `main.py` scripts) and small subscriber/publisher demos. They are **not** the same file as root `main.py`. |

If docs say `python main.py`, that means the root file **after** `cd` to the repo root unless a path like `examples/rabbit-python/main.py` is given explicitly.

### Installation

> **Required**: Python 3.10 or newer (the codebase uses modern typing syntax). Install dependencies from the repository root:

```sh
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For tests:

```sh
pip install -r requirements-dev.txt
```

---

### Configuration

Start from `[config/examples/](./config/examples/)` (full Twitch sample: `[twitch_config.example.json](./config/examples/twitch_config.example.json)`).

#### Twitch — `config/twitch_config.json`

> Match [EventSub](https://dev.twitch.tv/docs/eventsub/) for each subscription’s `type`, `version`, and `condition`. Use **numeric** user IDs in `condition` ([username → ID](https://www.streamweasels.com/tools/convert-twitch-username-to-user-id/)). In the [developer console](https://dev.twitch.tv/console/apps), set the app’s OAuth redirect to the same URL as `oauth_redirect_uri`.

```json
{
  "oauth_redirect_uri": "http://localhost:4343/oauth/callback",
  "scopes": ["user:read:chat", "chat:read"],
  "events": [
    {
      "type": "channel.chat.message",
      "version": "1",
      "condition": {
        "broadcaster_user_id": "12345678",
        "user_id": "87654321"
      }
    }
  ]
}
```

> Omit `oauth_callback_listen_host` on the desktop (bind follows `oauth_redirect_uri`). For Docker, add `"oauth_callback_listen_host": "0.0.0.0"` while keeping `oauth_redirect_uri` as registered with Twitch — see `[twitch_config.docker.example.json](./config/examples/twitch_config.docker.example.json)`.

#### WebSocket — `config/ws_config.json`

For `main.py --use-websockets`. Use `"host": "0.0.0.0"` if clients are not on localhost.

```json
{
  "host": "127.0.0.1",
  "port": 8765
}
```

#### AMQP — `config/amqp_config.json`

For `main.py --use-rabbitmq`. Optional `reconnect_*` fields control the initial broker connect loop; see `[amqp_config.example.json](./config/examples/amqp_config.example.json)`.

```json
{
  "url": "amqp://guest:guest@localhost:5672/",
  "exchange": "twitch_eventsub",
  "reconnect_delay": 1.0,
  "reconnect_backoff": 2.0,
  "reconnect_max_retries": null,
  "reconnect_max_delay": 60.0
}
```

---

### Environment variables

```sh
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
```

Optional:

```sh
TWITCH_DEBUG=1 # more verbose application logging.
NO_LOGS=1 # log to stderr only, no files under `logs/`
```

---

### Run natively (root `main.py`)

From the **repository root** (activate `.venv` if you use one). This is `[./main.py](./main.py)`, not the `main.py` files under `examples/`.

```bash
python main.py
python main.py --use-rabbitmq
python main.py --use-websockets
python main.py --use-rabbitmq --use-websockets
python main.py --help
```

- **Default:** each EventSub notification is printed on stdout (JSON payload).
- `--use-rabbitmq`: also publishes to RabbitMQ using `[config/amqp_config.json](./config/amqp_config.json)`.
  > Optional keys `**reconnect_delay`**, `**reconnect_backoff**`, `**reconnect_max_retries**` (`null`= retry until the broker is up), and`**reconnect_max_delay\*\*`control the initial TCP connect loop in`[AmqpClient](src/amqp/client.py)` when RabbitMQ is not ready yet.
- `--use-websockets`:also starts the WebSocket broadcaster using `[config/ws_config.json](./config/ws_config.json)`.
  > Clients choose which notification “channels” (opaque strings, typically Twitch subscription types such as `channel.chat.message`) to subscribe to after connecting.

### Docker Compose (full stack)

RabbitMQ + `twitch_eventsub` running root `main.py --use-rabbitmq --use-websockets`. See `[docker-compose.yml](./docker-compose.yml)` (network `stream_tools`).

**Setup:** Fill `[config/docker/](./config/docker/)` (see `[config/examples/*.docker.example.json](./config/examples/)`), `[.env](./.env)` from `[.env.example](./.env.example)` ([Environment variables](#environment-variables)), match the Twitch app redirect to `oauth_redirect_uri`, `touch tokens.sqlite`, then:

> If you have ssh access to the machine you're running the containers on you can also copy the `tokens.sqlite` db file to it with `scp` after authenticating once from your work machine.

```bash
docker compose up --build
```

Published ports:

| Port      | Service                           |
| --------- | --------------------------------- |
| **4343**  | OAuth callback                    |
| **8765**  | EventSub WebSocket broadcaster    |
| **5672**  | RabbitMQ AMQP                     |
| **15672** | RabbitMQ management UI (optional) |

### Makefile and tests

```bash
make setup   # create .venv and pip install -r requirements-dev.txt
make test    # pytest
```

---

---

## AI use disclaimer

Some agentic AI tools (namely Cursor) was used to write the code for this repository, under strict vigilance and reviews by me. I am not a fan of using these tools but, as a professional software engineer, I also want to make sure I _can_ use them in case it becomes a requisite for my job and so I took on this project as a training opportunity.

Before taking on this task I was convinced that these tools are not in a place where they can replace someone who knows what they're doing. As of writing this, I am even more convinced of this. While the code is for sure not perfect, getting it to a place where it's not a complete spaghetti cluster fuck took a lot of intent on my end and some strong steering of the slop machine.
