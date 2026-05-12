# Twitch EventSub Relay

> Because I like to overengineer stuff.

This repo contains a relay/orchestrator for Twitch's EventSub notifications.

By providing the desired subscriptions in the config file and the necessary scopes, it handles OAuth, connection upgrade and notification handling, relaying the messages to RabbitMQ exchanges and WebSocket broadcasts.

Apps downstream of this will be able to connect to the WebSocket server (subscribing to specific updates) or bind a queue to the desired Rabbit exchange(s) and receive the json payload of events, without having to worry about authenticating with Twitch.

> The system is thought to be run locally/inside a private network. It doesn't have any authentication, so I don't recommend deploying it publicly. I personally run it on my raspberry pi.

The relay does not do any preprocessing (e.g. stripping, reformatting...) of messages, and will just forward the message to the specified channels. Downstream applications will handle the parsing and processing of the received json payload.

## Twitch OAuth and Eventsub Client

In the core [twitch module](./src/core/twitch/) you can find a raw implementation of the applications credentials oauth flow and the EventSub WebSocket service that do not depend on any external libraries.

`[src/app.py](./src/app.py)` defines `[TwitchApp](./src/app.py)`—OAuth, token storage, and EventSub wiring—used by `[main.py](./main.py)` as the runnable entrypoint.

> The idea is authorize once and then forget about it. I chose to use sqlite as token storage rather than a plain json because, with this being a streaming tool, I wanted to increase the friction to accidentally leaking one's tokens on stream.

> Yeah I know I left my user ID in the config files, that mostly because I'm lazy but with how easy it is to get it using publicly available tools I am really not pressed about it.

## AMQP and RabbitMQ

Since I will use the notifications elsewhere and I am using RabbitMQ at work (although in Go) I have also implemented a Rabbit sink and consumer (the latter mainly used to test the former) to subscribe and receive the EventSub notifications from outside. Published messages use the EventSub subscription type as the topic routing key (for example `channel.chat.message`).

Implementation: [AMQP client](./src/core/amqp/) and [rabbit "publisher" module](./src/core/rabbit/).

## WebSocket Server

Since it's generally advised against subscribing to rabbit queues from the frontend, I decided to also add a [WebSocket server](./src/core/websockets/) to the sinks (this was mostly done for potential overlays).

Similarly to how Rabbit consumers bind their queue to an exchange, WebSocket client connections subscribe to channel/topics by sending a message like this to the server:

```json
{
  "op": "subscribe",
  "channels": ["channel_1", "channel_2"]
}
```

After which the will be notified for every event that matches.

## Async Loop Handling

This is uninteresting to most but the [AsyncIO wrapper module](./src/core/aioloop/) was mainly just built to handle `KeyboardInterrupt`s because I found it annoying to have to spam `CTRL+C` like two/three times and see exceptions clutter the CLI.

## Usage

### Installation and configuration

Check out [config.md](./config.md) for the installation instructions and overview of the config files.

> I recommend running this with docker compose after setting up the config files for the most "plug-n-play" experience.

### Plugins

By default the app used to just forward any eventsub message to the sinks.

I reworked it so that now it supports adding what I call "plugins", which are just a way to inject some business logic in the "orchestration loop" to shift some of the complexity from downstream apps up to the relay. Rather than only supporting a default amqp exchange/websocket topic, plugins can declare their own "channels" and conditionally forward messages through them (the default sinks have been refactored as plugins that just unconditionally send any message to the default "channels")

See more in [plugins.md](./plugins.md) for what the app already includes.

### Run natively (`main.py`)

From the **repository root** (activate `.venv` if you use one):

```bash
python main.py
python main.py --use-rabbitmq
python main.py --use-websockets
python main.py --use-rabbitmq --use-websockets
python main.py --help
```

- `--use-rabbitmq`: connects and publishes to RabbitMQ using `[config/amqp_config.json](./config/amqp_config.json)`.
  Optional keys `**reconnect_delay**`, `**reconnect_backoff**`, `**reconnect_max_retries**` (`null` = retry until the broker is up), and `**reconnect_max_delay**` control the initial TCP connect loop in `[AmqpClient](src/core/amqp/client.py)` when RabbitMQ is not ready yet.
- `--use-websockets`: also starts the WebSocket broadcaster using `[config/ws_config.json](./config/ws_config.json)`.
  Clients subscribe with JSON `{"op":"subscribe","channels":[...]}`. Raw EventSub traffic uses the `**eventsub::**` prefix plus the subscription type (e.g. `eventsub::channel.chat.message`). Routed chat/reward channels use the plugin prefixes above (`chat::…`, `reward::…`); see `[examples/websocket-web/plugins/README.md](./examples/websocket-web/plugins/README.md)`.

> The docker compose is configured to run `main.py` with both flags.

---

## AI use disclaimer

Some agentic AI tools (namely Cursor) were used to write the code for this repository, under strict design, vigilance and reviews by me. I am not a fan of using these tools but, as a professional software engineer, I also want to make sure I _can_ use them in case it becomes a requisite for my job and so I took on this project as a training opportunity.

While the code itself, as it exists right now, took a relatively short amount of time to generate+type, it is also true that I've also taken on this problem – making a twitch api client – a thousand times with python, nodejs and go, so I knew what I was doing/what I wanted to do different. The system design was thought of organically, so if it sucks you can blame me and not the clankers.

Before taking on this task I was convinced that these tools are not in a place where they can replace someone who knows what they're doing. As of writing this, I am even more convinced of this. While the code is for sure not perfect, getting it to a place where it's not a complete-spaghetti-clusterfuck took a lot of intent on my end and some strong steering of the slop machine.
