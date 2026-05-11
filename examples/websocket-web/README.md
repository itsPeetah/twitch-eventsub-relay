# WebSocket chat viewer (vanilla)

Small static page that connects to this repo’s **EventSub WebSocket broadcaster** (`EventSubWebSocketBroadcaster`), subscribes to **`eventsub::channel.chat.message`** (prefix matches [`DefaultEventSubSinkPlugin`](../../src/apps/plugins/default_sink.py) used by [`main.py --use-websockets`](../../main.py)), and appends each message to the page.

Each row uses a **black background**, **white** message text, and the **login/display name** tinted with the **`color`** field from the Twitch payload.

## Prerequisite

Run the Python broadcaster (from the repo root), e.g.:

```bash
python main.py --use-websockets
```

(from the repo root, with `config/ws_config.json` matching the URL in the page—default `ws://127.0.0.1:8765/`). Subscription channels must include the `eventsub::` prefix for notifications to match (see app.js).

## Serving the files

Browsers block some WebSocket setups from `file://`. Serve this folder over HTTP, for example with **`serve`** from npm:

```bash
cd examples/websocket-web
npx --yes serve .
```

Open the URL printed in the terminal (often `http://localhost:3000`). Click **Connect** (or set `?ws=ws://127.0.0.1:8765/` in the query string).

## Files

| File        | Role                                      |
| ----------- | ----------------------------------------- |
| `index.html` | Markup + toolbar (WS URL, connect buttons) |
| `styles.css` | Layout and chat line styling               |
| `app.js`     | WebSocket client + DOM updates             |

## All plugin channels

For a page that subscribes to the **default sink**, **chat router**, and **reward router** channels at once (with checkboxes and JSON log), see [`plugins/`](./plugins/README.md).
