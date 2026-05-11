from __future__ import annotations

from src.websockets.registry import ChannelSubscriptionRegistry


def test_registry_subscribe_peers_and_cleanup() -> None:
    reg = ChannelSubscriptionRegistry()
    a = object()
    b = object()

    reg.subscribe(a, ["channel.chat.message", "  ", "channel.follow"])
    reg.subscribe(b, ["channel.chat.message"])

    peers_chat = reg.peers_for("channel.chat.message")
    assert peers_chat == {a, b}
    assert reg.peers_for("channel.follow") == {a}
    assert sorted(reg.channels_for(a)) == ["channel.chat.message", "channel.follow"]

    reg.unsubscribe(a, ["channel.chat.message"])
    assert reg.peers_for("channel.chat.message") == {b}
    assert reg.peers_for("channel.follow") == {a}

    reg.remove_connection(a)
    assert reg.peers_for("channel.follow") == set()
    assert reg.channels_for(a) == frozenset()

    reg.remove_connection(b)
    assert reg.peers_for("channel.chat.message") == set()
