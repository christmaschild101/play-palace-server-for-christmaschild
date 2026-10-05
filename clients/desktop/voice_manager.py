"""Voice chat client for PlayPalace.

Capture, voice-activity detection, and playback all run on the same BASS
backend the rest of the client audio uses, so the chosen input and output
devices match the speakers the player already hears.

Audio is 16kHz mono signed 16-bit little-endian PCM sliced into 20ms frames.
Each frame is base64-encoded into a ``voice_audio`` packet and relayed by the
server; nothing is stored locally.

The BASS objects are imported lazily so this module can be imported (and its
pure logic tested) on a machine with no audio hardware.
"""

from __future__ import annotations

import base64
import logging
import math
import threading
from array import array

LOG = logging.getLogger(__name__)

# Audio format shared with the server (see server/network/packet_models.py).
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
FRAME_MS = 20
FRAME_BYTES = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * FRAME_MS // 1000  # 640

# Transmit modes.
MODE_VOICE_ACTIVITY = "voice_activity"
MODE_PUSH_TO_TALK = "push_to_talk"

# Defaults, mirrored by the options dialog.
DEFAULT_MIC_GAIN = 100  # percent, 0-200
DEFAULT_VOICE_ACTIVITY_THRESHOLD = 15  # 0-100 scale
DEFAULT_VOICE_ACTIVITY_HANG_MS = 500
DEFAULT_VOICE_VOLUME = 100  # percent, 0-200

# Never let the outgoing queue grow without bound if the network stalls.
MAX_QUEUED_FRAMES = 50


class VoiceActivityDetector:
    """Decides whether a frame of PCM should be transmitted.

    Uses RMS amplitude against a threshold, then holds the mic open for a hang
    period so speech is not chopped between words.
    """

    def __init__(
        self,
        threshold: int = DEFAULT_VOICE_ACTIVITY_THRESHOLD,
        hang_ms: int = DEFAULT_VOICE_ACTIVITY_HANG_MS,
    ) -> None:
        self.threshold = threshold
        self.hang_ms = hang_ms
        self._speaking = False
        self._frames_since_speech = 0
        self._hang_frames = max(1, hang_ms // FRAME_MS)

    def reset(self) -> None:
        """Return to the silent state, e.g. after the user stops talking."""
        self._speaking = False
        self._frames_since_speech = 0

    def is_speaking(self) -> bool:
        """Return whether the mic is currently considered open."""
        return self._speaking

    def level_percent(self, frame: bytes) -> int:
        """Return the frame's RMS level on a 0-100 scale."""
        samples = array("h")
        usable = len(frame) - (len(frame) % SAMPLE_WIDTH)
        if usable <= 0:
            return 0
        samples.frombytes(frame[:usable])
        if not samples:
            return 0
        # RMS of full-scale 16-bit audio is 32768.
        total = 0
        for value in samples:
            total += value * value
        rms = math.sqrt(total / len(samples))
        return int(min(100, round((rms / 32768.0) * 100)))

    def process(self, frame: bytes) -> bool:
        """Feed one frame and return whether it should be transmitted."""
        level = self.level_percent(frame)
        if level >= self.threshold:
            self._speaking = True
            self._frames_since_speech = 0
            return True

        self._frames_since_speech += 1
        if self._frames_since_speech >= self._hang_frames:
            self._speaking = False
        return self._speaking


def apply_gain(frame: bytes, gain_percent: int) -> bytes:
    """Scale 16-bit PCM samples by a percentage, clipping at full scale."""
    if gain_percent == 100:
        return frame
    gain = max(0, min(200, gain_percent)) / 100.0
    samples = array("h")
    usable = len(frame) - (len(frame) % SAMPLE_WIDTH)
    if usable <= 0:
        return frame
    samples.frombytes(frame[:usable])
    for index, value in enumerate(samples):
        scaled = int(value * gain)
        samples[index] = 32767 if scaled > 32767 else (-32768 if scaled < -32768 else scaled)
    return samples.tobytes()


class VoiceSpeaker:
    """A push stream that plays one remote speaker's audio."""

    def __init__(self, volume_percent: int = DEFAULT_VOICE_VOLUME) -> None:
        self.volume_percent = volume_percent
        self._stream = None
        self._stream_factory = None

    def _ensure_stream(self):
        """Create the underlying BASS push stream on first use."""
        if self._stream is None and self._stream_factory is not None:
            self._stream = self._stream_factory()
            if self._stream is not None:
                self._stream.play()
        return self._stream

    def push(self, frame: bytes) -> None:
        """Queue decoded PCM for playback."""
        stream = self._ensure_stream()
        if stream is None:
            return
        try:
            if self.volume_percent != 100:
                stream.volume = max(0.0, min(2.0, self.volume_percent / 100.0))
            stream.push(frame)
        except Exception:  # pragma: no cover - depends on audio hardware
            LOG.debug("Voice playback push failed", exc_info=True)
            self.close()

    def close(self) -> None:
        """Tear down the playback stream."""
        if self._stream is None:
            return
        try:
            self._stream.free()
        except Exception:  # pragma: no cover - depends on audio hardware
            LOG.debug("Failed to free voice playback stream", exc_info=True)
        self._stream = None


class VoiceManager:
    """Owns microphone capture, transmit gating, and speaker playback.

    ``send_packet`` is called from BASS's audio callback thread, so frames are
    queued and drained by a sender thread rather than sent inline.
    """

    def __init__(self, network=None, on_state_change=None) -> None:
        """
        Args:
            network: NetworkManager used to send voice packets.
            on_state_change: Callback invoked on the main thread whenever
                join/mute/transmitting state changes, for UI refresh.
        """
        self.network = network
        self.on_state_change = on_state_change

        self.joined = False
        self.muted = False
        self.transmitting = False
        self.room = None
        self.peers = []

        self.mode = MODE_VOICE_ACTIVITY
        self.mic_gain = DEFAULT_MIC_GAIN
        self.voice_volume = DEFAULT_VOICE_VOLUME
        self.input_device = "Default"
        self.output_device = "Default"

        self.detector = VoiceActivityDetector()
        self.push_to_talk_active = False

        self._lock = threading.Lock()
        self._outbound = []
        self._inbound = {}
        self._pending = b""

        self._recorder = None
        self._input = None
        self._senders = {}
        self._sender_thread = None
        self._stop_event = threading.Event()
        # Replaced in tests; defaults to a real BASS push stream in the client.
        self._stream_factory = self._create_push_stream

    # -- Device enumeration -------------------------------------------------

    @staticmethod
    def list_input_devices() -> list:
        """Return available microphone names ("Default" first)."""
        try:
            from sound_lib.input import Input

            return list(Input.get_device_names())
        except Exception:
            LOG.debug("Could not enumerate input devices", exc_info=True)
            return ["Default"]

    @staticmethod
    def list_output_devices() -> list:
        """Return available speaker names."""
        try:
            from sound_lib.output import Output

            return list(Output.get_device_names())
        except Exception:
            LOG.debug("Could not enumerate output devices", exc_info=True)
            return []

    # -- Settings -----------------------------------------------------------

    def apply_settings(self, options: dict) -> None:
        """Apply voice settings from the client options dict."""
        audio = options.get("audio", {}) if isinstance(options, dict) else {}
        if not isinstance(audio, dict):
            audio = {}

        previous_device = self.input_device
        previous_mode = self.mode
        previous_output = self.output_device

        self.mic_gain = int(audio.get("voice_mic_gain", DEFAULT_MIC_GAIN))
        self.voice_volume = int(audio.get("voice_volume", DEFAULT_VOICE_VOLUME))
        self.input_device = str(audio.get("voice_input_device", "Default") or "Default")
        self.output_device = str(audio.get("voice_output_device", "") or "")

        mode = str(audio.get("voice_mode", MODE_VOICE_ACTIVITY) or MODE_VOICE_ACTIVITY)
        self.mode = mode if mode in (MODE_VOICE_ACTIVITY, MODE_PUSH_TO_TALK) else MODE_VOICE_ACTIVITY

        self.detector.threshold = int(
            audio.get("voice_activity_threshold", DEFAULT_VOICE_ACTIVITY_THRESHOLD)
        )
        self.detector.hang_ms = int(
            audio.get("voice_activity_hang_ms", DEFAULT_VOICE_ACTIVITY_HANG_MS)
        )

        for speaker in self._senders.values():
            speaker.volume_percent = self.voice_volume

        # Playback streams bind to an output device when they are created, so a
        # changed choice has to rebuild them to take effect.
        if previous_output != self.output_device:
            self._close_speakers()

        # Restart capture if the input device changed underneath us.
        if self.joined and previous_device != self.input_device:
            self._start_capture()

        if previous_mode != self.mode or self.mode == MODE_PUSH_TO_TALK:
            self.detector.reset()
            self._refresh_transmitting()

    # -- Join / leave -------------------------------------------------------

    def join(self) -> None:
        """Join voice chat, asking the server for the room we belong in."""
        if self.joined or self.network is None:
            return
        self.network.send_packet({"type": "voice_join", "muted": self.muted})
        # Optimistically mark joined so the button state flips immediately; the
        # server's voice_status packet confirms it.
        self.joined = True
        self._notify_state()

    def unjoin(self) -> None:
        """Leave voice chat and release the microphone."""
        if self.network is not None and self.joined:
            self.network.send_packet({"type": "voice_leave"})
        self.joined = False
        self.room = None
        self.peers = []
        self.muted = False
        self.transmitting = False
        self._stop_capture()
        self._close_speakers()
        self._notify_state()

    def set_muted(self, muted: bool) -> None:
        """Mute or unmute the microphone while staying joined."""
        muted = bool(muted)
        if muted == self.muted:
            return
        self.muted = muted
        if muted:
            self.transmitting = False
        else:
            self.detector.reset()
        # Re-join with the new mute state so the server stops/starts relaying.
        if self.joined and self.network is not None:
            self.network.send_packet({"type": "voice_join", "muted": muted})
        self._refresh_transmitting()

    def set_push_to_talk(self, active: bool) -> None:
        """Hold or release the push-to-talk key."""
        active = bool(active)
        if active == self.push_to_talk_active:
            return
        self.push_to_talk_active = active
        self._refresh_transmitting()

    def shutdown(self) -> None:
        """Release everything; safe to call more than once."""
        self.unjoin()

    # -- Server packets -----------------------------------------------------

    def handle_voice_status(self, packet: dict) -> None:
        """Apply the server's confirmation of our voice state."""
        self.joined = bool(packet.get("joined", False))
        self.room = packet.get("room")
        self.peers = list(packet.get("peers", []) or [])
        self.muted = bool(packet.get("muted", self.muted))

        if self.joined and self._recorder is None:
            self._start_capture()
        elif not self.joined:
            self._stop_capture()
            self._close_speakers()

        # Speakers we can no longer hear are dropped.
        for username in list(self._senders):
            if username not in self.peers:
                self._senders.pop(username).close()

        self._refresh_transmitting()
        self._notify_state()

    def handle_voice_peer(self, packet: dict) -> None:
        """Apply a peer join/leave announcement."""
        action = packet.get("action")
        username = packet.get("username")
        if not username:
            return
        if action == "left":
            speaker = self._senders.pop(username, None)
            if speaker is not None:
                speaker.close()
            self.peers = [name for name in self.peers if name != username]
        else:
            if username not in self.peers:
                self.peers.append(username)
        self._notify_state()

    def handle_voice_audio(self, packet: dict) -> None:
        """Decode and play one relayed audio frame."""
        if self.muted:
            return
        sender = packet.get("sender")
        data = packet.get("data")
        if not sender or not isinstance(data, str):
            return
        try:
            frame = base64.b64decode(data, validate=True)
        except Exception:
            return
        if not frame:
            return

        speaker = self._senders.get(sender)
        if speaker is None:
            speaker = VoiceSpeaker(self.voice_volume)
            speaker._stream_factory = self._stream_factory
            self._senders[sender] = speaker
        speaker.push(frame)

    # -- Capture ------------------------------------------------------------

    def _create_push_stream(self):
        """Build a BASS push stream for one remote speaker.

        Returns None when no audio output is available (headless machine), so
        playback degrades quietly instead of raising into the network loop.
        """
        try:
            # Importing sound_cacher initialises the shared BASS output device;
            # without it BASS_Init has never been called and stream creation
            # fails with error 8. The client always uses it, but importing here
            # keeps voice working even if startup order ever changes.
            import sound_cacher  # noqa: F401
            from sound_lib import stream as sound_stream

            push_stream = sound_stream.PushStream(
                freq=SAMPLE_RATE, chans=CHANNELS, flags=0, decode=False
            )
        except Exception:
            LOG.debug("Could not open voice playback output", exc_info=True)
            return None

        # Playback honours the voice output device when the user picked one;
        # otherwise BASS keeps using PlayPalace's own output device.
        if self.output_device:
            self._apply_output_device(push_stream)
        return push_stream

    def _apply_output_device(self, push_stream) -> None:
        """Point a playback stream at the user's chosen voice output device."""
        try:
            names = list(self.list_output_devices())
            index = names.index(self.output_device)
            push_stream.set_device(index)
        except Exception:
            LOG.debug(
                "Could not select voice output device %r; using the default",
                self.output_device,
                exc_info=True,
            )

    def _start_capture(self) -> None:
        """Begin microphone capture on a background thread."""
        self._stop_capture()
        try:
            import ctypes

            from sound_lib.input import Input
            from sound_lib.recording import Recording

            device_index = self._resolve_input_device(Input)
            self._input = Input(device_index)
        except Exception:
            LOG.debug("Could not open microphone", exc_info=True)
            self._input = None
            return

        def callback(handle, buffer, length, user):
            try:
                data = ctypes.string_at(buffer, length)
                self._on_captured(data)
            except Exception:  # pragma: no cover - callback must never raise
                LOG.debug("Voice capture callback failed", exc_info=True)
            return True  # keep recording

        try:
            self._recorder = Recording(
                frequency=SAMPLE_RATE,
                channels=CHANNELS,
                flags=0,
                proc=callback,
            )
        except Exception:
            LOG.debug("Could not start recording", exc_info=True)
            self._recorder = None
            self._input = None
            return

        self._stop_event.clear()
        self._sender_thread = threading.Thread(
            target=self._drain_outbound, name="voice-sender", daemon=True
        )
        self._sender_thread.start()

    def _resolve_input_device(self, input_cls) -> int:
        """Translate a device name into a BASS input index.

        ``Input.get_device_names`` returns "Default" followed by the real
        devices, and BASS indexes those from 0, so the index is one less than
        the position in that list.
        """
        if self.input_device and self.input_device != "Default":
            try:
                names = list(input_cls.get_device_names())
                index = names.index(self.input_device) - 1
                return index if index >= 0 else -1
            except Exception:
                LOG.debug("Falling back to default input device", exc_info=True)
        return -1

    def _stop_capture(self) -> None:
        """Stop recording and drain the sender thread."""
        self._stop_event.set()
        recorder, self._recorder = self._recorder, None
        if recorder is not None:
            try:
                recorder.stop()
                recorder.free()
            except Exception:  # pragma: no cover - depends on audio hardware
                LOG.debug("Failed to stop recording", exc_info=True)

        thread, self._sender_thread = self._sender_thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

        audio_input, self._input = self._input, None
        if audio_input is not None:
            try:
                audio_input.free()
            except Exception:  # pragma: no cover - depends on audio hardware
                LOG.debug("Failed to free input device", exc_info=True)

        with self._lock:
            self._pending = b""
            self._outbound.clear()

    def _on_captured(self, data: bytes) -> None:
        """Split captured audio into frames and queue the ones we transmit."""
        with self._lock:
            buffered = self._pending + data
            self._pending = b""
            while len(buffered) >= FRAME_BYTES:
                frame = buffered[:FRAME_BYTES]
                buffered = buffered[FRAME_BYTES:]
                outgoing = self._frame_to_send(frame)
                if outgoing is not None:
                    self._outbound.append(base64.b64encode(outgoing).decode("ascii"))
            # Carry the incomplete tail into the next callback.
            self._pending = buffered
        # Keep memory bounded if the sender thread stalls.
        while True:
            with self._lock:
                if len(self._outbound) <= MAX_QUEUED_FRAMES:
                    break
                self._outbound.pop(0)

    def _frame_to_send(self, frame: bytes) -> bytes | None:
        """Return the gain-applied frame to transmit, or None to drop it."""
        if self.muted or not self.joined:
            self._set_transmitting(False)
            return None

        if self.mode == MODE_PUSH_TO_TALK:
            if not self.push_to_talk_active:
                self._set_transmitting(False)
                return None
        elif not self.detector.process(frame):
            self._set_transmitting(False)
            return None

        self._set_transmitting(True)
        return apply_gain(frame, self.mic_gain)

    def _drain_outbound(self) -> None:
        """Send queued frames from the sender thread."""
        sequence = 0
        while not self._stop_event.is_set():
            with self._lock:
                batch = self._outbound[:]
                del self._outbound[:]
            for payload in batch:
                if self.network is None or not self.connected_state():
                    continue
                self.network.send_packet(
                    {"type": "voice_audio", "data": payload, "seq": sequence}
                )
                sequence += 1
            if not batch:
                self._stop_event.wait(0.005)

    def connected_state(self) -> bool:
        """Return whether the network layer can currently send."""
        return bool(getattr(self.network, "connected", False))

    # -- State --------------------------------------------------------------

    def _set_transmitting(self, value: bool) -> None:
        if value != self.transmitting:
            self.transmitting = value
            self._notify_state()

    def _refresh_transmitting(self) -> None:
        """Recompute the transmitting indicator from current settings."""
        if self.muted or not self.joined:
            self._set_transmitting(False)
        elif self.mode == MODE_PUSH_TO_TALK:
            self._set_transmitting(self.push_to_talk_active)

    def _close_speakers(self) -> None:
        """Tear down every playback stream."""
        for speaker in list(self._senders.values()):
            speaker.close()
        self._senders.clear()

    def _notify_state(self) -> None:
        """Invoke the UI callback on the main thread."""
        if self.on_state_change is None:
            return
        try:
            import wx

            wx.CallAfter(self.on_state_change, self)
        except Exception:
            self.on_state_change(self)