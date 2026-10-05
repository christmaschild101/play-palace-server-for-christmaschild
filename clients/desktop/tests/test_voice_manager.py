"""Tests for the client-side voice chat manager."""

from __future__ import annotations

import base64
import math
import struct

import pytest

from voice_manager import (
    DEFAULT_VOICE_ACTIVITY_THRESHOLD,
    FRAME_BYTES,
    MODE_PUSH_TO_TALK,
    MODE_VOICE_ACTIVITY,
    SAMPLE_RATE,
    VoiceActivityDetector,
    VoiceManager,
    VoiceSpeaker,
    apply_gain,
)


def tone(amplitude: int, samples: int = SAMPLE_RATE // 50) -> bytes:
    """Build a 20ms mono 16-bit frame of a constant-amplitude tone."""
    return struct.pack("<%dh" % samples, *[amplitude] * samples)


def silence(samples: int = SAMPLE_RATE // 50) -> bytes:
    """Build a 20ms silent frame."""
    return b"\x00" * (samples * 2)


class FakeNetwork:
    """Records outgoing packets."""

    def __init__(self, connected=True):
        self.sent = []
        self.connected = connected

    def send_packet(self, packet):
        self.sent.append(packet)
        return True


class FakeStream:
    """Stands in for a BASS push stream."""

    def __init__(self):
        self.pushed = []
        self.played = False
        self.freed = False
        self.volume = None

    def play(self):
        self.played = True

    def push(self, data):
        self.pushed.append(data)

    def free(self):
        self.freed = True


# -- Gain -----------------------------------------------------------------


def test_gain_at_unity_is_unchanged():
    frame = tone(1000)
    assert apply_gain(frame, 100) == frame


def test_gain_halves_amplitude():
    result = apply_gain(tone(1000), 50)
    assert struct.unpack("<h", result[:2])[0] == 500


def test_gain_doubles_amplitude():
    result = apply_gain(tone(1000), 200)
    assert struct.unpack("<h", result[:2])[0] == 2000


def test_gain_clips_positive_peak():
    assert struct.unpack("<h", apply_gain(tone(20000), 200)[:2])[0] == 32767


def test_gain_clips_negative_peak():
    result = apply_gain(tone(-20000), 200)
    assert struct.unpack("<h", result[:2])[0] == -32768


def test_gain_of_zero_silences():
    assert apply_gain(tone(1000), 0) == silence()


def test_gain_preserves_frame_length():
    frame = tone(1234)
    assert len(apply_gain(frame, 175)) == len(frame)


# -- Voice activity detection ---------------------------------------------


def test_silence_does_not_trigger():
    detector = VoiceActivityDetector(threshold=10, hang_ms=100)
    assert detector.process(silence()) is False
    assert detector.is_speaking() is False


def test_loud_tone_triggers():
    detector = VoiceActivityDetector(threshold=10, hang_ms=100)
    assert detector.process(tone(20000)) is True
    assert detector.is_speaking() is True


def test_quiet_tone_below_threshold_does_not_trigger():
    detector = VoiceActivityDetector(threshold=50, hang_ms=100)
    # 1% of full scale measures ~1 on the 0-100 level scale.
    assert detector.process(tone(328)) is False


def test_hang_time_keeps_mic_open_between_words():
    detector = VoiceActivityDetector(threshold=10, hang_ms=100)
    detector.process(tone(20000))

    # Within the hang window the mic stays open (5 frames = 100ms).
    for _ in range(4):
        assert detector.process(silence()) is True
    # Past the hang window it closes.
    assert detector.process(silence()) is False


def test_reset_closes_the_mic():
    detector = VoiceActivityDetector(threshold=10, hang_ms=100)
    detector.process(tone(20000))
    detector.reset()
    assert detector.is_speaking() is False


def test_level_percent_scales_with_amplitude():
    detector = VoiceActivityDetector()
    assert detector.level_percent(silence()) == 0
    assert detector.level_percent(tone(32767)) == 100
    assert 49 <= detector.level_percent(tone(16384)) <= 51


def test_level_percent_of_empty_frame_is_zero():
    assert VoiceActivityDetector().level_percent(b"") == 0


def test_default_threshold_is_in_range():
    detector = VoiceActivityDetector()
    assert detector.threshold == DEFAULT_VOICE_ACTIVITY_THRESHOLD
    assert 0 < detector.threshold <= 100


# -- Framing --------------------------------------------------------------


def test_frame_bytes_is_20ms_at_16k_mono():
    assert FRAME_BYTES == 640


# -- Join / leave ---------------------------------------------------------


def test_join_sends_join_packet():
    network = FakeNetwork()
    manager = VoiceManager(network=network)

    manager.join()

    assert network.sent == [{"type": "voice_join", "muted": False}]
    assert manager.joined is True


def test_join_is_idempotent():
    network = FakeNetwork()
    manager = VoiceManager(network=network)

    manager.join()
    manager.join()

    assert len(network.sent) == 1


def test_unjoin_sends_leave_and_clears_state():
    network = FakeNetwork()
    manager = VoiceManager(network=network)
    manager.join()
    manager.room = "lobby"
    manager.peers = ["bob"]

    manager.unjoin()

    assert {"type": "voice_leave"} in network.sent
    assert manager.joined is False
    assert manager.room is None
    assert manager.peers == []


def test_unjoin_without_network_does_not_raise():
    manager = VoiceManager(network=None)
    manager.unjoin()
    assert manager.joined is False


def test_mute_rejoins_with_muted_flag():
    network = FakeNetwork()
    manager = VoiceManager(network=network)
    manager.join()

    manager.set_muted(True)

    assert network.sent[-1] == {"type": "voice_join", "muted": True}
    assert manager.muted is True


def test_mute_stops_transmitting():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager._set_transmitting(True)

    manager.set_muted(True)

    assert manager.transmitting is False


# -- Status handling ------------------------------------------------------


def test_status_joined_sets_room_and_peers():
    manager = VoiceManager(network=FakeNetwork())

    manager.handle_voice_status(
        {"type": "voice_status", "joined": True, "room": "table:t1", "peers": ["bob"]}
    )

    assert manager.joined is True
    assert manager.room == "table:t1"
    assert manager.peers == ["bob"]


def test_status_not_joined_clears_state():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager.room = "lobby"

    manager.handle_voice_status({"type": "voice_status", "joined": False, "room": None})

    assert manager.joined is False
    assert manager.room is None


def test_peer_left_removes_speaker():
    manager = VoiceManager(network=FakeNetwork())
    stream = FakeStream()
    speaker = VoiceSpeaker()
    speaker._stream = stream
    manager._senders["bob"] = speaker
    manager.peers = ["bob"]

    manager.handle_voice_peer({"type": "voice_peer", "action": "left", "username": "bob"})

    assert "bob" not in manager._senders
    assert manager.peers == []
    assert stream.freed is True


def test_peer_joined_adds_to_peers():
    manager = VoiceManager(network=FakeNetwork())

    manager.handle_voice_peer({"type": "voice_peer", "action": "joined", "username": "carol"})

    assert manager.peers == ["carol"]


# -- Playback -------------------------------------------------------------


def test_audio_packet_is_decoded_and_pushed():
    manager = VoiceManager(network=FakeNetwork())
    manager.muted = False
    stream = FakeStream()
    manager._stream_factory = lambda: stream
    payload = base64.b64encode(tone(500)).decode("ascii")

    manager.handle_voice_audio({"type": "voice_audio", "sender": "bob", "data": payload})

    assert stream.pushed == [tone(500)]
    assert stream.played is True


def test_audio_is_not_played_while_muted():
    manager = VoiceManager(network=FakeNetwork())
    manager.muted = True
    stream = FakeStream()
    manager._stream_factory = lambda: stream

    manager.handle_voice_audio(
        {
            "type": "voice_audio",
            "sender": "bob",
            "data": base64.b64encode(tone(500)).decode("ascii"),
        }
    )

    assert stream.pushed == []


def test_invalid_base64_audio_is_ignored():
    manager = VoiceManager(network=FakeNetwork())
    manager.muted = False
    stream = FakeStream()
    manager._stream_factory = lambda: stream

    manager.handle_voice_audio({"type": "voice_audio", "sender": "bob", "data": "!!!not base64"})

    assert stream.pushed == []


def test_missing_sender_is_ignored():
    manager = VoiceManager(network=FakeNetwork())
    manager.muted = False
    stream = FakeStream()
    manager._stream_factory = lambda: stream

    manager.handle_voice_audio(
        {"type": "voice_audio", "data": base64.b64encode(tone(1)).decode("ascii")}
    )

    assert stream.pushed == []


def test_speaker_survives_a_push_failure():
    speaker = VoiceSpeaker()
    stream = FakeStream()

    def boom(_data):
        raise RuntimeError("audio device gone")

    stream.push = boom
    speaker._stream = stream

    speaker.push(tone(500))

    assert speaker._stream is None
    assert stream.freed is True


# -- Transmit gating ------------------------------------------------------


def test_voice_activity_mode_drops_silence():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager.muted = False
    manager.mode = MODE_VOICE_ACTIVITY
    manager.detector.threshold = 10

    assert manager._frame_to_send(silence()) is None


def test_voice_activity_mode_sends_loud_frames():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager.muted = False
    manager.mode = MODE_VOICE_ACTIVITY
    manager.detector.threshold = 10

    outgoing = manager._frame_to_send(tone(20000))

    assert outgoing == tone(20000)
    assert manager.transmitting is True


def test_push_to_talk_mode_requires_the_key():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager.muted = False
    manager.mode = MODE_PUSH_TO_TALK

    assert manager._frame_to_send(tone(20000)) is None

    manager.set_push_to_talk(True)

    assert manager._frame_to_send(tone(20000)) == tone(20000)


def test_muted_member_never_sends():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager.muted = True

    assert manager._frame_to_send(tone(20000)) is None


def test_unjoined_member_never_sends():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = False

    assert manager._frame_to_send(tone(20000)) is None


def test_gain_is_applied_to_transmitted_frames():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager.muted = False
    manager.mode = MODE_PUSH_TO_TALK
    manager.mic_gain = 50
    manager.set_push_to_talk(True)

    outgoing = manager._frame_to_send(tone(1000))

    assert struct.unpack("<h", outgoing[:2])[0] == 500


def test_captured_audio_is_split_into_frames():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager.muted = False
    manager.mode = MODE_PUSH_TO_TALK
    manager.set_push_to_talk(True)

    manager._on_captured(tone(1000) + tone(2000))

    assert len(manager._outbound) == 2
    first = base64.b64decode(manager._outbound[0])
    assert len(first) == FRAME_BYTES


def test_partial_frames_are_buffered_until_complete():
    manager = VoiceManager(network=FakeNetwork())
    manager.joined = True
    manager.muted = False
    manager.mode = MODE_PUSH_TO_TALK
    manager.set_push_to_talk(True)

    half = FRAME_BYTES // 2
    manager._on_captured(tone(1000)[:half])
    assert manager._outbound == []

    manager._on_captured(tone(1000)[half:])
    assert len(manager._outbound) == 1


# -- Settings -------------------------------------------------------------


def test_apply_settings_reads_audio_options():
    manager = VoiceManager(network=FakeNetwork())

    manager.apply_settings(
        {
            "audio": {
                "voice_mic_gain": 150,
                "voice_volume": 80,
                "voice_mode": MODE_PUSH_TO_TALK,
                "voice_activity_threshold": 42,
                "voice_activity_hang_ms": 900,
                "voice_input_device": "Test Mic",
            }
        }
    )

    assert manager.mic_gain == 150
    assert manager.voice_volume == 80
    assert manager.mode == MODE_PUSH_TO_TALK
    assert manager.detector.threshold == 42
    assert manager.detector.hang_ms == 900
    assert manager.input_device == "Test Mic"


def test_apply_settings_rejects_unknown_mode():
    manager = VoiceManager(network=FakeNetwork())

    manager.apply_settings({"audio": {"voice_mode": "telepathy"}})

    assert manager.mode == MODE_VOICE_ACTIVITY


def test_apply_settings_tolerates_missing_audio_section():
    manager = VoiceManager(network=FakeNetwork())
    manager.apply_settings({})
    assert manager.mic_gain == 100


def test_apply_settings_ignores_non_dict_audio():
    manager = VoiceManager(network=FakeNetwork())
    manager.apply_settings({"audio": "nonsense"})
    assert manager.mic_gain == 100


def test_settings_propagate_to_existing_speakers():
    manager = VoiceManager(network=FakeNetwork())
    speaker = VoiceSpeaker(100)
    manager._senders["bob"] = speaker

    manager.apply_settings({"audio": {"voice_volume": 50}})

    assert speaker.volume_percent == 50


# -- Devices --------------------------------------------------------------


def test_device_listing_never_raises():
    # No audio hardware in CI; the helpers must degrade to a safe default.
    assert VoiceManager.list_input_devices()[0] == "Default"
    assert isinstance(VoiceManager.list_output_devices(), list)

# -- Real stream factory (no injected fake) -------------------------------


def test_default_stream_factory_is_real():
    """The manager must build a real playback stream, not a None placeholder.

    A None factory would make _ensure_stream return None and silently drop
    every audio frame, so voice would appear joined but never be audible.
    """
    manager = VoiceManager(network=FakeNetwork())

    assert callable(manager._stream_factory)
    assert manager._stream_factory == manager._create_push_stream


def test_speaker_without_factory_drops_frames_quietly():
    """With no audio hardware, pushing a frame must not raise."""
    speaker = VoiceSpeaker()

    speaker.push(tone(500))  # must not raise

    assert speaker._stream is None


def test_output_device_change_rebuilds_speakers():
    """Existing playback streams bind to a device, so they must be rebuilt."""
    manager = VoiceManager(network=FakeNetwork())
    manager.output_device = ""
    speaker = VoiceSpeaker()
    stream = FakeStream()
    speaker._stream = stream
    manager._senders["bob"] = speaker

    manager.apply_settings({"audio": {"voice_output_device": "Headphones"}})

    assert stream.freed is True
    assert manager._senders == {}


def test_same_output_device_keeps_speakers():
    manager = VoiceManager(network=FakeNetwork())
    manager.output_device = "Headphones"
    speaker = VoiceSpeaker()
    stream = FakeStream()
    speaker._stream = stream
    manager._senders["bob"] = speaker

    manager.apply_settings({"audio": {"voice_output_device": "Headphones"}})

    assert stream.freed is False
    assert "bob" in manager._senders


def test_apply_output_device_uses_selected_index(monkeypatch):
    """The chosen speaker name maps to a BASS device index."""
    manager = VoiceManager(network=FakeNetwork())
    manager.output_device = "Headphones"
    monkeypatch.setattr(
        VoiceManager, "list_output_devices", staticmethod(lambda: ["Speakers", "Headphones"])
    )
    stream = FakeStream()
    stream.devices = []

    def set_device(index):
        stream.devices.append(index)

    stream.set_device = set_device
    manager._apply_output_device(stream)

    assert stream.devices == [1]


def test_unknown_output_device_falls_back(monkeypatch):
    """A device that disappeared must not raise or change the stream."""
    manager = VoiceManager(network=FakeNetwork())
    manager.output_device = "Gone"
    monkeypatch.setattr(
        VoiceManager, "list_output_devices", staticmethod(lambda: ["Speakers"])
    )
    stream = FakeStream()
    stream.set_device = lambda index: (_ for _ in ()).throw(AssertionError("must not set"))

    manager._apply_output_device(stream)  # must not raise
