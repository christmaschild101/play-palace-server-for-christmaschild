"""Player definition for Moto Strike."""

from dataclasses import dataclass, field

from ..base import Player
from .cards import Card


@dataclass
class MotoStrikePlayer(Player):
    """Player state for Moto Strike.

    Bike status flags:
        stuck: Bike stopped (Mud Trap or fallen after Spike/Rock). Needs a
            Rebalance card to move again.
        wheel_damaged: Wheel damaged (Spike/Rock Trap). Needs a Repair card
            (and a Rebalance, since the bike also fell).
        immobilized: Stopped by the police after failing to escape a Police
            Chase. Needs an Escape card.
        police_chase_turns: Remaining turns to play a Maneuver card and escape
            an active Police Chase (2 or 1). 0 means no active chase.
        eliminated: Out of the race (Deadly Kick).
    """

    hand: list[Card] = field(default_factory=list)
    distance: int = 0
    stuck: bool = False
    wheel_damaged: bool = False
    immobilized: bool = False
    police_chase_turns: int = 0
    eliminated: bool = False

    def can_move(self) -> bool:
        """Check if the bike can move (play movement/maneuver cards)."""
        if self.eliminated:
            return False
        if self.stuck:
            return False
        if self.wheel_damaged:
            return False
        if self.immobilized:
            return False
        return True

    def needs_recovery(self) -> bool:
        """Check if the bike currently needs a recovery card."""
        return self.stuck or self.wheel_damaged or self.immobilized

    def reset(self) -> None:
        """Reset bike state (used when starting a fresh race)."""
        self.distance = 0
        self.stuck = False
        self.wheel_damaged = False
        self.immobilized = False
        self.police_chase_turns = 0
        self.eliminated = False