# WebSocket chat viewer (vanilla)

Small static page that connects to this repo’s **EventSub WebSocket broadcaster** (`EventSubWebSocketBroadcaster`), subscribes to `channel.chat.message`, and appends each message to the page.

Each row uses a **black background**, **white** message text, and the **login/display name** tinted with the **`color`** field from the Twitch payload.

## Prerequisite

Run the Python broadcaster (from the repo root), e.g.:

```bash
python examples/websocket-python/main.py
```

Or use `python main.py --use-websockets` with `config/ws_config.json` pointing at the same host/port as the URL in the page (default `ws://127.0.0.1:8765/`).

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
