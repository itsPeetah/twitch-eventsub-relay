from __future__ import annotations

from collections.abc import Iterable


class ChannelSubscriptionRegistry:
    """
    Maps opaque channel strings to connections and tracks each connection's channels.

    Connections are compared by object identity (any hashable connection object works).
    """

    def __init__(self) -> None:
        self._conn_channels: dict[object, set[str]] = {}
        self._channel_peers: dict[str, set[object]] = {}

    def subscribe(self, conn: object, channels: Iterable[str]) -> None:
        subs = self._conn_channels.setdefault(conn, set())
        for raw in channels:
            ch = str(raw).strip()
            if not ch:
                continue
            subs.add(ch)
            self._channel_peers.setdefault(ch, set()).add(conn)

    def unsubscribe(self, conn: object, channels: Iterable[str]) -> None:
        subs = self._conn_channels.get(conn)
        if not subs:
            return
        for raw in channels:
            ch = str(raw).strip()
            if not ch:
                continue
            subs.discard(ch)
            peers = self._channel_peers.get(ch)
            if peers:
                peers.discard(conn)
                if not peers:
                    del self._channel_peers[ch]
        if not subs:
            del self._conn_channels[conn]

    def remove_connection(self, conn: object) -> None:
        subs = self._conn_channels.pop(conn, set())
        for ch in subs:
            peers = self._channel_peers.get(ch)
            if peers:
                peers.discard(conn)
                if not peers:
                    del self._channel_peers[ch]

    def peers_for(self, channel: str) -> set[object]:
        return set(self._channel_peers.get(channel.strip(), ()))

    def channels_for(self, conn: object) -> frozenset[str]:
        return frozenset(self._conn_channels.get(conn, ()))
