"""Game options for Moto Strike."""

from dataclasses import dataclass

from ..base import GameOptions
from ...game_utils.options import (
    BoolOption,
    IntOption,
    option_field,
)


@dataclass
class MotoStrikeOptions(GameOptions):
    """Options for the Moto Strike race."""

    track_length: int = option_field(
        IntOption(
            default=2000,
            min_val=500,
            max_val=5000,
            value_key="meters",
            label="motostrike-set-track-length",
            prompt="motostrike-enter-track-length",
            change_msg="motostrike-option-changed-track-length",
            description="motostrike-desc-track-length",
        )
    )
    deadly_kick: bool = option_field(
        BoolOption(
            default=True,
            value_key="enabled",
            label="motostrike-toggle-deadly-kick",
            change_msg="motostrike-option-changed-deadly-kick",
            description="motostrike-desc-deadly-kick",
        )
    )