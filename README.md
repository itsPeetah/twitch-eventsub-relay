# Mali's Overengineered Stream Tools

## Twitch OAuth and Eventsub Client

In the core [twitch module](./src/core/twitch/) you can find a raw implementation of the applications credentials oauth flow and the EventSub WebSocket service that do not depend on any external libraries.

[`src/app.py`](./src/app.py) defines [`TwitchApp`](./src/app.py)—OAuth, token storage, and EventSub wiring—used by [`main.py`](./main.py) as the runnable entrypoint.

## AMQP and RabbitMQ

Since I will use the notifications elsewhere and I am using RabbitMQ at work (although in Go) I have also implemented a Rabbit sink and consumer (the latter mainly used to test the former) to subscribe and receive the EventSub notifications from outside. Published messages use the EventSub subscription type as the topic routing key (for example `channel.chat.message`).

Implementation: [`src/core/rabbit/`](./src/core/rabbit/). Runnable samples: [`examples/README.md`](./examples/README.md).

### Plugins

[`src/core/plugins/`](./src/core/plugins/) defines [`EventSubPlugin`](./src/core/plugins/base.py): EventSub sinks that receive optional [`EventSubWebSocketBroadcaster`](./src/core/websockets/server.py) and [`RabbitAsyncPublisher`](./src/core/rabbit/publisher.py) plus optional RabbitMQ [`DeclareJob`](./src/core/rabbit/publisher.py) declarations.

[`src/apps/plugins/`](./src/apps/plugins/) provides plugins registered by [`main.py`](./main.py), always together with stdout printing of each EventSub notification:

| Plugin | Role |
| ------ | ---- |
| [`DefaultEventSubSinkPlugin`](./src/apps/plugins/default_sink.py) | Pass-through: topic exchange **`twitch_eventsub`** (routing key = subscription type); WebSocket channels **`eventsub::<subscription_type>`** (see `WEBSOCKET_CHANNEL_PREFIX` in [`default_sink.py`](./src/apps/plugins/default_sink.py)), e.g. `eventsub::channel.chat.message`. |
| [`ChatRouterPlugin`](./src/apps/plugins/chatrouter.py) | Only **`channel.chat.message`**: topic **`chat::commands`** (routing key = `!token`), fanout **`chat::messages`**; WebSocket **`chat::commands::<token>`** and **`chat::messages`** (every chat line is broadcast on `chat::messages`; lines with a leading `!command` are also routed to the matching command channel). |
| [`RewardRouterPlugin`](./src/apps/plugins/rewardrouter.py) | Only **`channel.channel_points_custom_reward_redemption.add`**: topic **`reward::redemption`** (routing key = reward title), fanout **`reward::redemptions`**; WebSocket **`reward::redemptions`** and **`reward::redemptions::<title>`**. |

When RabbitMQ or WebSocket is disabled for a transport, the corresponding plugin calls for that transport are no-ops (same pattern as the default sink).

## Usage

> Usage documentation was written by Cursor (and checked by me).

**What to run**

| What                    | Where                                             | Role                                                                                                                                        |
| ----------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Primary application** | [`main.py`](./main.py) at the **repository root** | Twitch OAuth + EventSub; optional stdout, RabbitMQ, and WebSocket broadcaster via flags (see below).                                        |
| **Downstream demos**      | [`examples/README.md`](./examples/README.md)                  | Small **standalone** Rabbit/WebSocket clients (no `src.*` imports)—copy or adapt for other apps.                                           |

Run the CLI from the repo root: `python main.py ...`. Example scripts live under `examples/` (e.g. `examples/rabbit-python/rmq_example.py`).

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
  "reconnect_delay": 1.0,
  "reconnect_backoff": 2.0,
  "reconnect_max_retries": null,
  "reconnect_max_delay": 60.0
}
```

Connection-only JSON (exchange names are declared in code—see [`DefaultEventSubSinkPlugin`](./src/apps/plugins/default_sink.py), [`ChatRouterPlugin`](./src/apps/plugins/chatrouter.py), [`RewardRouterPlugin`](./src/apps/plugins/rewardrouter.py), and [`AmqpClient.declare_exchange`](./src/core/amqp/client.py)).

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

### Run natively (`main.py`)

From the **repository root** (activate `.venv` if you use one):

```bash
python main.py
python main.py --use-rabbitmq
python main.py --use-websockets
python main.py --use-rabbitmq --use-websockets
python main.py --help
```

- **Default:** each EventSub notification is printed on stdout (JSON payload). [`DefaultEventSubSinkPlugin`](./src/apps/plugins/default_sink.py), [`ChatRouterPlugin`](./src/apps/plugins/chatrouter.py), and [`RewardRouterPlugin`](./src/apps/plugins/rewardrouter.py) are always registered; if neither Rabbit nor WebSocket is enabled they no-op for those transports (chat/reward routers still only react to their respective EventSub types).
- `--use-rabbitmq`: connects and publishes to RabbitMQ using `[config/amqp_config.json](./config/amqp_config.json)`. Declares **`twitch_eventsub`** (topic; routing key = subscription type) plus the chat and reward exchanges when those plugins apply—see the plugins table above.
  > Optional keys `**reconnect_delay**`, `**reconnect_backoff**`, `**reconnect_max_retries**` (`null` = retry until the broker is up), and `**reconnect_max_delay**` control the initial TCP connect loop in [`AmqpClient`](src/core/amqp/client.py) when RabbitMQ is not ready yet.
- `--use-websockets`: also starts the WebSocket broadcaster using `[config/ws_config.json](./config/ws_config.json)`.
  > Clients subscribe with JSON `{"op":"subscribe","channels":[...]}`. Raw EventSub traffic uses the **`eventsub::`** prefix plus the subscription type (e.g. `eventsub::channel.chat.message`). Routed chat/reward channels use the plugin prefixes above (`chat::…`, `reward::…`); see [`examples/websocket-web/plugins/README.md`](./examples/websocket-web/plugins/README.md).

### Docker Compose (full stack)

RabbitMQ + `twitch_eventsub` running `main.py --use-rabbitmq --use-websockets`. See `[docker-compose.yml](./docker-compose.yml)` (network `stream_tools`).

**Setup:** Fill `[config/docker/](./config/docker/)` (see `[config/examples/*.docker.example.json](./config/examples/)`). For Compose credentials, copy [`env.compose.example`](./env.compose.example) to **`.env.compose`** (gitignored) and set `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` — `docker-compose.yml` loads it via **`env_file`**. Match the Twitch app redirect to `oauth_redirect_uri`, `touch tokens.sqlite`, then:

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
make run     # main.py --use-rabbitmq --use-websockets (after make install)
```

---

---

## AI use disclaimer

Some agentic AI tools (namely Cursor) were used to write the code for this repository, under strict vigilance and reviews by me. I am not a fan of using these tools but, as a professional software engineer, I also want to make sure I _can_ use them in case it becomes a requisite for my job and so I took on this project as a training opportunity.

While the code itself, as it exists right now, took a relatively short amount of time to generate+type, it is also true that I've also taken on this problem – making a twitch api client – a thousand times with python, nodejs and go, so I knew what I was doing/what I wanted to do different.

Before taking on this task I was convinced that these tools are not in a place where they can replace someone who knows what they're doing. As of writing this, I am even more convinced of this. While the code is for sure not perfect, getting it to a place where it's not a complete spaghetti cluster fuck took a lot of intent on my end and some strong steering of the slop machine.