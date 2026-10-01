"""Player definition for Aircraft Extreme."""

from dataclasses import dataclass

from ..base import Player


@dataclass
class AircraftExtremePlayer(Player):
    """Player state for Aircraft Extreme.

    Flight state:
        row / col: Position on the 6x6 sky map (0-indexed).
        base: Corner runway id (``nw`` / ``ne`` / ``sw`` / ``se``).
        laps: Completed laps (far-corner touches).
        health: Plane health; at 0 the plane is shot down.
        power: Engine power. Flying costs 1; at 0 the engine is dead
            until the pilot plays Climb.
        actions_left: Remaining actions this turn (2 per turn).
        barrel_roll: Next incoming shot automatically misses.
        cloud_shield: Next incoming hit is absorbed by cloud cover.
        downs: Times shot down. Three downs and the pilot is out.
        downed: Waiting to respawn on the runway.
    """

    row: int = 0
    col: int = 0
    base: str = ""
    laps: int = 0
    health: int = 10
    power: int = 3
    actions_left: int = 0
    barrel_roll: bool = False
    cloud_shield: bool = False
    downs: int = 0
    downed: bool = False

    def has_power(self) -> bool:
        """Whether the engine can power a fly action."""
        return self.power > 0

    def reset_for_game(self, base: str, health: int, row: int, col: int) -> None:
        """Place the pilot on their runway with a fresh plane."""
        self.base = base
        self.row = row
        self.col = col
        self.laps = 0
        self.health = health
        self.power = 3  # MAX_POWER; kept literal to avoid a circular import
        self.actions_left = 0
        self.barrel_roll = False
        self.cloud_shield = False
        self.downs = 0
        self.downed = False
