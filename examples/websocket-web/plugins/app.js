(() => {
  "use strict";

  /**
   * Default channels aligned with src/apps/plugins (main.py).
   * Chat commands are per-`!token`; adjust the example `!clip` row or use extras.
   * Reward per-title channels are `reward::redemptions::<title>` — add in textarea.
   */
  const PLUGIN_CHANNEL_DEFS = [
    {
      id: "ev-chat",
      channel: "eventsub::channel.chat.message",
      plugin: "DefaultEventSubSinkPlugin",
      description: "Raw EventSub stream (subscription type suffix)",
    },
    {
      id: "chat-msg",
      channel: "chat::messages",
      plugin: "ChatRouterPlugin",
      description: "All chat lines (commands also appear here)",
    },
    {
      id: "chat-cmd",
      channel: "chat::commands::!clip",
      plugin: "ChatRouterPlugin",
      description: "Example !command bucket (change !clip to your bot commands)",
    },
    {
      id: "rw-all",
      channel: "reward::redemptions",
      plugin: "RewardRouterPlugin",
      description: "All channel-points redemptions",
    },
  ];

  const elUrl = document.getElementById("ws-url");
  const elConnect = document.getElementById("btn-connect");
  const elDisconnect = document.getElementById("btn-disconnect");
  const elStatus = document.getElementById("status");
  const elLog = document.getElementById("log");
  const elChannelList = document.getElementById("channel-checkboxes");
  const elExtra = document.getElementById("extra-channels");
  const elApplySubs = document.getElementById("btn-apply-subs");

  /** @type {WebSocket | null} */
  let ws = null;

  /** @type {string[]} Channels last sent to the server (for unsubscribe/replace). */
  let lastSubscribedChannels = [];

  function setStatus(text, state) {
    elStatus.textContent = text;
    elStatus.dataset.state = state;
  }

  function channelTagClass(eventType) {
    if (eventType.startsWith("eventsub::")) return "ch-eventsub";
    if (eventType.startsWith("chat::")) return "ch-chat";
    if (eventType.startsWith("reward::")) return "ch-reward";
    return "ch-other";
  }

  function prependLog(eventType, payload) {
    const line = document.createElement("div");
    line.className = "log-line";

    const tag = document.createElement("span");
    tag.className = "channel-tag " + channelTagClass(eventType);
    tag.textContent = eventType;

    const pre = document.createElement("pre");
    pre.className = "payload";
    pre.textContent = JSON.stringify(payload, null, 2);

    line.append(tag, pre);
    elLog.prepend(line);
    elLog.scrollTop = 0;
  }

  function selectedChannels() {
    const fromChecks = [];
    elChannelList.querySelectorAll('input[type="checkbox"]:checked').forEach(
      (box) => {
        fromChecks.push(box.dataset.channel);
      },
    );
    const raw = elExtra.value.trim();
    const extras = [];
    if (raw) {
      for (const line of raw.split("\n")) {
        for (const part of line.split(",")) {
          const s = part.trim();
          if (s) extras.push(s);
        }
      }
    }
    const seen = new Set();
    const out = [];
    for (const c of [...fromChecks, ...extras]) {
      if (!seen.has(c)) {
        seen.add(c);
        out.push(c);
      }
    }
    return out;
  }

  /**
   * Replace server-side subscriptions for this connection.
   * Server merges subscribe calls; we unsubscribe the previous set first so removals stick.
   */
  function sendSubscriptions(channels) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return false;
    }
    if (channels.length === 0) {
      return false;
    }
    if (lastSubscribedChannels.length > 0) {
      ws.send(
        JSON.stringify({
          op: "unsubscribe",
          channels: [...lastSubscribedChannels],
        }),
      );
    }
    ws.send(JSON.stringify({ op: "subscribe", channels }));
    lastSubscribedChannels = [...channels];
    setStatus(
      "Connected — subscribed to " + channels.length + " channel(s)",
      "open",
    );
    return true;
  }

  function applySubscriptions() {
    const channels = selectedChannels();
    if (channels.length === 0) {
      setStatus("Select at least one channel or add extras", "error");
      return;
    }
    if (!sendSubscriptions(channels)) {
      setStatus("Not connected — connect first", "error");
    }
  }

  function buildChannelList() {
    for (const def of PLUGIN_CHANNEL_DEFS) {
      const li = document.createElement("li");
      li.className = "channel-row";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.id = def.id;
      cb.dataset.channel = def.channel;
      cb.checked = true;

      const meta = document.createElement("div");
      meta.className = "channel-meta";

      const label = document.createElement("label");
      label.htmlFor = def.id;
      label.className = "channel-name";
      label.textContent = def.channel;

      const badge = document.createElement("span");
      badge.className = "plugin-badge";
      badge.textContent = def.plugin + " — " + def.description;

      meta.append(label, badge);
      li.append(cb, meta);
      elChannelList.appendChild(li);
    }
  }

  function connect() {
    const url = elUrl.value.trim();
    if (!url) {
      setStatus("Enter a WebSocket URL", "error");
      return;
    }

    const channels = selectedChannels();
    if (channels.length === 0) {
      setStatus("Select at least one channel or add extras", "error");
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
      lastSubscribedChannels = [];
      sendSubscriptions(channels);
      elApplySubs.disabled = false;
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
        prependLog(obj.event_type, obj.payload);
      }
    });

    ws.addEventListener("close", () => {
      setStatus("Disconnected", "idle");
      ws = null;
      lastSubscribedChannels = [];
      elApplySubs.disabled = true;
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
    lastSubscribedChannels = [];
    elApplySubs.disabled = true;
    elConnect.disabled = false;
    elDisconnect.disabled = true;
    setStatus("Disconnected", "idle");
  }

  buildChannelList();

  const params = new URLSearchParams(window.location.search);
  const qWs = params.get("ws");
  if (qWs) elUrl.value = qWs;

  elConnect.addEventListener("click", connect);
  elDisconnect.addEventListener("click", disconnect);
  elApplySubs.addEventListener("click", applySubscriptions);
})();
