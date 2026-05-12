# Plugins

This app relays Twitch EventSub notifications to downstream consumers over RabbitMQ exchanges and WebSocket broadcasts. Plugins add relay-level routing logic to that flow: they receive each EventSub notification like a sink, can declare their own RabbitMQ exchanges, and can conditionally forward payloads to their own RabbitMQ and WebSocket channels.

## Plugin Interface

`[src/core/plugins/](./src/core/plugins/)` defines `[EventSubPlugin](./src/core/plugins/base.py)`, the base class for EventSub sink-like plugins. Subclasses implement `handle(event_type, payload)` and receive optional `[EventSubWebSocketBroadcaster](./src/core/websockets/server.py)` and `[RabbitAsyncPublisher](./src/core/rabbit/publisher.py)` instances. They may also provide RabbitMQ `[DeclareJob](./src/core/rabbit/publisher.py)` declarations, which are registered when RabbitMQ is enabled.

When RabbitMQ or WebSocket is disabled for a transport, the corresponding plugin calls for that transport are no-ops.

## Included Plugins

`[src/apps/plugins/](./src/apps/plugins/)` provides the plugins registered by `[main.py](./main.py)`, always together with stdout printing of each EventSub notification.

### Default EventSub Sink

`[DefaultEventSubSinkPlugin](./src/apps/plugins/default_sink.py)` is the pass-through plugin. (formerly the default sinks).

| SINK TYPE               | CHANNELNAME                     | ROUTING           | NOTES |
| ----------------------- | ------------------------------- | ----------------- | ----- |
| RabbitMQ topic exchange | `twitch_eventsub`               | Subscription type | -     |
| WebSocket channel       | `eventsub::<subscription_type>` | -                 | -     |

> For a comprehensive list of Twitch EventSub event types and their subscription parameters, refer to the [official Twitch documentation](https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/)

### Chat Router

`[ChatRouterPlugin](./src/apps/plugins/chatrouter.py)` handles only `**channel.chat.message**` notifications. Every chat line is broadcast on `chat::messages`; lines with a leading `!command` are also routed to the matching command channel.

| SINK TYPE                | CHANNELNAME               | ROUTING  | NOTES |
| ------------------------ | ------------------------- | -------- | ----- |
| RabbitMQ topic exchange  | `chat::commands`          | `!token` | -     |
| RabbitMQ fanout exchange | `chat::messages`          | -        | -     |
| WebSocket channel        | `chat::commands::<token>` | -        | -     |
| WebSocket channel        | `chat::messages`          | -        | -     |

### Reward Rout

`[RewardRouterPlugin](./src/ap/plugins/rewardrouter.py)` handles only `**channel.channel_points_custom_reward_redemption.add**` notifications
| SINK TYPE | CNNELNAME | ROUTING | NOTES |
| ------------------------ | -------------------------------- | ------------------ | ----------------------------------------------- |
| RabbitMQ topic exchange | `reward::redemption` | Reward title | This should probably be "direct", might change. |
| RabbitMQ fanout exchange | `reward::redemptions` | none (it's fanout) | - |
| WebSocket channel | `reward::redemptions` | - | - |
| WebSocket channel | `reward::redemptions::<title>` | - | - |
