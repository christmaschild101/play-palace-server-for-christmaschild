"""Card definitions and deck management for Moto Strike.

Moto Strike is a card-based motorcycle race (ported from TableEx). Riders
advance along a 2000-meter track by playing Movement cards while slowing
opponents with Traps and Attacks and defending with specials and maneuvers.

Concepts are unique to this game - traps require recovery cards (Rebalance,
Repair), Police Chase forces a Maneuver response, and Deadly Kick can end a
rider's race permanently.
"""

from dataclasses import dataclass, field
from enum import Enum
import random

from mashumaro.mixins.json import DataClassJSONMixin


class CardType(str, Enum):
    """Card type enumeration."""

    MOVEMENT = "movement"  # Advance your own bike
    TRAP = "trap"  # Slow an opponent (Mud / Spike / Rock)
    ATTACK = "attack"  # Hindrance cards (Smoke / Shock / Police Chase)
    SPECIAL = "special"  # Kicks, shields, and the Emergency Swerve
    MANEUVER = "maneuver"  # Turn cards: dodge the police or gain a little ground
    RECOVERY = "recovery"  # Fix your bike (Rebalance / Repair / Escape)


# Movement card values in meters
MOVEMENT_VALUES: dict[str, int] = {
    "easy_ride": 25,
    "speed_boost": 50,
    "power_dash": 75,
}

# Maneuver card values in meters (played as a normal action)
MANEUVER_VALUES: dict[str, int] = {
    "slight_left": 10,
    "slight_right": 10,
    "full_left": 25,
    "full_right": 25,
}

# Trap card values
TRAP_VALUES: list[str] = ["mud_trap", "spike_trap", "rock_trap"]

# Cards that are held for protection and trigger automatically
SHIELD_VALUES: list[str] = ["kick_shield", "emergency_swerve"]

# Card names for display
CARD_NAMES: dict[str, str] = {
    # Movement
    "easy_ride": "Easy Ride",
    "speed_boost": "Speed Boost",
    "power_dash": "Power Dash",
    # Traps
    "mud_trap": "Mud Trap",
    "spike_trap": "Spike Trap",
    "rock_trap": "Rock Trap",
    # Attacks
    "smoke_bomb": "Smoke Bomb",
    "electric_shock": "Electric Shock",
    "police_chase": "Police Chase",
    # Specials
    "quick_kick": "Quick Kick",
    "deadly_kick": "Deadly Kick",
    "kick_shield": "Kick Shield",
    "emergency_swerve": "Emergency Swerve",
    # Maneuvers
    "slight_left": "Slight Turn Left",
    "slight_right": "Slight Turn Right",
    "full_left": "Full Turn Left",
    "full_right": "Full Turn Right",
    # Recovery
    "rebalance": "Rebalance",
    "repair": "Repair",
    "escape": "Escape",
}


@dataclass
class Card(DataClassJSONMixin):
    """A single card in Moto Strike."""

    id: int  # Unique ID for this card instance
    card_type: str  # CardType value
    value: str  # Card value (e.g. "easy_ride", "mud_trap")

    @property
    def name(self) -> str:
        """Get the display name for this card."""
        return CARD_NAMES.get(self.value, self.value)

    @property
    def movement(self) -> int:
        """Get the meters gained when played as a movement/maneuver action."""
        return MOVEMENT_VALUES.get(self.value, MANEUVER_VALUES.get(self.value, 0))


@dataclass
class Deck(DataClassJSONMixin):
    """A deck of cards with draw and shuffle functionality."""

    cards: list[Card] = field(default_factory=list)
    _next_id: int = 0

    def _create_card(self, card_type: str, value: str) -> Card:
        """Create a card with a unique ID."""
        card = Card(id=self._next_id, card_type=card_type, value=value)
        self._next_id += 1
        return card

    def build_standard_deck(self) -> None:
        """Build the standard Moto Strike deck (93 cards).

        Recovery cards outnumber trap cards so races keep moving - with equal
        counts a 2-rider race degenerates into both riders being stuck,
        discarding card after card while waiting for the right recovery card.
        """
        self.cards = []

        # Movement cards (30)
        for _ in range(12):
            self.cards.append(self._create_card(CardType.MOVEMENT, "easy_ride"))
        for _ in range(10):
            self.cards.append(self._create_card(CardType.MOVEMENT, "speed_boost"))
        for _ in range(8):
            self.cards.append(self._create_card(CardType.MOVEMENT, "power_dash"))

        # Trap cards (8)
        for _ in range(4):
            self.cards.append(self._create_card(CardType.TRAP, "mud_trap"))
        for _ in range(2):
            self.cards.append(self._create_card(CardType.TRAP, "spike_trap"))
        for _ in range(2):
            self.cards.append(self._create_card(CardType.TRAP, "rock_trap"))

        # Attack cards (11)
        for _ in range(5):
            self.cards.append(self._create_card(CardType.ATTACK, "smoke_bomb"))
        for _ in range(3):
            self.cards.append(self._create_card(CardType.ATTACK, "electric_shock"))
        for _ in range(3):
            self.cards.append(self._create_card(CardType.ATTACK, "police_chase"))

        # Special cards (10)
        for _ in range(2):
            self.cards.append(self._create_card(CardType.SPECIAL, "quick_kick"))
        self.cards.append(self._create_card(CardType.SPECIAL, "deadly_kick"))
        for _ in range(3):
            self.cards.append(self._create_card(CardType.SPECIAL, "kick_shield"))
        for _ in range(4):
            self.cards.append(self._create_card(CardType.SPECIAL, "emergency_swerve"))

        # Maneuver cards (10)
        for _ in range(3):
            self.cards.append(self._create_card(CardType.MANEUVER, "slight_left"))
        for _ in range(3):
            self.cards.append(self._create_card(CardType.MANEUVER, "slight_right"))
        for _ in range(2):
            self.cards.append(self._create_card(CardType.MANEUVER, "full_left"))
        for _ in range(2):
            self.cards.append(self._create_card(CardType.MANEUVER, "full_right"))

        # Recovery cards (24): rebalances outnumber traps so stuck riders
        # recover quickly and the race keeps progressing.
        for _ in range(12):
            self.cards.append(self._create_card(CardType.RECOVERY, "rebalance"))
        for _ in range(6):
            self.cards.append(self._create_card(CardType.RECOVERY, "repair"))
        for _ in range(6):
            self.cards.append(self._create_card(CardType.RECOVERY, "escape"))

    def shuffle(self) -> None:
        """Shuffle the deck using Fisher-Yates."""
        random.shuffle(self.cards)

    def draw(self) -> Card | None:
        """Draw a card from the top of the deck."""
        if self.cards:
            return self.cards.pop(0)
        return None

    def add(self, card: Card) -> None:
        """Add a card to the bottom of the deck."""
        self.cards.append(card)

    def add_all(self, cards: list[Card]) -> None:
        """Add multiple cards to the deck."""
        self.cards.extend(cards)

    def is_empty(self) -> bool:
        """Check if the deck is empty."""
        return len(self.cards) == 0

    def size(self) -> int:
        """Get the number of cards in the deck."""
        return len(self.cards)