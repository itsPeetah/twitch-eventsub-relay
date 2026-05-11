# WebSocket plugins inspector

Static page that subscribes to **all built-in plugin channel patterns** used by [`main.py --use-websockets`](../../../main.py) together with [`DefaultEventSubSinkPlugin`](../../../src/apps/plugins/default_sink.py), [`ChatRouterPlugin`](../../../src/apps/plugins/chatrouter.py), and [`RewardRouterPlugin`](../../../src/apps/plugins/rewardrouter.py).

Each notification is logged with its **`event_type`** (channel string) and formatted JSON **payload**.

## Default checkboxes

| Channel | Plugin |
| ------- | ------ |
| `eventsub::channel.chat.message` | Default sink — raw EventSub for that subscription type |
| `chat::messages` | Chat router — **all** chat lines (including `!commands`, which are also duplicated on `chat::commands::<token>`) |
| `chat::commands::!clip` | Chat router — example command (edit or add `chat::commands::!foo` in extras) |
| `reward::redemptions` | Reward router — every redemption |

Use **Extra channels** for per-reward titles, e.g. `reward::redemptions::Hydrate`, or more command routes (comma- or newline-separated). After you change checkboxes or the textarea while already connected, click **Apply subscriptions** so the server picks up the new list (you do not need to disconnect).

If a reward title contains a comma, put it on its own line and avoid comma-splitting inside that line (only newline-separated entries are safe for commas in titles).

## Prerequisite

```bash
python main.py --use-websockets
```

(`config/ws_config.json` host/port must match the URL in the page.)

## Serve locally

```bash
cd examples/websocket-web/plugins
npx --yes serve .
```

Open the printed URL; optional query `?ws=ws://127.0.0.1:8765/`.

## Files

| File | Role |
| ---- | ---- |
| `index.html` | URL, channel toggles, extra channels, log |
| `styles.css` | Layout + channel-prefix colors |
| `app.js` | Subscribe bundle + JSON log |
