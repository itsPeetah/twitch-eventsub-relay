(() => {
  "use strict";

  /** Matches WEBSOCKET_CHANNEL_PREFIX + subscription type (see src/apps/plugins/default_sink.py). */
  const CHANNEL = "eventsub::channel.chat.message";

  const elUrl = document.getElementById("ws-url");
  const elConnect = document.getElementById("btn-connect");
  const elDisconnect = document.getElementById("btn-disconnect");
  const elStatus = document.getElementById("status");
  const elChat = document.getElementById("chat");

  /** @type {WebSocket | null} */
  let ws = null;

  function setStatus(text, state) {
    elStatus.textContent = text;
    elStatus.dataset.state = state;
  }

  function appendChatLine(username, usernameColor, messageText) {
    const line = document.createElement("div");
    line.className = "chat-line";

    const userSpan = document.createElement("span");
    userSpan.className = "username";
    userSpan.textContent = username;
    userSpan.style.color = usernameColor || "#ffffff";

    const msgSpan = document.createElement("span");
    msgSpan.className = "message-text";
    msgSpan.textContent = messageText;

    line.append(userSpan, msgSpan);
    elChat.appendChild(line);
    line.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function extractChatText(payload) {
    const m = payload.message;
    if (m && typeof m.text === "string") return m.text;
    if (m && Array.isArray(m.fragments)) {
      return m.fragments
        .filter((f) => f && f.type === "text" && typeof f.text === "string")
        .map((f) => f.text)
        .join("");
    }
    return "";
  }

  function handleNotification(obj) {
    if (obj.event_type !== CHANNEL) return;
    const p = obj.payload;
    if (!p || typeof p !== "object") return;

    const username =
      (typeof p.chatter_user_name === "string" && p.chatter_user_name) ||
      (typeof p.chatter_user_login === "string" && p.chatter_user_login) ||
      "?";

    const color = typeof p.color === "string" ? p.color : "#ffffff";
    const text = extractChatText(p);

    appendChatLine(username, color, text);
  }

  function connect() {
    const url = elUrl.value.trim();
    if (!url) {
      setStatus("Enter a WebSocket URL", "error");
      return;
    }

    disconnect();

    setStatus("Connecting…", "connecting");
    elConnect.disabled = true;
    elDisconnect.disabled = false;

    try {
      ws = new WebSocket(url);
    } catch (e) {
      setStatus("Invalid URL", "error");
      elConnect.disabled = false;
      elDisconnect.disabled = true;
      return;
    }

    ws.addEventListener("open", () => {
      setStatus("Connected — subscribed to " + CHANNEL, "open");
      ws.send(JSON.stringify({ op: "subscribe", channels: [CHANNEL] }));
    });

    ws.addEventListener("message", (ev) => {
      if (typeof ev.data !== "string") return;
      let obj;
      try {
        obj = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (obj && typeof obj.event_type === "string") {
        handleNotification(obj);
      }
    });

    ws.addEventListener("close", () => {
      setStatus("Disconnected", "idle");
      ws = null;
      elConnect.disabled = false;
      elDisconnect.disabled = true;
    });

    ws.addEventListener("error", () => {
      setStatus("WebSocket error", "error");
    });
  }

  function disconnect() {
    if (ws) {
      ws.close();
      ws = null;
    }
    elConnect.disabled = false;
    elDisconnect.disabled = true;
    setStatus("Disconnected", "idle");
  }

  const params = new URLSearchParams(window.location.search);
  const qWs = params.get("ws");
  if (qWs) elUrl.value = qWs;

  elConnect.addEventListener("click", connect);
  elDisconnect.addEventListener("click", disconnect);
})();
