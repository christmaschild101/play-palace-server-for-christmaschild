"""Tests for the voice chat UI in the main window."""

import types

import pytest
import wx

from ui import main_window as main_mod
from voice_manager import MODE_PUSH_TO_TALK, MODE_VOICE_ACTIVITY, VoiceManager


class DummyNetworkManager:
    def __init__(self, connected=True):
        self.sent = []
        self.connected = connected

    def send_packet(self, packet):
        self.sent.append(packet)
        return True


class FakeButton:
    def __init__(self, label=""):
        self.label = label
        self.name = ""
        self.value = False
        self.tooltip = ""

    def SetLabel(self, label):
        self.label = label

    def GetLabel(self):
        return self.label

    def SetName(self, name):
        self.name = name

    def GetName(self):
        return self.name

    def SetToolTip(self, tip):
        self.tooltip = tip

    def SetValue(self, value):
        self.value = value

    def GetValue(self):
        return self.value

    def SetFocus(self):
        pass


class FakeSlider:
    def __init__(self, value=0):
        self.value = value

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value


class FakeChoice:
    def __init__(self, choices=None, selection=0):
        self.choices = choices or []
        self.selection = selection

    def GetSelection(self):
        return self.selection

    def SetSelection(self, index):
        self.selection = index

    def GetStringSelection(self):
        if not self.choices or self.selection < 0:
            return ""
        return self.choices[self.selection]


class FakeKeyEvent:
    def __init__(self, key_code):
        self.key_code = key_code
        self.skipped = False

    def GetKeyCode(self):
        return self.key_code

    def Skip(self):
        self.skipped = True


class FakeLabel:
    def __init__(self, label=""):
        self.label = label

    def SetLabel(self, label):
        self.label = label

    def GetLabel(self):
        return self.label


@pytest.fixture
def window():
    """Build a MainWindow stub with working voice controls."""
    win = main_mod.MainWindow.__new__(main_mod.MainWindow)
    win.network = DummyNetworkManager()
    win.connected = True
    win.voice_manager = VoiceManager(network=win.network)
    win.voice_join_button = FakeButton("Join Voice")
    win.voice_mute_button = FakeButton("Mute")
    win.voice_gain_slider = FakeSlider(100)
    win.voice_activity_slider = FakeSlider(15)
    win.voice_mode_choice = FakeChoice(["Voice activation", "Push to talk"], 0)
    win.voice_status_label = FakeLabel("Not in voice chat.")
    win.history_calls = []
    win.add_history = lambda text, buffer="misc", **_: win.history_calls.append(text)
    win.expecting_reconnect = False
    win.returning_to_login = False
    win._show_connection_error = lambda message, return_to_login=False: None
    win.saved_options = {}
    win.modify_option_value = lambda path, value: win.saved_options.__setitem__(path, value)
    return win


# -- Join / unjoin --------------------------------------------------------


def test_join_button_label_flips_to_unjoin(window):
    window.on_voice_join_toggle(None)

    assert window.voice_join_button.GetLabel() == "Unjoin Voice"
    assert window.voice_join_button.GetName() == "Unjoin voice chat"


def test_unjoin_button_label_flips_back(window):
    window.on_voice_join_toggle(None)
    window.on_voice_join_toggle(None)

    assert window.voice_join_button.GetLabel() == "Join Voice"
    assert window.voice_join_button.GetName() == "Join voice chat"


def test_joining_sends_join_packet(window):
    window.on_voice_join_toggle(None)
    assert {"type": "voice_join", "muted": False} in window.network.sent


def test_leaving_sends_leave_packet(window):
    window.on_voice_join_toggle(None)
    window.on_voice_join_toggle(None)
    assert {"type": "voice_leave"} in window.network.sent


def test_join_is_refused_while_disconnected(window):
    window.connected = False

    window.on_voice_join_toggle(None)

    assert window.network.sent == []
    assert "unavailable" in window.history_calls[0]


def test_joining_speaks_to_the_history(window):
    window.on_voice_join_toggle(None)
    assert any("Joined voice chat" in text for text in window.history_calls)


def test_leaving_speaks_to_the_history(window):
    window.on_voice_join_toggle(None)
    window.on_voice_join_toggle(None)
    assert any("left voice chat" in text for text in window.history_calls)


# -- Server status --------------------------------------------------------


def test_status_packet_updates_room(window):
    window.on_server_voice_status(
        {"type": "voice_status", "joined": True, "room": "table:t1", "peers": ["bob"]}
    )

    assert window.voice_manager.room == "table:t1"
    assert window.voice_manager.peers == ["bob"]


def test_status_packet_shows_who_is_heard(window):
    window.on_server_voice_status(
        {"type": "voice_status", "joined": True, "room": "lobby", "peers": ["bob", "carol"]}
    )

    label = window.voice_status_label.GetLabel()
    assert "bob" in label and "carol" in label


def test_peer_joined_is_announced(window):
    window.on_server_voice_peer(
        {"type": "voice_peer", "action": "joined", "username": "bob", "room": "lobby"}
    )

    assert "bob joined voice chat." in window.history_calls


def test_peer_left_is_announced(window):
    window.on_server_voice_peer(
        {"type": "voice_peer", "action": "left", "username": "bob", "room": "lobby"}
    )

    assert "bob left voice chat." in window.history_calls


# -- Mic gain -------------------------------------------------------------


def test_mic_gain_change_updates_manager_and_saves(window):
    window.voice_gain_slider.SetValue(175)

    window.on_voice_gain_change(None)

    assert window.voice_manager.mic_gain == 175
    assert window.saved_options["audio/voice_mic_gain"] == 175


def test_mic_gain_change_is_announced(window):
    window.voice_gain_slider.SetValue(80)

    window.on_voice_gain_change(None)

    assert "80%" in window.voice_status_label.GetLabel()


# -- Voice activation -----------------------------------------------------


def test_activity_threshold_change_updates_manager(window):
    window.voice_activity_slider.SetValue(42)

    window.on_voice_activity_change(None)

    assert window.voice_manager.detector.threshold == 42
    assert window.saved_options["audio/voice_activity_threshold"] == 42


def test_activity_threshold_is_announced(window):
    window.voice_activity_slider.SetValue(60)

    window.on_voice_activity_change(None)

    assert "60" in window.voice_status_label.GetLabel()


# -- Transmit mode --------------------------------------------------------


def test_push_to_talk_selection_switches_mode(window):
    window.voice_mode_choice.SetSelection(1)

    window.on_voice_mode_change(None)

    assert window.voice_manager.mode == MODE_PUSH_TO_TALK
    assert window.saved_options["audio/voice_mode"] == MODE_PUSH_TO_TALK


def test_voice_activity_selection_switches_mode(window):
    window.voice_manager.mode = MODE_PUSH_TO_TALK
    window.voice_mode_choice.SetSelection(0)

    window.on_voice_mode_change(None)

    assert window.voice_manager.mode == MODE_VOICE_ACTIVITY


def test_non_space_key_does_not_start_transmitting(window):
    window.voice_manager.joined = True
    window.voice_manager.muted = False
    window.voice_manager.mode = MODE_PUSH_TO_TALK

    window.on_voice_key_down(FakeKeyEvent(ord("A")))

    assert window.voice_manager.transmitting is False


def test_push_to_talk_status_explains_the_key(window):
    window.on_voice_join_toggle(None)
    window.voice_mode_choice.SetSelection(1)

    window.on_voice_mode_change(None)

    assert "Hold Space" in window.voice_status_label.GetLabel()


def test_voice_activity_status_explains_the_mic(window):
    window.on_voice_join_toggle(None)

    assert "when you speak" in window.voice_status_label.GetLabel()


# -- Push to talk key -----------------------------------------------------


def test_holding_the_key_starts_transmitting(window):
    window.voice_manager.joined = True
    window.voice_manager.muted = False
    window.voice_manager.mode = MODE_PUSH_TO_TALK

    window.on_voice_key_down(FakeKeyEvent(wx.WXK_SPACE))

    assert window.voice_manager.transmitting is True


def test_releasing_the_key_stops_transmitting(window):
    window.voice_manager.joined = True
    window.voice_manager.muted = False
    window.voice_manager.mode = MODE_PUSH_TO_TALK
    window.on_voice_key_down(FakeKeyEvent(wx.WXK_SPACE))

    window.on_voice_key_up(FakeKeyEvent(wx.WXK_SPACE))

    assert window.voice_manager.transmitting is False


# -- Mute -----------------------------------------------------------------


def test_mute_toggle_sends_mute_state(window):
    window.on_voice_join_toggle(None)
    window.voice_mute_button.SetValue(True)

    window.on_voice_mute_toggle(None)

    assert {"type": "voice_join", "muted": True} in window.network.sent
    assert window.voice_manager.muted is True


def test_unmute_speaks_microphone_live(window):
    window.on_voice_join_toggle(None)
    window.voice_mute_button.SetValue(False)

    window.on_voice_mute_toggle(None)

    assert "Microphone live." in window.history_calls


# -- Disconnect -----------------------------------------------------------


def test_connection_loss_unjoins_voice(window):
    window.on_voice_join_toggle(None)
    assert window.voice_manager.joined is True

    window.on_connection_lost()

    assert window.voice_manager.joined is False
    assert window.voice_join_button.GetLabel() == "Join Voice"


def test_connection_loss_when_not_joined_is_harmless(window):
    window.on_connection_lost()
    assert window.voice_manager.joined is False


# -- Audio frames bypass the UI ------------------------------------------


def test_audio_packet_is_routed_to_the_manager(window):
    window.voice_manager.muted = False
    window.voice_manager.handle_voice_audio = lambda packet: window.history_calls.append(packet)

    main_mod  # ensure module import side effects are loaded
    from network_manager import NetworkManager

    manager = NetworkManager.__new__(NetworkManager)
    manager.main_window = window
    manager._validate_incoming_packet = lambda packet: True

    manager._handle_packet(
        {"type": "voice_audio", "sender": "bob", "data": "AAAA", "seq": 1}
    )

    assert window.history_calls[-1]["sender"] == "bob"
    # Audio frames must never reach the history buffer as text.
    assert window.history_calls[-1]["type"] == "voice_audio"