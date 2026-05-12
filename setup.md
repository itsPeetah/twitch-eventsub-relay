# Installation and Configuration

I recommend running this inside of docker with `docker-compose` for the most plug-and-play experience.

## Local Installation

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

## Docker compose

**Setup:** Fill `[config/docker/](./config/docker/)` (see `[config/examples/*.docker.example.json](./config/examples/)`). For Compose credentials, copy [`env.compose.example`](./env.compose.example) to **`.env.compose`** (gitignored) and set `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` — `docker-compose.yml` loads it via **`env_file`**. Match the Twitch app redirect to `oauth_redirect_uri`, `touch tokens.sqlite`, then:

> If you have ssh access to the machine you're running the containers on you can also copy the `tokens.sqlite` db file to it with `scp` after authenticating once from your work machine.

```bash
docker compose up --build
```

Published ports:

| Port      | Service                        |
| --------- | ------------------------------ |
| **4343**  | OAuth callback                 |
| **8765**  | EventSub WebSocket broadcaster |
| **5672**  | RabbitMQ AMQP                  |
| **15672** | RabbitMQ management UI         |

---

## Configuration

Start from `[config/examples/](./config/examples/)` (full Twitch sample: `[twitch_config.example.json](./config/examples/twitch_config.example.json)`).

### Twitch — `config/twitch_config.json`

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

### WebSocket — `config/ws_config.json`

For `main.py --use-websockets`. Use `"host": "0.0.0.0"` if clients are not on localhost.

```json
{
  "host": "127.0.0.1",
  "port": 8765
}
```

### AMQP — `config/amqp_config.json`

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

## Environment variables

```sh
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
```

Optional:

```sh
TWITCH_DEBUG=1 # more verbose application logging.
NO_LOGS=1 # log to stderr only, no files under `logs/`
```
