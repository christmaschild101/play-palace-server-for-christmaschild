"""Voice chat channel for PlayPalace.

Voice is a relay, never a recording. Audio arrives as base64 PCM frames on the
existing websocket, is validated, and is forwarded to the other members of the
caller's room. Nothing is written to disk, logged, or persisted.

Rooms mirror the chat split:

* ``table:<table_id>`` - everyone seated at the same table.
* ``lobby``             - everyone who is approved and *not* at a table.

A user's room is derived from where they are sitting, not chosen by the client,
so a client cannot claim to be in a room it is not in.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import time

from server.network.websocket_server import encode_packet


LOG = logging.getLogger("playpalace.voice")

# Room identifier used for everyone who is not seated at a table.
LOBBY_ROOM = "lobby"

# How often a single sender may transmit, and how much audio per second.
# 20ms frames at 50/sec is exactly real time; a little slack absorbs jitter.
MAX_FRAMES_PER_SECOND = 50
VOICE_MAX_BYTES_PER_SECOND = 128 * 1024
# Ceiling on a single relayed burst when a sender catches up after a stall.
VOICE_MAX_FRAMES_PER_BURST = 200
# Largest decoded frame accepted: a 20ms frame is 640 bytes, so this leaves room
# for a client that batches a few frames while still refusing bulk transfers.
MAX_VOICE_FRAME_BYTES = 64 * 1024
# How often to re-check whether a member has started or stopped sitting at a
# table, which moves them between the lobby and a table room.
ROOM_RESYNC_SECONDS = 2.0


class VoiceMember:
    """Bookkeeping for one participant currently in a voice room."""

    __slots__ = ("username", "room", "muted", "frame_times", "bytes_window", "room_checked_at")

    def __init__(self, username: str, room: str, muted: bool = False) -> None:
        self.username = username
        self.room = room
        self.muted = muted
        self.frame_times: list[float] = []
        self.bytes_window: list[tuple[float, int]] = []
        self.room_checked_at = 0.0


class VoiceChannelMixin:
    """Voice chat relay for the :class:`~server.core.server.Server` composition.

    Expected attributes: ``_users`` (username -> NetworkUser) and ``_tables``
    (a TableManager exposing ``find_user_table``).
    """

    def _init_voice(self) -> None:
        """Create the voice state container. Called during Server.__init__."""
        self._voice_members: dict[str, VoiceMember] = {}

    async def _send_to_room(
        self, room: str, packet: dict, *, exclude: str | None = None
    ) -> None:
        """
        Relay one packet to everyone in a voice room.

        Audio arrives 50 times a second, so the packet is validated and
        serialized once here and the encoded text is written concurrently to
        every listener, rather than re-encoding the identical frame once per
        peer and waiting on each send in turn.
        """
        text = encode_packet(packet)
        if text is None:
            return

        connections = []
        for peer_name in self._voice_peers_in(room, exclude=exclude):
            peer = self._users.get(peer_name)
            if peer is not None and peer.connection is not None:
                connections.append(peer.connection)
        if not connections:
            return

        results = await asyncio.gather(
            *(connection.send_encoded(text) for connection in connections),
            return_exceptions=True,
        )
        for connection, result in zip(connections, results):
            if isinstance(result, Exception):
                LOG.debug(
                    "Dropped %s to voice peer %s: %s",
                    packet.get("type", "?"),
                    connection.username or connection.address,
                    result,
                )

    # -- Rooms ---------------------------------------------------------------

    def _voice_room_for(self, username: str) -> str:
        """Return the room a user belongs to, derived from table membership."""
        table = self._tables.find_user_table(username)
        if table is not None:
            return f"table:{table.table_id}"
        return LOBBY_ROOM

    def _voice_peers_in(self, room: str, exclude: str | None = None) -> list[str]:
        """Return the usernames sharing a room, excluding one member."""
        return sorted(
            member.username
            for member in self._voice_members.values()
            if member.room == room and member.username != exclude
        )

    def _is_in_voice(self, username: str) -> bool:
        """Return whether a user is currently joined to voice."""
        return username in self._voice_members

    # -- Join / leave --------------------------------------------------------

    async def _handle_voice_join(self, user, packet: dict) -> None:
        """Handle a client requesting to join voice chat."""
        if user is None:
            return
        username = user.username
        if not username:
            return

        muted = bool(packet.get("muted", False))
        room = self._voice_room_for(username)

        existing = self._voice_members.get(username)
        if existing is not None:
            # Re-joining only updates mute state; do not re-announce.
            existing.muted = muted
            await self._send_voice_status(username)
            return

        member = VoiceMember(username=username, room=room, muted=muted)
        self._voice_members[username] = member

        # Tell the joiner who is already there...
        await self._send_voice_status(username)

        # ...and tell the room someone arrived.
        await self._announce_peer(room, "joined", username, exclude=username)

        if room == LOBBY_ROOM:
            user.speak_l("voice-joined-lobby", buffer="misc")
        else:
            user.speak_l("voice-joined-table", buffer="misc")

    async def _handle_voice_leave(self, user, packet: dict) -> None:
        """Handle a client leaving voice chat."""
        if user is None:
            return
        # The user pressed Unjoin, so this is a deliberate action and gets spoken.
        await self.remove_user_from_voice(user.username, announce_self=True)

    async def remove_user_from_voice(
        self, username: str | None, *, announce_self: bool = True
    ) -> None:
        """Drop a user from their voice room and let the room know."""
        if not username:
            return
        member = self._voice_members.pop(username, None)
        if member is None:
            return

        await self._announce_peer(member.room, "left", username, exclude=username)

        if announce_self:
            user = self._users.get(username)
            if user is not None:
                await self._send_voice_status(username)
                user.speak_l("voice-left-voice-chat", buffer="misc")

    # -- Audio relay ---------------------------------------------------------

    async def _handle_voice_audio(self, user, packet: dict) -> None:
        """Relay one audio frame to the other members of the sender's room."""
        if user is None:
            return
        username = user.username
        if not username:
            return

        member = self._voice_members.get(username)
        if member is None or member.muted:
            # Not joined, or joined but muted: drop the frame silently.
            return

        await self._sync_voice_room(member)

        payload = packet.get("data")
        if not isinstance(payload, str):
            return
        decoded_length = self._voice_decoded_length(payload)
        if decoded_length is None:
            return

        now = time.monotonic()
        if not self._voice_within_limits(member, now, decoded_length):
            return

        seq = packet.get("seq", 0)
        relay = {
            "type": "voice_audio",
            "sender": username,
            "data": payload,
            "seq": seq if isinstance(seq, int) and seq >= 0 else 0,
        }

        await self._send_to_room(member.room, relay, exclude=username)

    def _voice_decoded_length(self, payload: str) -> int | None:
        """Return the decoded byte length of a base64 PCM frame, or None if invalid."""
        try:
            decoded = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            return None
        if not decoded:
            return None
        # A 20ms frame at 16kHz mono 16-bit is 640 bytes. Reject anything far
        # larger than one frame so a client cannot smuggle bulk data through.
        if len(decoded) > MAX_VOICE_FRAME_BYTES:
            return None
        return len(decoded)

    def _voice_within_limits(self, member: VoiceMember, now: float, byte_count: int) -> bool:
        """Apply frame-rate and bandwidth limits to one sender."""
        window = now - 1.0

        member.frame_times.append(now)
        member.frame_times = [t for t in member.frame_times if t >= window]
        if len(member.frame_times) > MAX_FRAMES_PER_SECOND + VOICE_MAX_FRAMES_PER_BURST:
            LOG.warning("Voice frame rate exceeded for %s", member.username)
            return False

        member.bytes_window.append((now, byte_count))
        member.bytes_window = [(t, n) for t, n in member.bytes_window if t >= window]
        if sum(n for _, n in member.bytes_window) > VOICE_MAX_BYTES_PER_SECOND:
            LOG.warning("Voice bandwidth exceeded for %s", member.username)
            return False
        return True

    # -- Status helpers ------------------------------------------------------

    async def _sync_voice_room(self, member: VoiceMember) -> None:
        """Move a member between rooms when they start or stop sitting at a table.

        Checked on the audio path rather than on every table action so the
        common case costs one dict lookup, not a scan of every table.
        """
        now = time.monotonic()
        if now - member.room_checked_at < ROOM_RESYNC_SECONDS:
            return
        member.room_checked_at = now

        room = self._voice_room_for(member.username)
        if room == member.room:
            return

        previous, member.room = member.room, room
        await self._announce_peer(previous, "left", member.username)
        await self._announce_peer(room, "joined", member.username, exclude=member.username)
        await self._send_voice_status(member.username)

    async def _send_voice_status(self, username: str) -> None:
        """Send a client its own voice status and the peers it can hear."""
        user = self._users.get(username)
        if user is None:
            return
        member = self._voice_members.get(username)
        await user.connection.send(
            {
                "type": "voice_status",
                "joined": member is not None,
                "room": member.room if member else None,
                "peers": self._voice_peers_in(member.room, exclude=username) if member else [],
                "muted": member.muted if member else False,
            }
        )

    async def _announce_peer(
        self, room: str, action: str, username: str, *, exclude: str | None = None
    ) -> None:
        """Tell everyone in a room that a peer joined or left."""
        await self._send_to_room(
            room,
            {"type": "voice_peer", "action": action, "username": username, "room": room},
            exclude=exclude,
        )