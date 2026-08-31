"""Tests for user preference helpers."""


def test_main_sound_default_chime_alert():
    assert MainSound.Default.value == "default"
    assert MainSound.Chime.value == "chime"
    assert MainSound.Alert.value == "alert"


from server.core.users.preferences import (
    DiceKeepingStyle,
    MainSound,
    UserPreferences,
)


def test_dice_keeping_style_from_str_defaults_to_playpalace():
    assert DiceKeepingStyle.from_str("quentin_c") == DiceKeepingStyle.QUENTIN_C
    assert DiceKeepingStyle.from_str("invalid") == DiceKeepingStyle.PLAYPALACE


def test_user_preferences_to_dict_and_from_dict_round_trip():
    prefs = UserPreferences(
        play_turn_sound=False,
        clear_kept_on_roll=True,
        dice_keeping_style=DiceKeepingStyle.QUENTIN_C,
    )
    data = prefs.to_dict()
    assert data["play_turn_sound"] is False
    assert data["clear_kept_on_roll"] is True
    assert data["dice_keeping_style"] == "quentin_c"

    rebuilt = UserPreferences.from_dict(
        {"clear_kept_on_roll": True, "dice_keeping_style": "unknown"}
    )
    assert rebuilt.play_turn_sound  # defaulted to True
    assert rebuilt.clear_kept_on_roll is True
    assert rebuilt.dice_keeping_style == DiceKeepingStyle.PLAYPALACE


def test_online_and_offline_sounds_appear_in_prefs_and_round_trip():
    prefs = UserPreferences(
        online_sound=MainSound.Chime,
        offline_sound=MainSound.Alert,
    )
    data = prefs.to_dict()
    assert data["online_sound"] == "chime"
    assert data["offline_sound"] == "alert"

    rebuilt = UserPreferences.from_dict(
        {"online_sound": "default", "offline_sound": "chime"}
    )
    assert rebuilt.online_sound is MainSound.Default
    assert rebuilt.offline_sound is MainSound.Chime


def test_online_and_offline_sound_defaults_to_default():
    prefs = UserPreferences()
    assert prefs.online_sound is MainSound.Default
    assert prefs.offline_sound is MainSound.Default


def test_main_sound_choices_are_exhaustive():
    # The menu rendering code enumerates these; keep them in sync with code.
    names = {s.name for s in MainSound}
    assert names == {"Default", "Chime", "Alert"}
