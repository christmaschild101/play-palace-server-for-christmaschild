"""Game options for Aircraft Extreme."""

from dataclasses import dataclass

from ..base import GameOptions
from ...game_utils.options import IntOption, option_field


@dataclass
class AircraftExtremeOptions(GameOptions):
    """Options for the Aircraft Extreme flight arena."""

    laps: int = option_field(
        IntOption(
            default=2,
            min_val=1,
            max_val=10,
            value_key="laps",
            label="aircraftextreme-set-laps",
            prompt="aircraftextreme-enter-laps",
            change_msg="aircraftextreme-option-changed-laps",
            description="aircraftextreme-desc-laps",
        )
    )
    storm_damage: int = option_field(
        IntOption(
            default=1,
            min_val=0,
            max_val=3,
            value_key="damage",
            label="aircraftextreme-set-storm-damage",
            prompt="aircraftextreme-enter-storm-damage",
            change_msg="aircraftextreme-option-changed-storm-damage",
            description="aircraftextreme-desc-storm-damage",
        )
    )
    start_health: int = option_field(
        IntOption(
            default=10,
            min_val=4,
            max_val=20,
            value_key="health",
            label="aircraftextreme-set-start-health",
            prompt="aircraftextreme-enter-start-health",
            change_msg="aircraftextreme-option-changed-start-health",
            description="aircraftextreme-desc-start-health",
        )
    )
    respawn_health: int = option_field(
        IntOption(
            default=8,
            min_val=2,
            max_val=20,
            value_key="health",
            label="aircraftextreme-set-respawn-health",
            prompt="aircraftextreme-enter-respawn-health",
            change_msg="aircraftextreme-option-changed-respawn-health",
            description="aircraftextreme-desc-respawn-health",
        )
    )
