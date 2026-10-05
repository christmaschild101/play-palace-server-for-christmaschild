"""Tests for the server-side voice chat relay."""

import asyncio
import base64
import json

import pytest

from server.core.server import Server
from server.core.voice import LOBBY_ROOM, VoiceChannelMixin


def _frame(byte_count: int = 640, fill: int = 0) -> str:
    """Build a base64 PCM frame payload."""
    return base64.b64encode(bytes([fill] * byte_count)).decode("ascii")


class FakeConnection:
    """Records packets a client would have received."""

    def __init__(self):
        self.packets = []
        self.encoded = []

    async def send(self, packet):
        self.packets.append(packet)

    async def send_encoded(self, text):
        """Mirrors ClientConnection.send_encoded: relay already-serialized text."""
        self.encoded.append(text)
        self.packets.append(json.loads(text))

    def types(self):
        return [p["type"] for p in self.packets]

    def find(self, packet_type):
        return [p for p in self.packets if p["type"] == packet_type]


class FakeUser:
    """Minimal stand-in for NetworkUser."""

    def __init__(self, username, approved=True):
        self.username = username
        self.approved = approved
        self.connection = FakeConnection()
        self.spoken = []

    def speak_l(self, key, buffer="misc", **kwargs):
        self.spoken.append((key, kwargs))


class FakeMember:
    """Minimal stand-in for TableManager."""

    def __init__(self, tables=None):
        # username -> table_id
        self.tables = tables or {}

    def find_user_table(self, username):
        table_id = self.tables.get(username)
        if table_id is None:
            return None
        return type("FakeTable", (), {"table_id": table_id})()


@pytest.fixture
def channel():
    """Build a VoiceChannelMixin with fake users and tables."""
    channel = VoiceChannelMixin()
    channel._init_voice()
    channel._users = {}
    channel._tables = FakeMember()
    return channel


def _add(channel, username, table_id=None):
    user = FakeUser(username)
    channel._users[username] = user
    if table_id is not None:
        channel._tables.tables[username] = table_id
    return user


def _run(coro):
    return asyncio.run(coro)


# -- Rooms ----------------------------------------------------------------


def test_lobby_users_share_one_room(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")

    _run(channel._handle_voice_join(a, {"type": "voice_join"}))
    _run(channel._handle_voice_join(b, {"type": "voice_join"}))

    assert channel._voice_room_for("alice") == LOBBY_ROOM
    assert channel._voice_peers_in(LOBBY_ROOM) == ["alice", "bob"]


def test_table_members_are_isolated_from_lobby(channel):
    seated = _add(channel, "alice", table_id="t1")
    other = _add(channel, "bob", table_id="t2")
    lobby = _add(channel, "carol")

    for user in (seated, other, lobby):
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    assert channel._voice_room_for("alice") == "table:t1"
    assert channel._voice_peers_in("table:t1") == ["alice"]
    assert channel._voice_peers_in("table:t2") == ["bob"]
    assert channel._voice_peers_in(LOBBY_ROOM) == ["carol"]


def test_two_users_at_same_table_hear_each_other(channel):
    a = _add(channel, "alice", table_id="t1")
    b = _add(channel, "bob", table_id="t1")

    _run(channel._handle_voice_join(a, {"type": "voice_join"}))
    _run(channel._handle_voice_join(b, {"type": "voice_join"}))

    assert channel._voice_peers_in("table:t1", exclude="alice") == ["bob"]


# -- Join / leave announcements -------------------------------------------


def test_join_speaks_and_reports_room(channel):
    user = _add(channel, "alice")

    _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    assert user.spoken[0][0] == "voice-joined-lobby"
    status = user.connection.find("voice_status")[0]
    assert status["joined"] is True
    assert status["room"] == LOBBY_ROOM


def test_join_at_table_speaks_table_message(channel):
    user = _add(channel, "alice", table_id="t9")

    _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    assert user.spoken[0][0] == "voice-joined-table"


def test_join_announced_to_existing_members(channel):
    first = _add(channel, "alice")
    second = _add(channel, "bob")

    _run(channel._handle_voice_join(first, {"type": "voice_join"}))
    _run(channel._handle_voice_join(second, {"type": "voice_join"}))

    peers = first.connection.find("voice_peer")
    assert len(peers) == 1
    assert peers[0]["action"] == "joined"
    assert peers[0]["username"] == "bob"


def test_leave_announced_and_speaks(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    _run(channel._handle_voice_join(a, {"type": "voice_join"}))
    _run(channel._handle_voice_join(b, {"type": "voice_join"}))

    _run(channel._handle_voice_leave(a, {"type": "voice_leave"}))

    # Bob joined second, so only Alice's departure reaches him.
    peers = b.connection.find("voice_peer")
    assert [(p["action"], p["username"]) for p in peers] == [("left", "alice")]
    assert a.spoken[-1][0] == "voice-left-voice-chat"


def test_rejoin_updates_mute_without_reannouncing(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    _run(channel._handle_voice_join(a, {"type": "voice_join"}))
    _run(channel._handle_voice_join(b, {"type": "voice_join"}))

    _run(channel._handle_voice_join(a, {"type": "voice_join", "muted": True}))

    assert channel._voice_members["alice"].muted is True
    # Alice learns nothing new about herself, and is not re-announced to bob.
    about_alice = [p for p in b.connection.find("voice_peer") if p["username"] == "alice"]
    assert about_alice == []
    assert [key for key, _ in a.spoken].count("voice-joined-lobby") == 1


# -- Audio relay ----------------------------------------------------------


def test_audio_relays_to_peers_only(channel):
    a = _add(channel, "alice", table_id="t1")
    b = _add(channel, "bob", table_id="t1")
    stranger = _add(channel, "carol", table_id="t2")
    for user in (a, b, stranger):
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    _run(channel._handle_voice_audio(a, {"type": "voice_audio", "data": _frame(), "seq": 7}))

    relayed = b.connection.find("voice_audio")
    assert len(relayed) == 1
    assert relayed[0]["sender"] == "alice"
    assert relayed[0]["seq"] == 7
    assert stranger.connection.find("voice_audio") == []
    # Never echoed back to the sender.
    assert a.connection.find("voice_audio") == []


def test_audio_relays_to_lobby_peers(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    for user in (a, b):
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    _run(channel._handle_voice_audio(a, {"type": "voice_audio", "data": _frame()}))

    assert len(b.connection.find("voice_audio")) == 1


def test_audio_ignored_when_not_joined(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    _run(channel._handle_voice_join(b, {"type": "voice_join"}))

    _run(channel._handle_voice_audio(a, {"type": "voice_audio", "data": _frame()}))

    assert b.connection.find("voice_audio") == []


def test_muted_member_audio_is_dropped(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    _run(channel._handle_voice_join(a, {"type": "voice_join", "muted": True}))
    _run(channel._handle_voice_join(b, {"type": "voice_join"}))

    _run(channel._handle_voice_audio(a, {"type": "voice_audio", "data": _frame()}))

    assert b.connection.find("voice_audio") == []


def test_invalid_base64_is_rejected(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    for user in (a, b):
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    _run(channel._handle_voice_audio(a, {"type": "voice_audio", "data": "not base64!!!"}))
    _run(channel._handle_voice_audio(a, {"type": "voice_audio", "data": 12345}))

    assert b.connection.find("voice_audio") == []


def test_oversized_frame_is_rejected(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    for user in (a, b):
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    _run(
        channel._handle_voice_audio(
            a, {"type": "voice_audio", "data": _frame(byte_count=1024 * 1024)}
        )
    )

    assert b.connection.find("voice_audio") == []


def test_frame_rate_limit_blocks_flood(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    for user in (a, b):
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    async def flood():
        for _ in range(400):
            await channel._handle_voice_audio(
                a, {"type": "voice_audio", "data": _frame()}
            )

    _run(flood())

    relayed = len(b.connection.find("voice_audio"))
    assert 0 < relayed <= 250


# -- Room resync ----------------------------------------------------------


def test_moving_to_a_table_moves_the_member_between_rooms(channel):
    a = _add(channel, "alice")
    _run(channel._handle_voice_join(a, {"type": "voice_join"}))
    assert channel._voice_members["alice"].room == LOBBY_ROOM

    # Alice sits down; the next audio frame should move her to the table room.
    channel._tables.tables["alice"] = "t5"
    _run(channel._handle_voice_audio(a, {"type": "voice_audio", "data": _frame()}))

    assert channel._voice_members["alice"].room == "table:t5"


def test_moving_rooms_is_announced_to_both_sides(channel):
    # Bob shares the lobby with Alice; Carol already sits at table t5.
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    carol = _add(channel, "carol", table_id="t5")
    for user in (a, b, carol):
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    # Alice sits down at Carol's table.
    channel._tables.tables["alice"] = "t5"
    _run(channel._handle_voice_audio(a, {"type": "voice_audio", "data": _frame()}))

    # Bob loses her; Carol gains her.
    assert [(p["action"], p["username"]) for p in b.connection.find("voice_peer")] == [
        ("left", "alice"),
    ]
    assert [(p["action"], p["username"]) for p in carol.connection.find("voice_peer")] == [
        ("joined", "alice"),
    ]
    # Alice is told about her new room and who is in it.
    status = a.connection.find("voice_status")[-1]
    assert status["room"] == "table:t5"
    assert status["peers"] == ["carol"]


# -- Disconnect -----------------------------------------------------------


def test_disconnect_removes_member_and_announces(channel):
    a = _add(channel, "alice")
    b = _add(channel, "bob")
    for user in (a, b):
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    _run(channel.remove_user_from_voice("alice", announce_self=False))

    assert "alice" not in channel._voice_members
    left = [p for p in b.connection.find("voice_peer") if p["action"] == "left"]
    assert left and left[0]["username"] == "alice"
    # A disconnect is not a user action, so it is not spoken; only the peer
    # packet informs the room.
    assert [key for key, _ in a.spoken] == ["voice-joined-lobby"]


def test_remove_unknown_user_is_a_noop(channel):
    _add(channel, "alice")
    _run(channel.remove_user_from_voice("ghost"))
    assert channel._voice_members == {}


def test_server_uses_voice_mixin():
    assert issubclass(Server, VoiceChannelMixin)

def test_audio_relay_encodes_once_and_sends_identical_text(channel, monkeypatch):
    """Every listener must get the same bytes, produced by a single encode."""
    import server.core.voice as voice_module

    encodes = []
    real_encode = voice_module.encode_packet

    def counting_encode(packet):
        encodes.append(packet.get("type"))
        return real_encode(packet)

    monkeypatch.setattr(voice_module, "encode_packet", counting_encode)

    listeners = [_add(channel, name, table_id="t1") for name in ("bob", "carol", "dave")]
    speaker = _add(channel, "alice", table_id="t1")
    for user in [speaker, *listeners]:
        _run(channel._handle_voice_join(user, {"type": "voice_join"}))

    encodes.clear()
    for listener in listeners:
        listener.connection.encoded.clear()
    _run(channel._handle_voice_audio(speaker, {"type": "voice_audio", "data": _frame()}))

    assert encodes == ["voice_audio"], f"expected one encode for 3 peers, got {encodes}"

    relayed = [listener.connection.encoded for listener in listeners]
    assert all(len(frames) == 1 for frames in relayed), relayed
    assert len({frames[0] for frames in relayed}) == 1, "peers received different bytes"

    payload = json.loads(relayed[0][0])
    assert payload["type"] == "voice_audio"
    assert payload["sender"] == "alice"
    assert speaker.connection.find("voice_audio") == []
