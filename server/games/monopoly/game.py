"""
Monopoly Game Implementation for PlayPalace.

Full classic rules with optional extras: 40-space board (US or London/UK
variant), properties with house building and mortgages, railroads and
utilities, income/luxury (super) taxes, complete 16-card Chance and Community
Chest decks (including Get Out of Jail Free cards), jail (doubles, bail,
jail-free cards, three-turn limit), auctions for declined properties, and
two-way player-to-player trades with accept/reject. Selectable classic or
simplified rent tables (independent of the board), Free Parking jackpot,
10% income tax, and auction start-price house rules. Players go bankrupt until
one remains; the last player standing wins.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.action_guard_mixin import ActionGuardMixin
from ...game_utils.actions import Action, ActionSet, EditboxInput, MenuInput, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.game_status import GameStatus
from ...game_utils.options import BoolOption, IntOption, MenuOption, option_field
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState

# fmt: off
SPACE_NAMES_US = {
    0: "monopoly-space-go", 1: "monopoly-space-mediterranean", 2: "monopoly-space-chest",
    3: "monopoly-space-baltic", 4: "monopoly-space-income-tax", 5: "monopoly-space-reading-railroad",
    6: "monopoly-space-oriental", 7: "monopoly-space-chance", 8: "monopoly-space-vermont",
    9: "monopoly-space-connecticut", 10: "monopoly-space-jail", 11: "monopoly-space-st-charles",
    12: "monopoly-space-electric-company", 13: "monopoly-space-states", 14: "monopoly-space-virginia",
    15: "monopoly-space-pennsylvania-railroad", 16: "monopoly-space-st-james", 17: "monopoly-space-chest",
    18: "monopoly-space-tennessee", 19: "monopoly-space-new-york", 20: "monopoly-space-free-parking",
    21: "monopoly-space-kentucky", 22: "monopoly-space-chance", 23: "monopoly-space-indiana",
    24: "monopoly-space-illinois", 25: "monopoly-space-bo-railroad", 26: "monopoly-space-atlantic",
    27: "monopoly-space-ventnor", 28: "monopoly-space-water-works", 29: "monopoly-space-marvin-gardens",
    30: "monopoly-space-go-to-jail", 31: "monopoly-space-pacific", 32: "monopoly-space-north-carolina",
    33: "monopoly-space-chest", 34: "monopoly-space-pennsylvania", 35: "monopoly-space-short-line-railroad",
    36: "monopoly-space-chance", 37: "monopoly-space-park-place", 38: "monopoly-space-luxury-tax",
    39: "monopoly-space-boardwalk",
}
SPACE_NAMES_UK = {
    0: "monopoly-space-go", 1: "monopoly-space-old-kent-road", 2: "monopoly-space-chest",
    3: "monopoly-space-whitechapel-road", 4: "monopoly-space-income-tax", 5: "monopoly-space-kings-cross",
    6: "monopoly-space-angel-islington", 7: "monopoly-space-chance", 8: "monopoly-space-euston-road",
    9: "monopoly-space-pentonville-road", 10: "monopoly-space-jail", 11: "monopoly-space-pall-mall",
    12: "monopoly-space-electric-company", 13: "monopoly-space-whitehall", 14: "monopoly-space-northumberland-avenue",
    15: "monopoly-space-marylebone-station", 16: "monopoly-space-bow-street", 17: "monopoly-space-chest",
    18: "monopoly-space-marlborough-street", 19: "monopoly-space-vine-street", 20: "monopoly-space-free-parking",
    21: "monopoly-space-strand", 22: "monopoly-space-chance", 23: "monopoly-space-fleet-street",
    24: "monopoly-space-trafalgar-square", 25: "monopoly-space-fenchurch-street", 26: "monopoly-space-leicester-square",
    27: "monopoly-space-coventry-street", 28: "monopoly-space-water-works", 29: "monopoly-space-piccadilly",
    30: "monopoly-space-go-to-jail", 31: "monopoly-space-regent-street", 32: "monopoly-space-oxford-street",
    33: "monopoly-space-chest", 34: "monopoly-space-bond-street", 35: "monopoly-space-liverpool-street",
    36: "monopoly-space-chance", 37: "monopoly-space-park-lane", 38: "monopoly-space-super-tax",
    39: "monopoly-space-mayfair",
}
#: Backwards-compatible alias (US board).
SPACE_NAMES = SPACE_NAMES_US
# fmt: on

PROPERTY_PRICES = {
    1: 60, 3: 60, 6: 100, 8: 100, 9: 120,
    11: 140, 13: 140, 14: 160,
    16: 180, 18: 180, 19: 200,
    21: 220, 23: 220, 24: 240,
    26: 260, 27: 260, 29: 280,
    31: 300, 32: 300, 34: 320,
    37: 350, 39: 400,
}
RAILROADS = [5, 15, 25, 35]
RAILROAD_PRICE = 200
UTILITIES = [12, 28]
UTILITY_PRICE = 150
GROUPS = {
    "brown": [1, 3], "lightblue": [6, 8, 9], "pink": [11, 13, 14],
    "orange": [16, 18, 19], "red": [21, 23, 24], "yellow": [26, 27, 29],
    "green": [31, 32, 34], "darkblue": [37, 39],
}
HOUSE_COSTS = {
    "brown": 50, "lightblue": 50, "pink": 100, "orange": 100,
    "red": 150, "yellow": 150, "green": 200, "darkblue": 200,
}
BASE_RENTS = {
    1: 2, 3: 4, 6: 6, 8: 6, 9: 8,
    11: 10, 13: 10, 14: 12,
    16: 14, 18: 14, 19: 16,
    21: 18, 23: 18, 24: 20,
    26: 22, 27: 22, 29: 24,
    31: 26, 32: 26, 34: 28,
    37: 35, 39: 50,
}
# Authentic classic rent charts: [base, 1 house, 2, 3, 4, hotel].
# The US and UK (London) boards share these values.
RENT_TABLE = {
    1: [2, 10, 30, 90, 160, 250],
    3: [4, 20, 60, 180, 320, 450],
    6: [6, 30, 90, 270, 400, 550],
    8: [6, 30, 90, 270, 400, 550],
    9: [8, 40, 100, 300, 450, 600],
    11: [10, 50, 150, 450, 625, 750],
    13: [10, 50, 150, 450, 625, 750],
    14: [12, 60, 180, 500, 700, 900],
    16: [14, 70, 200, 550, 750, 950],
    18: [14, 70, 200, 550, 750, 950],
    19: [16, 80, 220, 600, 800, 1000],
    21: [18, 90, 250, 700, 875, 1050],
    23: [18, 90, 250, 700, 875, 1050],
    24: [20, 100, 300, 750, 925, 1100],
    26: [22, 110, 330, 800, 975, 1150],
    27: [22, 110, 330, 800, 975, 1150],
    29: [24, 120, 360, 850, 1025, 1200],
    31: [26, 130, 390, 900, 1100, 1275],
    32: [26, 130, 390, 900, 1100, 1275],
    34: [28, 150, 450, 1000, 1200, 1400],
    37: [35, 175, 500, 1100, 1300, 1500],
    39: [50, 200, 600, 1400, 1700, 2000],
}
# Simplified ladder (base doubled per house level; hotel = 32x base).
HOUSE_MULTIPLIERS = [1, 2, 4, 8, 16, 32]
MAX_BUILDINGS = 5  # 0-4 houses + hotel
TAXES = {4: 200, 38: 100}
START_MONEY = 1500
SALARY = 200
BAIL = 50

# Complete classic decks (16 each). New kinds beyond the original set:
#   goojf              - Get Out of Jail Free (player-held card)
#   repairs            - street repairs: pay per house / per hotel (value2)
#   collect_from_all   - collect from every other player
CHANCE_CARDS = [
    {"kind": "move_to", "value": 0},  # Advance to Go (collect 200)
    {"kind": "move_to", "value": 24},  # Advance to Illinois Avenue
    {"kind": "move_to", "value": 11},  # Advance to St. Charles Place
    {"kind": "move_nearest_utility", "value": 0},
    {"kind": "move_nearest_railroad", "value": 0},
    {"kind": "collect", "value": 50},  # Bank pays you a dividend
    {"kind": "goojf", "value": 0},
    {"kind": "back_3", "value": 0},
    {"kind": "jail", "value": 0},
    {"kind": "repairs", "value": 25, "value2": 100},  # per house / per hotel
    {"kind": "pay", "value": 15},  # Poor tax
    {"kind": "move_to", "value": 5},  # Take a trip to Reading Railroad
    {"kind": "move_to", "value": 39},  # Take a walk on the Boardwalk
    {"kind": "chairman", "value": 50},
    {"kind": "collect", "value": 150},  # Building loan matures
    {"kind": "collect", "value": 100},  # Crossword competition
]
CHEST_CARDS = [
    {"kind": "move_to", "value": 0},  # Advance to Go (collect 200)
    {"kind": "collect", "value": 200},  # Bank error in your favor
    {"kind": "pay", "value": 50},  # Doctor's fees
    {"kind": "collect", "value": 50},  # From sale of stock
    {"kind": "goojf", "value": 0},
    {"kind": "jail", "value": 0},
    {"kind": "collect_from_all", "value": 50},  # Grand Opera Night
    {"kind": "collect", "value": 100},  # Holiday fund matures
    {"kind": "collect", "value": 20},  # Income tax refund
    {"kind": "birthday", "value": 10},  # It's your birthday
    {"kind": "collect", "value": 100},  # Life insurance matures
    {"kind": "pay", "value": 100},  # Hospital fees
    {"kind": "pay", "value": 150},  # School fees
    {"kind": "collect", "value": 25},  # Consultancy fee
    {"kind": "repairs", "value": 40, "value2": 115},  # Street repairs
    {"kind": "collect", "value": 10},  # Beauty contest second prize
]


def _group_of(space: int) -> str | None:
    for group, spaces in GROUPS.items():
        if space in spaces:
            return group
    return None


@dataclass
class MonopolyPlayer(Player):
    """Player state for Monopoly."""

    money: int = START_MONEY
    position: int = 0
    in_jail: bool = False
    jail_turns: int = 0
    bankrupt: bool = False
    properties: list[int] = field(default_factory=list)  # Owned buyable spaces
    houses: dict[int, int] = field(default_factory=dict)  # space -> buildings (0-5)
    mortgaged: list[int] = field(default_factory=list)
    built_this_turn: bool = False  # Bot AI: one build per turn
    # Get Out of Jail Free cards (parallel list of source decks for return)
    jail_free_cards: int = 0
    jail_free_decks: list[str] = field(default_factory=list)
    # Stats
    rent_collected: int = 0
    houses_built: int = 0
    # Trade wizard state (offerer side)
    trade_property: int | None = None
    trade_give_cash: int | None = None
    trade_target_id: str = ""
    trade_receive_property: int | None = None
    trade_receive_cash: int | None = None


@dataclass
class MonopolyOptions(GameOptions):
    """Options for Monopoly."""

    starting_money: int = option_field(
        IntOption(
            default=1500,
            min_val=500,
            max_val=5000,
            value_key="money",
            label="monopoly-set-starting-money",
            prompt="monopoly-enter-starting-money",
            change_msg="monopoly-option-changed-starting-money",
            description="monopoly-desc-starting-money",
        )
    )
    max_rounds: int = option_field(
        IntOption(
            default=0,
            min_val=0,
            max_val=500,
            value_key="rounds",
            label="monopoly-set-max-rounds",
            prompt="monopoly-enter-max-rounds",
            change_msg="monopoly-option-changed-max-rounds",
            description="monopoly-desc-max-rounds",
        )
    )
    board_variant: str = option_field(
        MenuOption(
            default="us",
            value_key="board",
            choices=["us", "uk"],
            choice_labels={
                "us": "monopoly-board-us",
                "uk": "monopoly-board-uk",
            },
            label="monopoly-set-board",
            prompt="monopoly-select-board",
            change_msg="monopoly-option-changed-board",
            description="monopoly-desc-board",
        )
    )
    rent_source: str = option_field(
        MenuOption(
            default="classic",
            value_key="rent",
            choices=["classic", "simplified"],
            choice_labels={
                "classic": "monopoly-rent-classic",
                "simplified": "monopoly-rent-simplified",
            },
            label="monopoly-set-rent",
            prompt="monopoly-select-rent",
            change_msg="monopoly-option-changed-rent",
            description="monopoly-desc-rent",
        )
    )
    free_parking_jackpot: bool = option_field(
        BoolOption(
            default=False,
            label="monopoly-set-free-parking-jackpot",
            change_msg="monopoly-option-changed-free-parking-jackpot",
            description="monopoly-desc-free-parking-jackpot",
        )
    )
    income_tax_10pct: bool = option_field(
        BoolOption(
            default=False,
            label="monopoly-set-income-tax-10pct",
            change_msg="monopoly-option-changed-income-tax-10pct",
            description="monopoly-desc-income-tax-10pct",
        )
    )
    auction_start_10pct: bool = option_field(
        BoolOption(
            default=False,
            label="monopoly-set-auction-start-10pct",
            change_msg="monopoly-option-changed-auction-start-10pct",
            description="monopoly-desc-auction-start-10pct",
        )
    )


@dataclass
@register_game
class MonopolyGame(ActionGuardMixin, Game):
    """Monopoly board game (US or UK board, full classic rules)."""

    players: list[MonopolyPlayer] = field(default_factory=list)
    options: MonopolyOptions = field(default_factory=MonopolyOptions)
    chance_deck: list[dict] = field(default_factory=list)
    chest_deck: list[dict] = field(default_factory=list)
    phase: str = "roll"  # "roll" | "buy" | "auction"
    last_doubles: bool = False
    doubled_rolls: int = 0
    auction_space: int = -1
    auction_bid: int = 0
    auction_leader_id: str = ""
    auction_passed: list[str] = field(default_factory=list)
    declarer_id: str = ""  # Player whose landing started the auction
    last_dice: list[int] = field(default_factory=list)
    # Free Parking jackpot house rule
    jackpot: int = 0
    # Pending two-way trade offer
    pending_offer: dict | None = None  # from_id/to_id/give_space/give_cash/receive_space/receive_cash
    # Bot AI throttling
    bot_last_offer_round: int = 0

    @classmethod
    def get_name(cls) -> str:
        return "Monopoly"

    @classmethod
    def get_type(cls) -> str:
        return "monopoly"

    @classmethod
    def get_category(cls) -> str:
        return "category-board-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 8

    @classmethod
    def get_leaderboard_types(cls) -> list[dict]:
        """Monopoly-specific leaderboards."""
        return [
            {
                "id": "most_money",
                "path": "money.{player_name}",
                "aggregate": "max",
                "format": "score",
            },
            {
                "id": "properties_owned",
                "path": "stats.{player_name}.properties",
                "aggregate": "max",
                "format": "score",
            },
            {
                "id": "houses_built",
                "path": "stats.{player_name}.houses_built",
                "aggregate": "max",
                "format": "score",
            },
            {
                "id": "rent_collected",
                "path": "stats.{player_name}.rent_collected",
                "aggregate": "max",
                "format": "score",
            },
        ]

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> MonopolyPlayer:
        """Create a new player."""
        return MonopolyPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_start(self) -> None:
        """Start the game."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        active = self.get_active_players()
        for player in active:
            player.money = self.options.starting_money
            player.position = 0
            player.in_jail = False
            player.jail_turns = 0
            player.bankrupt = False
            player.properties = []
            player.houses = {}
            player.mortgaged = []
            player.built_this_turn = False
            player.jail_free_cards = 0
            player.jail_free_decks = []
            player.rent_collected = 0
            player.houses_built = 0
            player.trade_property = None
            player.trade_give_cash = None
            player.trade_target_id = ""
            player.trade_receive_property = None
            player.trade_receive_cash = None
        self.chance_deck = [dict(c) for c in CHANCE_CARDS]
        self.chest_deck = [dict(c) for c in CHEST_CARDS]
        random.shuffle(self.chance_deck)  # nosec B311
        random.shuffle(self.chest_deck)  # nosec B311
        self.jackpot = 0
        self.pending_offer = None
        self.bot_last_offer_round = 0
        self.set_turn_players(active)
        self.phase = "roll"
        self.play_music("game_pig/mus.ogg")
        self.play_sound("game_squares/start.ogg")
        self.broadcast_l("monopoly-start")
        self.announce_turn()
        self.rebuild_all_menus()

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    def advance_turn(self, announce: bool = True) -> "Player | None":
        """Advance the turn, expiring stale offers and counting round circuits."""
        old_index = self.turn_index
        current = self.current_player
        result = super().advance_turn(announce=announce)
        for p in self.players:
            p.built_this_turn = False
        # An offer not decided by the target's turn expiry is withdrawn.
        if self.pending_offer and current and current.id == self.pending_offer["to_id"]:
            from_p = self.get_player_by_id(self.pending_offer["from_id"])
            self.broadcast_l("monopoly-trade-expired", player=from_p.name if from_p else "?")
            self.pending_offer = None
        if self.turn_player_ids and old_index == len(self.turn_player_ids) - 1:
            self.round += 1
            self._end_round_check()
        return result

    def get_active_players(self) -> list[MonopolyPlayer]:  # type: ignore[override]
        """Players who have not gone bankrupt."""
        return [p for p in self.players if not p.is_spectator and not p.bankrupt]

    def _alive(self) -> list[MonopolyPlayer]:
        return self.get_active_players()

    def _locale_for(self, player: Player) -> str:
        user = self.get_user(player)
        return user.locale if user else "en"

    def _space_names(self) -> dict:
        return SPACE_NAMES_UK if self.options.board_variant == "uk" else SPACE_NAMES_US

    def _space_name(self, space: int, locale: str) -> str:
        return Localization.get(locale, self._space_names().get(space, "monopoly-space-unknown"))

    # ==========================================================================
    # Money helpers
    # ==========================================================================

    def _symbol(self) -> str:
        return "£" if self.options.board_variant == "uk" else "$"

    def _money(self, amount: int) -> str:
        """Format an amount with the board's currency symbol."""
        return f"{self._symbol()}{amount}"

    def _total_assets(self, player: MonopolyPlayer) -> int:
        """Money plus property and building value (used by the 10% income tax)."""
        total = player.money
        for space in player.properties:
            total += self._property_value(space)
        for space, count in player.houses.items():
            group = _group_of(space)
            total += count * HOUSE_COSTS.get(group or "", 100)
        return total

    def _collect(self, player: MonopolyPlayer, amount: int, source: MonopolyPlayer | None = None) -> None:
        player.money += amount
        if source and not source.bankrupt:
            source.money -= amount

    def _charge(self, player: MonopolyPlayer, amount: int, creditor: MonopolyPlayer | None) -> bool:
        """Take money; liquidate if needed; bankrupt if still short.

        Returns True if the player went bankrupt.
        """
        if amount <= 0:
            return False
        if player.money >= amount:
            player.money -= amount
            if creditor:
                creditor.money += amount
            return False

        # Liquidate: sell buildings first, then mortgage
        self._liquidate(player)
        if player.money >= amount:
            player.money -= amount
            if creditor:
                creditor.money += amount
            return False

        # Bankrupt: everything goes to the creditor (or the bank)
        owed = amount - player.money
        if creditor and not creditor.bankrupt:
            creditor.money += player.money
        player.money = 0
        for space in list(player.properties):
            player.properties.remove(space)
            player.houses.pop(space, None)
            if creditor:
                creditor.properties.append(space)
        player.mortgaged = []
        player.bankrupt = True
        # Get Out of Jail Free cards return to the bottom of their decks.
        if player.jail_free_cards > 0:
            for deck_key in player.jail_free_decks:
                target_deck = self.chance_deck if deck_key == "chance" else self.chest_deck
                target_deck.append({"kind": "goojf", "value": 0})
            player.jail_free_cards = 0
            player.jail_free_decks = []
        # A pending offer from the bankrupt player is void.
        if self.pending_offer and self.pending_offer["from_id"] == player.id:
            self.pending_offer = None
        self.play_sound("game_pig/lose.ogg")
        if creditor and not creditor.bankrupt:
            self.broadcast_l(
                "monopoly-bankrupt-to",
                player=player.name,
                creditor=creditor.name,
                amount=self._money(owed),
            )
        else:
            self.broadcast_l("monopoly-bankrupt", player=player.name)
        self._prune_rotation()
        self._check_win()
        return True

    def _liquidate(self, player: MonopolyPlayer) -> None:
        """Sell buildings and mortgage properties to raise cash."""
        for space in sorted(player.houses, key=lambda s: -player.houses[s]):
            count = player.houses[space]
            group = _group_of(space)
            cost = HOUSE_COSTS.get(group or "", 100)
            player.money += (count * cost) // 2
            player.houses[space] = 0
        for space in list(player.properties):
            if space not in player.mortgaged:
                player.mortgaged.append(space)
                player.money += self._mortgage_value(space)

    def _mortgage_value(self, space: int) -> int:
        if space in RAILROADS:
            return RAILROAD_PRICE // 2
        if space in UTILITIES:
            return UTILITY_PRICE // 2
        return PROPERTY_PRICES.get(space, 0) // 2

    def _property_value(self, space: int) -> int:
        if space in RAILROADS:
            return RAILROAD_PRICE
        if space in UTILITIES:
            return UTILITY_PRICE
        return PROPERTY_PRICES.get(space, 0)

    def _pay_tax(self, player: MonopolyPlayer, amount: int) -> None:
        """Pay a tax or fine; route to the Free Parking jackpot when enabled."""
        if self.options.free_parking_jackpot and amount > 0:
            self.jackpot += amount
            self.broadcast_l("monopoly-jackpot-grew", amount=self._money(amount))
        else:
            self._charge(player, amount, None)

    # ==========================================================================
    # Rent
    # ==========================================================================

    def _rent_due(self, space: int, owner: MonopolyPlayer, dice_sum: int) -> int:
        if space in RAILROADS:
            count = sum(1 for s in owner.properties if s in RAILROADS)
            return 25 * (2 ** (count - 1))
        if space in UTILITIES:
            owns_both = all(u in owner.properties for u in UTILITIES)
            return dice_sum * (10 if owns_both else 4)
        group = _group_of(space)
        houses = owner.houses.get(space, 0)
        if houses == 0 and group and all(s in owner.properties for s in GROUPS[group]):
            return BASE_RENTS[space] * 2  # Full set doubles base rent
        if self.options.rent_source == "classic":
            return RENT_TABLE.get(space, [BASE_RENTS[space]] * 6)[houses]
        return BASE_RENTS[space] * HOUSE_MULTIPLIERS[houses]

    # ==========================================================================
    # Movement and landing
    # ==========================================================================

    def _move(self, player: MonopolyPlayer, spaces: int, salary: bool = True) -> None:
        old = player.position
        new = (old + spaces) % 40
        if salary and old + spaces >= 40:
            player.money += SALARY
            self.broadcast_l("monopoly-passed-go", player=player.name, money=self._money(SALARY))
        player.position = new

    def _resolve_landing(self, player: MonopolyPlayer, space: int) -> None:
        """Resolve what happens when a player lands on space."""
        if space in PROPERTY_PRICES or space in RAILROADS or space in UTILITIES:
            owner = self._owner_of(space)
            if owner is not None and owner is not player:
                if space in owner.mortgaged:
                    self._speak(player, "monopoly-mortgaged-no-rent")
                    return
                rent = self._rent_due(space, owner, sum(self.last_dice))
                owner.rent_collected += rent
                self.broadcast_l(
                    "monopoly-paid-rent",
                    player=player.name,
                    owner=owner.name,
                    rent=self._money(rent),
                    space=self._space_name(space, "en"),
                )
                self._charge(player, rent, owner)
                return
            if owner is None:
                self.phase = "buy"
                self.broadcast_l(
                    "monopoly-landed-unowned",
                    player=player.name,
                    space=self._space_name(space, "en"),
                    price=self._money(self._property_value(space)),
                )
                self.rebuild_all_menus()
                return
            self._speak(player, "monopoly-your-property", space=self._space_name(space, "en"))
            return

        if space in TAXES:
            if space == 4 and self.options.income_tax_10pct:
                tax = self._total_assets(player) // 10
                self.broadcast_l("monopoly-tax-10pct", player=player.name, amount=self._money(tax))
                self._pay_tax(player, tax)
            else:
                tax = TAXES[space]
                self.broadcast_l(
                    "monopoly-tax",
                    player=player.name,
                    tax=self._money(tax),
                    space=self._space_name(space, "en"),
                )
                self._pay_tax(player, tax)
            return
        if space == 30:  # Go to Jail
            self._send_to_jail(player)
            return
        if space in (7, 22, 36):  # Chance
            card = self.chance_deck.pop(0)
            if card.get("kind") != "goojf":
                self.chance_deck.append(card)
            self._apply_card(player, card, "chance")
            return
        if space in (2, 17, 33):  # Community Chest
            card = self.chest_deck.pop(0)
            if card.get("kind") != "goojf":
                self.chest_deck.append(card)
            self._apply_card(player, card, "chest")
            return
        if space == 20:
            if self.options.free_parking_jackpot and self.jackpot > 0:
                player.money += self.jackpot
                self.play_sound("game_farkle/bank1.ogg")
                self.broadcast_l(
                    "monopoly-jackpot-won",
                    player=player.name,
                    amount=self._money(self.jackpot),
                )
                self.jackpot = 0
            else:
                user = self.get_user(player)
                if user:
                    user.speak_l("monopoly-free-parking", buffer="table")

    def _owner_of(self, space: int) -> MonopolyPlayer | None:
        for p in self._alive():
            if space in p.properties:
                return p
        return None

    def _speak(self, player: MonopolyPlayer, key: str, **kwargs) -> None:
        user = self.get_user(player)
        if user:
            user.speak_l(key, buffer="table", **kwargs)

    def _send_to_jail(self, player: MonopolyPlayer) -> None:
        player.in_jail = True
        player.jail_turns = 0
        player.position = 10
        self.play_sound("game_chess/capture2.ogg")
        self.broadcast_l("monopoly-sent-jail", player=player.name)

    # ==========================================================================
    # Chance / Community Chest
    # ==========================================================================

    def _apply_card(self, player: MonopolyPlayer, card: dict, deck_key: str) -> None:
        kind, value = card["kind"], card.get("value", 0)
        deck_text = "monopoly-chance" if deck_key == "chance" else "monopoly-chest"
        self.broadcast_l(
            "monopoly-card",
            player=player.name,
            deck=deck_text,
            card=self._card_name(card, "en"),
        )
        self.play_sound("game_cards/draw1.ogg")

        if kind == "collect":
            self._collect(player, value)
        elif kind == "pay":
            self._pay_tax(player, value)
        elif kind == "goojf":
            player.jail_free_cards += 1
            player.jail_free_decks.append(deck_key)
            self.broadcast_l("monopoly-card-goojf-holder", player=player.name)
        elif kind == "repairs":
            rate = value
            rate2 = card.get("value2", 0)
            # A hotel counts as 4 houses + 1 hotel for repair charges.
            houses = sum(min(c, MAX_BUILDINGS - 1) for c in player.houses.values())
            hotels = sum(1 for c in player.houses.values() if c >= MAX_BUILDINGS)
            total = houses * rate + hotels * rate2
            self.broadcast_l(
                "monopoly-card-repairs-total",
                player=player.name,
                amount=self._money(rate),
                amount2=self._money(rate2),
                total=self._money(total),
            )
            self._pay_tax(player, total)
        elif kind == "chairman":
            self.broadcast_l("monopoly-chairman", player=player.name, amount=self._money(value))
            for other in self._alive():
                if other is not player:
                    self._charge(other, value, player)
        elif kind == "birthday" or kind == "collect_from_all":
            key = "monopoly-card-birthday" if kind == "birthday" else "monopoly-card-collect-from-all"
            self.broadcast_l(key, player=player.name, amount=self._money(value))
            for other in self._alive():
                if other is not player:
                    self._charge(other, value, player)
        elif kind == "jail":
            self._send_to_jail(player)
        elif kind == "move_to":
            old = player.position
            # Advance to Go always collects the salary exactly once; other
            # advance cards collect it only when passing Go en route.
            self._move(player, (value - old) % 40, salary=(value != 0))
            if value == 0:
                player.money += SALARY
                self.broadcast_l("monopoly-passed-go", player=player.name, money=self._money(SALARY))
            self.broadcast_l("monopoly-moving", player=player.name, space=self._space_name(player.position, "en"))
            self._resolve_landing(player, player.position)
        elif kind == "back_3":
            player.position = (player.position - 3) % 40
            self.broadcast_l("monopoly-moving", player=player.name, space=self._space_name(player.position, "en"))
            self._resolve_landing(player, player.position)
        elif kind == "move_nearest_railroad":
            target = self._nearest_railroad(player.position)
            self.broadcast_l("monopoly-moving", player=player.name, space=self._space_name(target, "en"))
            self._move(player, (target - player.position) % 40, salary=False)
            owner = self._owner_of(target)
            if owner is not None and owner is not player and target not in owner.mortgaged:
                rent = 2 * self._rent_due(target, owner, sum(self.last_dice))
                owner.rent_collected += rent
                self.broadcast_l(
                    "monopoly-paid-rent",
                    player=player.name,
                    owner=owner.name,
                    rent=self._money(rent),
                    space=self._space_name(target, "en"),
                )
                self._charge(player, rent, owner)
        elif kind == "move_nearest_utility":
            target = self._nearest_utility(player.position)
            self.broadcast_l("monopoly-moving", player=player.name, space=self._space_name(target, "en"))
            self._move(player, (target - player.position) % 40, salary=False)
            owner = self._owner_of(target)
            if owner is not None and owner is not player and target not in owner.mortgaged:
                rent = sum(self.last_dice) * 10
                owner.rent_collected += rent
                self.broadcast_l(
                    "monopoly-paid-rent",
                    player=player.name,
                    owner=owner.name,
                    rent=self._money(rent),
                    space=self._space_name(target, "en"),
                )
                self._charge(player, rent, owner)

    def _card_name(self, card: dict, locale: str = "en") -> str:
        kind = card["kind"]
        value = card.get("value", 0)
        if kind == "collect":
            return Localization.get(locale, "monopoly-card-collect", amount=self._money(value))
        if kind == "pay":
            return Localization.get(locale, "monopoly-card-pay", amount=self._money(value))
        if kind == "jail":
            return Localization.get(locale, "monopoly-card-jail")
        if kind == "goojf":
            return Localization.get(locale, "monopoly-card-goojf")
        if kind == "repairs":
            return Localization.get(
                locale,
                "monopoly-card-repairs",
                amount=self._money(value),
                amount2=self._money(card.get("value2", 0)),
            )
        if kind == "move_to":
            if value == 0:
                return Localization.get(locale, "monopoly-card-move-go", money=self._money(SALARY))
            return Localization.get(locale, "monopoly-card-move-to", space=self._space_name(value, locale))
        if kind == "back_3":
            return Localization.get(locale, "monopoly-card-back-3")
        if kind == "move_nearest_railroad":
            return Localization.get(locale, "monopoly-card-railroad")
        if kind == "move_nearest_utility":
            return Localization.get(locale, "monopoly-card-utility")
        if kind == "chairman":
            return Localization.get(locale, "monopoly-card-chairman", amount=self._money(value))
        if kind == "birthday":
            return Localization.get(locale, "monopoly-card-birthday", amount=self._money(value))
        if kind == "collect_from_all":
            return Localization.get(locale, "monopoly-card-collect-from-all", amount=self._money(value))
        return Localization.get(locale, "monopoly-card-collect", amount=self._money(value))

    def _nearest_railroad(self, position: int) -> int:
        return min(RAILROADS, key=lambda r: (r - position) % 40)

    def _nearest_utility(self, position: int) -> int:
        return min(UTILITIES, key=lambda u: (u - position) % 40)

    # ==========================================================================
    # Rolling
    # ==========================================================================

    def _action_roll(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        if mp.bankrupt:
            return

        d1 = random.randint(1, 6)  # nosec B311
        d2 = random.randint(1, 6)  # nosec B311
        self.last_dice = [d1, d2]
        doubles = d1 == d2
        self.last_doubles = doubles
        self.play_standard_dice_roll_sound()
        self.broadcast_l("monopoly-rolled", player=player.name, dice=f"{d1}, {d2}")

        if mp.in_jail:
            if doubles:
                mp.in_jail = False
                mp.jail_turns = 0
                self.broadcast_l("monopoly-jail-doubles", player=player.name)
                self._move(mp, d1 + d2)
                self._finish_roll(mp, doubles=True)
                return
            mp.jail_turns += 1
            if mp.jail_turns >= 3:
                self.broadcast_l("monopoly-jail-pay", player=player.name, bail=self._money(BAIL))
                if self._charge(mp, BAIL, None):
                    self.phase = "roll"
                    return
                mp.in_jail = False
                mp.jail_turns = 0
                self._move(mp, d1 + d2)
                self._finish_roll(mp, doubles=doubles)
            else:
                self.broadcast_l("monopoly-jail-stays", player=player.name, turns=mp.jail_turns)
                self.advance_turn()
                self.phase = "roll"
            return

        self._move(mp, d1 + d2)
        if doubles:
            self.doubled_rolls += 1
            if self.doubled_rolls >= 3:
                self.doubled_rolls = 0
                self.broadcast_l("monopoly-three-doubles", player=player.name)
                self._send_to_jail(mp)
                self.advance_turn()
                self.phase = "roll"
                return
        else:
            self.doubled_rolls = 0

        self.broadcast_l(
            "monopoly-landed",
            player=player.name,
            space=self._space_name(mp.position, "en"),
        )
        self._finish_roll(mp, doubles=doubles)

    def _finish_roll(self, mp: MonopolyPlayer, doubles: bool) -> None:
        """Resolve the landing, then either stay (doubles) or advance."""
        self._resolve_landing(mp, mp.position)
        if mp.bankrupt:
            # Rotation was pruned; the next alive player is already current.
            self.phase = "roll"
            return
        if self.phase == "buy" or self.phase == "auction":
            return  # Awaiting decision
        self._advance_after_turn(mp, doubles)

    def _advance_after_turn(self, mp: MonopolyPlayer, doubles: bool) -> None:
        if not doubles or (getattr(mp, "in_jail", False)):
            self.advance_turn()
            self.phase = "roll"
            return
        # Doubles: same player's turn continues
        self.broadcast_l("monopoly-doubles-again", player=mp.name)
        self.phase = "roll"
        self.rebuild_all_menus()

    # ==========================================================================
    # Jail actions
    # ==========================================================================

    def _action_pay_bail(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        if not mp.in_jail:
            return
        if self._charge(mp, BAIL, None):
            self.phase = "roll"
            return
        mp.in_jail = False
        mp.jail_turns = 0
        self.play_sound("game_farkle/bank2.ogg")
        self.broadcast_l("monopoly-jail-bail-paid", player=player.name, bail=self._money(BAIL))
        self.rebuild_all_menus()

    def _action_use_jail_free(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        if not mp.in_jail or mp.jail_free_cards <= 0:
            return
        mp.jail_free_cards -= 1
        if mp.jail_free_decks:
            mp.jail_free_decks.pop()
        mp.in_jail = False
        mp.jail_turns = 0
        self.play_sound("game_cards/discard1.ogg")
        self.broadcast_l("monopoly-jail-card-used", player=player.name)
        self.rebuild_all_menus()

    # ==========================================================================
    # Buying
    # ==========================================================================

    def _action_buy(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "buy" or self.current_player != player:
            return
        space = mp.position
        if space in mp.properties or self._owner_of(space) is not None:
            self.phase = "roll"
            return
        price = self._property_value(space)
        if mp.money >= price:
            mp.money -= price
            mp.properties.append(space)
            self.play_sound("game_farkle/bank1.ogg")
            self.broadcast_l(
                "monopoly-bought",
                player=player.name,
                space=self._space_name(space, "en"),
                price=self._money(price),
            )
        else:
            user = self.get_user(player)
            if user:
                user.speak_l("monopoly-cannot-afford")
            return
        self.phase = "roll"
        self._advance_after_turn(mp, self.last_doubles)

    def _action_decline(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "buy" or self.current_player != player:
            return
        space = mp.position
        if self._owner_of(space) is None:
            self.broadcast_l("monopoly-auction", player=player.name, space=self._space_name(space, "en"))
            self._start_auction(space)
        else:
            self.phase = "roll"

    # ==========================================================================
    # Auctions
    # ==========================================================================

    def _start_auction(self, space: int) -> None:
        self.phase = "auction"
        self.auction_space = space
        if self.options.auction_start_10pct:
            self.auction_bid = self._property_value(space) // 10
        else:
            self.auction_bid = 0
        self.auction_leader_id = ""
        self.auction_passed = []
        self.declarer_id = self.current_player.id if self.current_player else ""
        alive = self._alive()
        self.set_turn_players(alive)
        self.turn_index = 0
        self.broadcast_l("monopoly-auction-start", space=self._space_name(space, "en"))
        self.rebuild_all_menus()

    def _action_auction_bid(self, player: Player, input_value: str, action_id: str) -> None:
        if self.phase != "auction" or self.current_player != player:
            return
        try:
            bid = int(input_value)
        except ValueError:
            return
        if bid <= self.auction_bid:
            self._speak(player, "monopoly-bid-higher", bid=self._money(self.auction_bid))
            return
        if player.bankrupt or player is self.get_player_by_id(self.auction_leader_id):
            return
        if bid > player.money:
            self._speak(player, "monopoly-cannot-afford", amount=self._money(bid))
            return
        self.auction_bid = bid
        self.auction_leader_id = player.id
        self.auction_passed = []
        self.play_sound("game_farkle/takepoint.ogg")
        self.broadcast_l("monopoly-bid", player=player.name, bid=self._money(bid))
        self._advance_auction()

    def _action_auction_pass(self, player: Player, action_id: str) -> None:
        if self.phase != "auction" or self.current_player != player:
            return
        # The current leader passing ends the auction in their favor
        if player.id == self.auction_leader_id:
            self._close_auction(player)  # type: ignore[arg-type]
            return
        if player.id not in self.auction_passed:
            self.auction_passed.append(player.id)
        self.broadcast_l("monopoly-passed", player=player.name)
        self._advance_auction()

    def _advance_auction(self) -> None:
        alive = self._alive()
        unpassed = [p for p in alive if p.id not in self.auction_passed]

        # The lone surviving bidder wins when everyone else has passed
        if self.auction_leader_id and len(unpassed) == 1 and unpassed[0].id == self.auction_leader_id:
            self._close_auction(unpassed[0])
            return
        if not unpassed:
            self._close_auction(None)
            return

        # Advance to the next unpassed player
        current = self.current_player
        idx = self.turn_player_ids.index(current.id) if current else 0
        for _ in range(len(self.turn_player_ids)):
            idx = (idx + 1) % len(self.turn_player_ids)
            if self.turn_player_ids[idx] not in self.auction_passed:
                self.turn_index = idx
                break
        self.rebuild_all_menus()

    def _close_auction(self, winner: MonopolyPlayer | None) -> None:
        space = self.auction_space
        bid = self.auction_bid
        self.phase = "roll"
        self.auction_space = -1
        self.auction_bid = 0
        self.auction_leader_id = ""
        self.auction_passed = []

        if winner is not None and not winner.bankrupt:
            if winner.money >= bid:
                winner.money -= bid
            else:
                winner.money = 0
            winner.properties.append(space)
            self.play_sound("game_farkle/bank1.ogg")
            self.broadcast_l(
                "monopoly-auction-won",
                player=winner.name,
                space=self._space_name(space, "en"),
                bid=self._money(bid),
            )
        else:
            self.broadcast_l("monopoly-auction-none", space=self._space_name(space, "en"))

        # Resume turns after the decliner
        alive = self._alive()
        declarer = self.get_player_by_id(self.declarer_id)
        self.declarer_id = ""
        if declarer in alive:
            idx = alive.index(declarer)
            order = alive[idx + 1:] + alive[:idx + 1]
        else:
            order = alive
        self.set_turn_players(order)
        self.turn_index = 0
        for p in self.players:
            p.built_this_turn = False
        self.announce_turn()
        self.rebuild_all_menus()

    # ==========================================================================
    # Building, mortgages, selling houses
    # ==========================================================================

    def _build_options(self, player: MonopolyPlayer) -> list[int]:
        """Spaces where this player can build (owns the full group, has room)."""
        result = []
        for group, spaces in GROUPS.items():
            if all(s in player.properties for s in spaces):
                for space in spaces:
                    if space in player.mortgaged:
                        continue
                    if player.houses.get(space, 0) < MAX_BUILDINGS:
                        result.append(space)
        return result

    def _action_build(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        try:
            space = int(input_value)
        except ValueError:
            return
        if space not in self._build_options(mp):
            return
        group = _group_of(space)
        cost = HOUSE_COSTS.get(group or "", 100)
        if mp.money < cost:
            self._speak(player, "monopoly-cannot-afford-build", cost=self._money(cost))
            return
        mp.money -= cost
        mp.houses[space] = mp.houses.get(space, 0) + 1
        mp.houses_built += 1
        self.play_sound("game_dominos/play.ogg")
        self.broadcast_l(
            "monopoly-built",
            player=player.name,
            space=self._space_name(space, "en"),
            houses=mp.houses[space],
        )
        self.rebuild_all_menus()

    def _sell_house_options(self, player: Player) -> list[str]:
        mp: MonopolyPlayer = player  # type: ignore
        return [str(s) for s in mp.houses if mp.houses[s] > 0]

    def _action_sell_house(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        try:
            space = int(input_value)
        except ValueError:
            return
        if space not in mp.houses or mp.houses[space] <= 0:
            return
        group = _group_of(space)
        cost = HOUSE_COSTS.get(group or "", 100)
        mp.houses[space] -= 1
        if mp.houses[space] == 0:
            del mp.houses[space]
        value = cost // 2
        mp.money += value
        self.play_sound("game_farkle/bank2.ogg")
        self.broadcast_l(
            "monopoly-sold-house",
            player=player.name,
            space=self._space_name(space, "en"),
            value=self._money(value),
        )
        self.rebuild_all_menus()

    def _action_mortgage(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        try:
            space = int(input_value)
        except ValueError:
            return
        if space not in mp.properties or space in mp.mortgaged:
            return
        if mp.houses.get(space, 0) > 0:
            self._speak(player, "monopoly-sell-houses-first")
            return
        mp.mortgaged.append(space)
        value = self._mortgage_value(space)
        mp.money += value
        self.play_sound("game_farkle/bank2.ogg")
        self.broadcast_l(
            "monopoly-mortgaged",
            player=player.name,
            space=self._space_name(space, "en"),
            value=self._money(value),
        )
        self.rebuild_all_menus()

    def _action_unmortgage(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        try:
            space = int(input_value)
        except ValueError:
            return
        if space not in mp.mortgaged:
            return
        cost = int(self._mortgage_value(space) * 1.1)
        if mp.money < cost:
            self._speak(player, "monopoly-cannot-afford", amount=self._money(cost))
            return
        mp.money -= cost
        mp.mortgaged.remove(space)
        self.play_sound("game_farkle/bank1.ogg")
        self.broadcast_l(
            "monopoly-unmortgaged",
            player=player.name,
            space=self._space_name(space, "en"),
            cost=self._money(cost),
        )
        self.rebuild_all_menus()

    # ==========================================================================
    # Two-way trades
    # ==========================================================================

    def _trade_step_state(self, player: Player) -> int:
        """Which wizard step the player's draft is at (1-6)."""
        mp: MonopolyPlayer = player  # type: ignore
        if mp.trade_property is None:
            return 1
        if mp.trade_give_cash is None:
            return 2
        if not mp.trade_target_id:
            return 3
        if mp.trade_receive_property is None:
            return 4
        if mp.trade_receive_cash is None:
            return 5
        return 6

    def _reset_trade_draft(self, player: Player) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        mp.trade_property = None
        mp.trade_give_cash = None
        mp.trade_target_id = ""
        mp.trade_receive_property = None
        mp.trade_receive_cash = None

    def _offer_side_desc(self, space: int, cash: int, locale: str) -> str:
        parts = []
        if space >= 0:
            parts.append(self._space_name(space, locale))
        if cash > 0:
            parts.append(self._money(cash))
        if not parts:
            return Localization.get(locale, "monopoly-trade-nothing")
        return " + ".join(parts)

    def _action_trade_property(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        try:
            space = int(input_value)
        except ValueError:
            return
        if space != 0 and space not in mp.properties:
            return
        mp.trade_property = space
        mp.trade_give_cash = None
        mp.trade_target_id = ""
        mp.trade_receive_property = None
        mp.trade_receive_cash = None
        self.update_player_menu(player)

    def _action_trade_cash(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player or mp.trade_property is None:
            return
        try:
            cash = max(0, int(input_value))
        except ValueError:
            return
        mp.trade_give_cash = cash
        self.update_player_menu(player)

    def _action_trade_target(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player or mp.trade_give_cash is None:
            return
        target = self.get_player_by_name(input_value)
        if target is None or target is player or target.bankrupt:
            return
        mp.trade_target_id = target.id
        mp.trade_receive_property = None
        mp.trade_receive_cash = None
        self.update_player_menu(player)

    def _action_trade_get_property(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player or not mp.trade_target_id:
            return
        try:
            space = int(input_value)
        except ValueError:
            return
        target = self.get_player_by_id(mp.trade_target_id)
        if target is None or target.bankrupt:
            self._reset_trade_draft(player)
            self.update_player_menu(player)
            return
        if space != 0 and space not in target.properties:
            return
        mp.trade_receive_property = space
        mp.trade_receive_cash = None
        self.update_player_menu(player)

    def _action_trade_get_cash(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player or mp.trade_receive_property is None:
            return
        try:
            cash = max(0, int(input_value))
        except ValueError:
            return
        mp.trade_receive_cash = cash
        self.update_player_menu(player)

    def _action_trade_post(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        if self.pending_offer is not None:
            self._speak(player, "monopoly-trade-blocked")
            return
        if self._trade_step_state(player) != 6:
            return
        give_space = mp.trade_property or 0
        give_cash = mp.trade_give_cash or 0
        target = self.get_player_by_id(mp.trade_target_id)
        receive_space = mp.trade_receive_property or 0
        receive_cash = mp.trade_receive_cash or 0
        if target is None or target.bankrupt:
            self._reset_trade_draft(player)
            return
        if give_space != 0 and give_space not in mp.properties:
            self._reset_trade_draft(player)
            return
        if receive_space != 0 and receive_space not in target.properties:
            self._reset_trade_draft(player)
            return
        if give_cash > mp.money:
            self._speak(player, "monopoly-trade-cannot-give", name=player.name)
            self._reset_trade_draft(player)
            return
        if give_space == 0 and give_cash <= 0 and receive_space == 0 and receive_cash <= 0:
            self._speak(player, "monopoly-trade-empty")
            self._reset_trade_draft(player)
            return
        self.pending_offer = {
            "from_id": player.id,
            "to_id": target.id,
            "give_space": give_space,
            "give_cash": give_cash,
            "receive_space": receive_space,
            "receive_cash": receive_cash,
        }
        self._reset_trade_draft(player)
        give_desc = self._offer_side_desc(give_space, give_cash, "en")
        recv_desc = self._offer_side_desc(receive_space, receive_cash, "en")
        self.play_sound("game_cards/discard1.ogg")
        self.broadcast_l(
            "monopoly-trade-offer",
            player=player.name,
            target=target.name,
            give=give_desc,
            receive=recv_desc,
        )
        self.rebuild_all_menus()

    def _action_trade_cancel(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        if self._trade_step_state(player) == 1:
            return
        self._reset_trade_draft(player)
        user = self.get_user(player)
        if user:
            user.speak_l("monopoly-trade-draft-cancelled", buffer="table")
        self.rebuild_all_menus()

    def _action_accept_trade(self, player: Player, action_id: str) -> None:
        if self.phase != "roll" or self.current_player != player:
            return
        offer = self.pending_offer
        if not offer or offer["to_id"] != player.id:
            return
        from_p = self.get_player_by_id(offer["from_id"])
        to_p: MonopolyPlayer = player  # type: ignore
        if from_p is None or from_p.bankrupt:
            self.pending_offer = None
            self.rebuild_all_menus()
            return
        give_space, give_cash = offer["give_space"], offer["give_cash"]
        recv_space, recv_cash = offer["receive_space"], offer["receive_cash"]
        if from_p.money < give_cash:
            self._speak(player, "monopoly-trade-cannot-give", name=from_p.name)
            self.pending_offer = None
            self.rebuild_all_menus()
            return
        if to_p.money < recv_cash:
            self._speak(player, "monopoly-trade-cannot-get", name=player.name)
            return
        if give_space != 0 and give_space in from_p.properties:
            from_p.properties.remove(give_space)
            to_p.properties.append(give_space)
            from_p.houses.pop(give_space, None)
            if give_space in from_p.mortgaged:
                from_p.mortgaged.remove(give_space)
        if recv_space != 0 and recv_space in to_p.properties:
            to_p.properties.remove(recv_space)
            from_p.properties.append(recv_space)
            to_p.houses.pop(recv_space, None)
            if recv_space in to_p.mortgaged:
                to_p.mortgaged.remove(recv_space)
        from_p.money -= give_cash
        to_p.money += give_cash
        to_p.money -= recv_cash
        from_p.money += recv_cash
        give_desc = self._offer_side_desc(give_space, give_cash, "en")
        recv_desc = self._offer_side_desc(recv_space, recv_cash, "en")
        self.play_sound("game_cards/discard1.ogg")
        self.broadcast_l(
            "monopoly-trade-accepted",
            player=from_p.name,
            target=to_p.name,
            give=give_desc,
            receive=recv_desc,
        )
        self.pending_offer = None
        self.rebuild_all_menus()

    def _action_reject_trade(self, player: Player, action_id: str) -> None:
        if self.phase != "roll" or self.current_player != player:
            return
        offer = self.pending_offer
        if not offer or offer["to_id"] != player.id:
            return
        from_p = self.get_player_by_id(offer["from_id"])
        self.broadcast_l(
            "monopoly-trade-rejected",
            target=player.name,
            player=from_p.name if from_p else "?",
        )
        self.pending_offer = None
        self.rebuild_all_menus()

    def _action_cancel_offer(self, player: Player, action_id: str) -> None:
        if self.phase != "roll" or self.current_player != player:
            return
        offer = self.pending_offer
        if not offer or offer["from_id"] != player.id:
            return
        self.broadcast_l("monopoly-trade-cancelled", player=player.name)
        self.pending_offer = None
        self.rebuild_all_menus()

    def _action_end_turn(self, player: Player, action_id: str) -> None:
        if self.phase != "roll" or self.current_player != player:
            return
        self.advance_turn()
        self.phase = "roll"

    # ==========================================================================
    # Status / board overview
    # ==========================================================================

    def _action_status(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        user = self.get_user(player)
        if user:
            pos = self._space_name(mp.position, user.locale)
            user.speak_l(
                "monopoly-status-info",
                money=self._money(mp.money),
                space=pos,
                houses=sum(mp.houses.values()),
            )

    def _action_board(self, player: Player, action_id: str) -> None:
        user = self.get_user(player)
        if not user:
            return
        locale = user.locale
        for p in self._alive():
            parts = []
            for space in p.properties:
                name = self._space_name(space, locale)
                if p.houses.get(space, 0) >= MAX_BUILDINGS:
                    name += " (hotel)"
                elif p.houses.get(space, 0) > 0:
                    name += f" ({p.houses[space]})"
                if space in p.mortgaged:
                    name += " (M)"
                parts.append(name)
            props = ", ".join(parts) if parts else Localization.get(locale, "monopoly-board-empty")
            user.speak_l(
                "monopoly-board-info",
                player=p.name,
                money=self._money(p.money),
                properties=props,
                buffer="table",
            )

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_roll_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "roll":
            return "monopoly-not-your-phase"
        return None

    def _is_roll_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player, extra_condition=self.phase == "roll")

    def _is_manage_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player, extra_condition=self.phase == "roll")

    def _is_buy_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "buy":
            return "monopoly-not-your-phase"
        mp: MonopolyPlayer = player  # type: ignore
        if self._owner_of(mp.position) is not None or mp.position in mp.properties:
            return "monopoly-not-available"
        return None

    def _is_buy_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player, extra_condition=self.phase == "buy")

    def _get_buy_label(self, player: Player, action_id: str) -> str:
        mp: MonopolyPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        price = self._property_value(mp.position)
        return Localization.get(locale, "monopoly-buy", price=self._money(price))

    def _is_decline_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "buy":
            return "monopoly-not-your-phase"
        return None

    def _is_decline_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player, extra_condition=self.phase == "buy")

    def _is_auction_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "auction":
            return "monopoly-not-your-phase"
        return None

    def _is_auction_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player, extra_condition=self.phase == "auction")

    def _get_bid_label(self, player: Player, action_id: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "monopoly-bid-action", bid=self._money(self.auction_bid))

    # --- Jail actions ---

    def _is_pay_bail_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "roll":
            return "monopoly-not-your-phase"
        mp: MonopolyPlayer = player  # type: ignore
        if not mp.in_jail:
            return "monopoly-not-in-jail"
        return None

    def _is_pay_bail_hidden(self, player: Player) -> Visibility:
        mp: MonopolyPlayer = player  # type: ignore
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and mp.in_jail
        )

    def _is_use_jail_free_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "roll":
            return "monopoly-not-your-phase"
        mp: MonopolyPlayer = player  # type: ignore
        if not mp.in_jail:
            return "monopoly-not-in-jail"
        if mp.jail_free_cards <= 0:
            return "monopoly-no-jail-free-card"
        return None

    def _is_use_jail_free_hidden(self, player: Player) -> Visibility:
        mp: MonopolyPlayer = player  # type: ignore
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and mp.in_jail and mp.jail_free_cards > 0
        )

    # --- Trade wizard ---

    def _trade_guard(self, player: Player, step: int) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "roll":
            return "monopoly-not-your-phase"
        if self._trade_step_state(player) != step:
            return "monopoly-not-your-phase"
        return None

    def _is_trade_enabled(self, player: Player) -> str | None:
        return self._trade_guard(player, 1)

    def _is_trade_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and self._trade_step_state(player) == 1
        )

    def _is_trade_cash_enabled(self, player: Player) -> str | None:
        return self._trade_guard(player, 2)

    def _is_trade_cash_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and self._trade_step_state(player) == 2
        )

    def _is_trade_target_enabled(self, player: Player) -> str | None:
        return self._trade_guard(player, 3)

    def _is_trade_target_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and self._trade_step_state(player) == 3
        )

    def _is_trade_get_property_enabled(self, player: Player) -> str | None:
        return self._trade_guard(player, 4)

    def _is_trade_get_property_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and self._trade_step_state(player) == 4
        )

    def _is_trade_get_cash_enabled(self, player: Player) -> str | None:
        return self._trade_guard(player, 5)

    def _is_trade_get_cash_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and self._trade_step_state(player) == 5
        )

    def _is_trade_post_enabled(self, player: Player) -> str | None:
        return self._trade_guard(player, 6)

    def _is_trade_post_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player,
            extra_condition=self.phase == "roll"
            and self._trade_step_state(player) == 6
            and self.pending_offer is None,
        )

    def _is_trade_cancel_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and self._trade_step_state(player) >= 2
        )

    # --- Pending offer actions ---

    def _has_pending_offer_for(self, player: Player) -> bool:
        return bool(self.pending_offer) and self.pending_offer["to_id"] == player.id

    def _has_pending_offer_from(self, player: Player) -> bool:
        return bool(self.pending_offer) and self.pending_offer["from_id"] == player.id

    def _is_accept_trade_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "roll":
            return "monopoly-not-your-phase"
        if not self._has_pending_offer_for(player):
            return "monopoly-not-available"
        return None

    def _is_accept_trade_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and self._has_pending_offer_for(player)
        )

    def _is_reject_trade_enabled(self, player: Player) -> str | None:
        return self._is_accept_trade_enabled(player)

    def _is_reject_trade_hidden(self, player: Player) -> Visibility:
        return self._is_accept_trade_hidden(player)

    def _is_cancel_offer_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "roll":
            return "monopoly-not-your-phase"
        if not self._has_pending_offer_from(player):
            return "monopoly-not-available"
        return None

    def _is_cancel_offer_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(
            player, extra_condition=self.phase == "roll" and self._has_pending_offer_from(player)
        )

    # --- Labels ---

    def _get_end_turn_label(self, player: Player, action_id: str) -> str:
        mp: MonopolyPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "monopoly-end-turn", money=self._money(mp.money))

    def _get_status_label(self, player: Player, action_id: str) -> str:
        mp: MonopolyPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        pos = self._space_name(mp.position, locale)
        return Localization.get(locale, "monopoly-status", money=self._money(mp.money), space=pos)

    # ==========================================================================
    # Menu input helpers
    # ==========================================================================

    def _auction_bid_input(self, player: Player) -> str:
        return str(self.auction_bid + 10)

    def _bot_auction_bid(self, player: Player) -> str:
        return str(self.auction_bid + 10)

    def _build_options_str(self, player: Player) -> list[str]:
        mp: MonopolyPlayer = player  # type: ignore
        buildable = self._build_options(mp)
        order = sorted(buildable, key=self._property_value, reverse=True)
        return [str(s) for s in order]

    def _build_option_label(self, player: Player, option: str) -> str:
        try:
            space = int(option)
        except ValueError:
            return option
        group = _group_of(space)
        cost = HOUSE_COSTS.get(group or "", 100)
        name = self._space_name(space, self._locale_for(player))
        return f"{name} ({cost})"

    def _mortgage_options(self, player: Player) -> list[str]:
        mp: MonopolyPlayer = player  # type: ignore
        return [str(s) for s in mp.properties if s not in mp.mortgaged and mp.houses.get(s, 0) == 0]

    def _unmortgage_options(self, player: Player) -> list[str]:
        mp: MonopolyPlayer = player  # type: ignore
        return [str(s) for s in mp.mortgaged]

    def _trade_property_options(self, player: Player) -> list[str]:
        mp: MonopolyPlayer = player  # type: ignore
        return [str(s) for s in mp.properties] + ["0"]

    def _trade_target_options(self, player: Player) -> list[str]:
        return [p.name for p in self._alive() if p is not player]

    def _trade_get_property_options(self, player: Player) -> list[str]:
        mp: MonopolyPlayer = player  # type: ignore
        target = self.get_player_by_id(mp.trade_target_id) if mp.trade_target_id else None
        if target is None or target.bankrupt:
            return ["0"]
        return [str(s) for s in target.properties] + ["0"]

    def _property_option_label(self, player: Player, option: str) -> str:
        try:
            space = int(option)
        except ValueError:
            return option
        if space == 0:
            return Localization.get(self._locale_for(player), "monopoly-trade-cash-only")
        return self._space_name(space, self._locale_for(player))

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def _bot_wants_buy(self, player: MonopolyPlayer, space: int) -> bool:
        price = self._property_value(space)
        reserve = 300
        group = _group_of(space)
        if group:
            owned = sum(1 for s in GROUPS[group] if s in player.properties)
            if owned == len(GROUPS[group]) - 1:
                # Completing a group is worth stretching for.
                return player.money >= price + 100
        return player.money >= price + reserve

    def _bot_should_build(self, player: MonopolyPlayer) -> bool:
        if not self._build_options(player):
            return False
        buildable = self._build_options(player)
        group = _group_of(buildable[0])
        cost = HOUSE_COSTS.get(group or "", 100)
        return player.money >= cost * 3

    def _bot_sell_options(self, player: MonopolyPlayer) -> list[int]:
        return [s for s in player.houses if player.houses[s] > 0]

    def _group_complete(self, player: MonopolyPlayer, space: int) -> bool:
        group = _group_of(space)
        return bool(group) and all(s in player.properties for s in GROUPS[group])

    def _bot_offer_plan(self, player: MonopolyPlayer) -> tuple | None:
        """Return (give_space, give_cash, target_id, receive_space, receive_cash) or None."""
        # 1) Complete a group: buy the missing member with cash.
        for group, spaces in GROUPS.items():
            owned = [s for s in spaces if s in player.properties]
            missing = [s for s in spaces if s not in player.properties]
            if len(owned) == len(spaces) - 1 and len(missing) == 1:
                target = self._owner_of(missing[0])
                if target is not None and target is not player and not target.bankrupt:
                    price = int(self._property_value(missing[0]) * 1.2)
                    if player.money >= price:
                        return (0, price, target.id, missing[0], 0)
        # 2) Raise cash: sell a non-essential property to the richest player.
        if player.money < 250 and len(player.properties) > 2:
            sellable = [s for s in player.properties if not self._group_complete(player, s)]
            if sellable:
                space = min(sellable, key=self._property_value)
                targets = [p for p in self._alive() if p is not player and not p.bankrupt]
                targets.sort(key=lambda p: -p.money)
                if targets:
                    price = int(self._property_value(space) * 0.8)
                    return (space, 0, targets[0].id, 0, price)
        return None

    def _bot_trade_decision(self, player: MonopolyPlayer) -> str:
        """Decide whether to accept or reject a pending offer."""
        offer = self.pending_offer
        from_p = self.get_player_by_id(offer["from_id"]) if offer else None
        if from_p is None or from_p.bankrupt:
            return "reject_trade"
        # From the target's perspective: gain the give side, pay the receive side.
        give_value = (
            (self._property_value(offer["give_space"]) if offer["give_space"] != 0 else 0)
            + offer["give_cash"]
        )
        recv_value = (
            (self._property_value(offer["receive_space"]) if offer["receive_space"] != 0 else 0)
            + offer["receive_cash"]
        )
        # A gained property that completes a group is worth more.
        if offer["give_space"] != 0:
            group = _group_of(offer["give_space"])
            if group and all(
                s in player.properties or s == offer["give_space"] for s in GROUPS[group]
            ):
                give_value = int(give_value * 1.5)
        # Losing a property that completes one of your groups hurts more.
        if offer["receive_space"] != 0:
            group = _group_of(offer["receive_space"])
            if group and all(s in player.properties for s in GROUPS[group]):
                recv_value = int(recv_value * 1.5)
        if player.money >= offer["receive_cash"] and give_value >= recv_value:
            return "accept_trade"
        return "reject_trade"

    def _bot_trade_property(self, player: Player, options: list[str]) -> str | None:
        plan = self._bot_offer_plan(player)  # type: ignore[arg-type]
        if plan is not None:
            give = plan[0]
            return "0" if give == 0 else str(give)
        return "0" if "0" in options else (options[0] if options else None)

    def _bot_trade_cash(self, player: Player) -> str:
        plan = self._bot_offer_plan(player)  # type: ignore[arg-type]
        return str(plan[1] if plan is not None else 0)

    def _bot_trade_target(self, player: Player, options: list[str]) -> str | None:
        plan = self._bot_offer_plan(player)  # type: ignore[arg-type]
        if plan is not None and plan[2]:
            target = self.get_player_by_id(plan[2])
            if target is not None and target.name in options:
                return target.name
        return options[0] if options else None

    def _bot_trade_get_property(self, player: Player, options: list[str]) -> str | None:
        plan = self._bot_offer_plan(player)  # type: ignore[arg-type]
        if plan is not None:
            recv = plan[3]
            if recv != 0 and str(recv) in options:
                return str(recv)
        return "0" if "0" in options else (options[0] if options else None)

    def _bot_trade_get_cash(self, player: Player) -> str:
        plan = self._bot_offer_plan(player)  # type: ignore[arg-type]
        return str(plan[4] if plan is not None else 0)

    def _bot_build_choice(self, player: Player, options: list[str]) -> str | None:
        mp: MonopolyPlayer = player  # type: ignore
        buildable = self._build_options(mp)
        if not buildable:
            return None
        # Even building: prefer the most valuable group, then its least-developed property.
        groups: dict[str, list[int]] = {}
        for space in buildable:
            g = _group_of(space)
            if g:
                groups.setdefault(g, []).append(space)
        if not groups:
            return str(buildable[0])
        best_group = max(groups, key=lambda g: (HOUSE_COSTS.get(g, 100), len(groups[g])))
        members = groups[best_group]
        target = min(members, key=lambda s: mp.houses.get(s, 0))
        return str(target)

    def _bot_sell_house_choice(self, player: Player, options: list[str]) -> str | None:
        if not options:
            return None
        spaces = [int(s) for s in options]
        mp: MonopolyPlayer = player  # type: ignore
        return str(max(spaces, key=lambda s: mp.houses.get(s, 0)))

    def _bot_mortgage_choice(self, player: Player, options: list[str]) -> str | None:
        if not options:
            return None
        spaces = [int(s) for s in options]
        return str(min(spaces, key=self._property_value))

    def _bot_unmortgage_choice(self, player: Player, options: list[str]) -> str | None:
        if not options:
            return None
        mp: MonopolyPlayer = player  # type: ignore
        affordable = [s for s in options if mp.money >= int(self._mortgage_value(int(s)) * 1.1)]
        if not affordable:
            return None
        return str(min(map(int, affordable), key=self._property_value))

    def bot_think(self, player: MonopolyPlayer) -> str | None:
        """Bot AI for the current phase."""
        if player.bankrupt:
            return None
        if self.phase == "buy":
            if self._bot_wants_buy(player, player.position):
                return "buy"
            return "decline"
        if self.phase == "auction":
            space = self.auction_space
            value = self._property_value(space)
            group = _group_of(space)
            if group and all(
                s in player.properties or s == space for s in GROUPS[group]
            ):
                value = int(value * 1.5)
            max_bid = min(player.money - 200, int(value * 1.4))
            if player.id == self.auction_leader_id:
                return "auction_pass"
            if self.auction_bid < max_bid and player.money > value:
                return "auction_bid"
            return "auction_pass"
        if self.phase == "roll":
            # Continue a trade wizard in progress.
            if player.trade_property is not None:
                if player.trade_give_cash is None:
                    return "trade_cash"
                if not player.trade_target_id:
                    return "trade_target"
                if player.trade_receive_property is None:
                    return "trade_get_property"
                if player.trade_receive_cash is None:
                    return "trade_get_cash"
                return "trade_post"
            # Decide on a pending offer.
            if self.pending_offer and self.pending_offer["to_id"] == player.id:
                return self._bot_trade_decision(player)
            # Jail decisions.
            if player.in_jail:
                if player.jail_free_cards > 0:
                    return "use_jail_free"
                if player.money >= 300:
                    return "pay_bail"
                return "roll"
            # Occasionally post trade offers.
            if self.round >= self.bot_last_offer_round + 3 and self._bot_offer_plan(player) is not None:
                self.bot_last_offer_round = self.round
                return "trade_property"
            # Manage cash and buildings.
            if not player.built_this_turn and self._bot_should_build(player):
                player.built_this_turn = True
                return "build"
            if player.money < 300:
                if self._bot_sell_options(player):
                    return "sell_house"
                if self._mortgage_options(player):
                    return "mortgage"
            return "roll"

    # ==========================================================================
    # Win handling
    # ==========================================================================

    def _prune_rotation(self) -> None:
        """Remove bankrupt players from the turn rotation."""
        alive_ids = [p.id for p in self._alive()]
        self.turn_player_ids = [pid for pid in self.turn_player_ids if pid in alive_ids]
        if not self.turn_player_ids:
            return
        if self.turn_index >= len(self.turn_player_ids):
            self.turn_index = 0
        if self.status == "playing":
            self.announce_turn()
            self.rebuild_all_menus()

    def _check_win(self) -> None:
        alive = self._alive()
        if len(alive) <= 1 and len(self.players) > 1:
            if alive:
                winner = alive[0]
                self.play_sound("game_pig/win.ogg")
                self.broadcast_l("monopoly-winner", player=winner.name)
                self.finish_game()
            elif len(self.players) == 1:
                winner = self.players[0]
                self.play_sound("game_pig/win.ogg")
                self.broadcast_l("monopoly-winner", player=winner.name)
                self.finish_game()

    def _end_round_check(self) -> None:
        """Called between turns for the max_rounds cap."""
        if self.options.max_rounds > 0 and self.round >= self.options.max_rounds:
            alive = self._alive()
            if len(alive) > 1:
                rich = max(alive, key=lambda p: p.money)
                self.play_sound("game_pig/win.ogg")
                self.broadcast_l(
                    "monopoly-winner-money",
                    player=rich.name,
                    money=self._money(rich.money),
                )
                self.finish_game()

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        alive = self.get_active_players()
        all_players = [p for p in self.players if not p.is_spectator]
        money = {p.name: p.money for p in all_players}
        winner_name = None
        if len(self.players) > 1 and len(alive) == 1:
            winner_name = alive[0].name
        elif len(self.players) == 1:
            winner_name = self.players[0].name

        return GameResult(
            game_type=self.get_type(),
            timestamp=datetime.now().isoformat(),
            duration_ticks=self.sound_scheduler_tick,
            player_results=[
                PlayerResult(
                    player_id=p.id,
                    player_name=p.name,
                    is_bot=p.is_bot,
                    is_virtual_bot=getattr(p, "is_virtual_bot", False),
                )
                for p in all_players
            ],
            custom_data={
                "winner_name": winner_name,
                "money": money,
                "max_rounds": self.options.max_rounds,
                "board_variant": self.options.board_variant,
                "stats": {
                    p.name: {
                        "properties": len(p.properties),
                        "houses_built": p.houses_built,
                        "rent_collected": p.rent_collected,
                    }
                    for p in all_players
                },
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        money = result.custom_data.get("money", {})
        for name, value in sorted(money.items(), key=lambda kv: -kv[1]):
            lines.append(
                Localization.get(locale, "monopoly-score-line", player=name, money=self._money(value))
            )
        return lines

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: MonopolyPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="status",
                label=Localization.get(locale, "monopoly-status", money="", space="-"),
                handler="_action_status",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                get_label="_get_status_label",
                show_in_actions_menu=False,
            )
        )
        action_set.add(
            Action(
                id="board",
                label=Localization.get(locale, "monopoly-board"),
                handler="_action_board",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                show_in_actions_menu=True,
            )
        )
        action_set.add(
            Action(
                id="roll",
                label=Localization.get(locale, "monopoly-roll"),
                handler="_action_roll",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_roll_hidden",
            )
        )
        action_set.add(
            Action(
                id="buy",
                label=Localization.get(locale, "monopoly-buy", price=""),
                handler="_action_buy",
                is_enabled="_is_buy_enabled",
                is_hidden="_is_buy_hidden",
                get_label="_get_buy_label",
            )
        )
        action_set.add(
            Action(
                id="decline",
                label=Localization.get(locale, "monopoly-decline"),
                handler="_action_decline",
                is_enabled="_is_decline_enabled",
                is_hidden="_is_decline_hidden",
            )
        )
        action_set.add(
            Action(
                id="auction_bid",
                label=Localization.get(locale, "monopoly-bid-action", bid=""),
                handler="_action_auction_bid",
                is_enabled="_is_auction_enabled",
                is_hidden="_is_auction_hidden",
                get_label="_get_bid_label",
                input_request=EditboxInput(
                    prompt="monopoly-enter-bid",
                    default="10",
                    bot_input="_bot_auction_bid",
                ),
            )
        )
        action_set.add(
            Action(
                id="auction_pass",
                label=Localization.get(locale, "monopoly-pass-action"),
                handler="_action_auction_pass",
                is_enabled="_is_auction_enabled",
                is_hidden="_is_auction_hidden",
            )
        )
        action_set.add(
            Action(
                id="pay_bail",
                label=Localization.get(locale, "monopoly-pay-bail", bail=self._money(BAIL)),
                handler="_action_pay_bail",
                is_enabled="_is_pay_bail_enabled",
                is_hidden="_is_pay_bail_hidden",
            )
        )
        action_set.add(
            Action(
                id="use_jail_free",
                label=Localization.get(locale, "monopoly-use-jail-free"),
                handler="_action_use_jail_free",
                is_enabled="_is_use_jail_free_enabled",
                is_hidden="_is_use_jail_free_hidden",
            )
        )
        action_set.add(
            Action(
                id="build",
                label=Localization.get(locale, "monopoly-build"),
                handler="_action_build",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                input_request=MenuInput(
                    prompt="monopoly-pick-build",
                    options="_build_options_str",
                    option_label="_build_option_label",
                    bot_select="_bot_build_choice",
                ),
            )
        )
        action_set.add(
            Action(
                id="sell_house",
                label=Localization.get(locale, "monopoly-sell-house"),
                handler="_action_sell_house",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                input_request=MenuInput(
                    prompt="monopoly-pick-sell-house",
                    options="_sell_house_options",
                    option_label="_property_option_label",
                    bot_select="_bot_sell_house_choice",
                ),
            )
        )
        action_set.add(
            Action(
                id="mortgage",
                label=Localization.get(locale, "monopoly-mortgage"),
                handler="_action_mortgage",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                input_request=MenuInput(
                    prompt="monopoly-pick-mortgage",
                    options="_mortgage_options",
                    option_label="_property_option_label",
                    bot_select="_bot_mortgage_choice",
                ),
            )
        )
        action_set.add(
            Action(
                id="unmortgage",
                label=Localization.get(locale, "monopoly-unmortgage"),
                handler="_action_unmortgage",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                input_request=MenuInput(
                    prompt="monopoly-pick-unmortgage",
                    options="_unmortgage_options",
                    option_label="_property_option_label",
                    bot_select="_bot_unmortgage_choice",
                ),
            )
        )
        action_set.add(
            Action(
                id="trade_property",
                label=Localization.get(locale, "monopoly-trade"),
                handler="_action_trade_property",
                is_enabled="_is_trade_enabled",
                is_hidden="_is_trade_hidden",
                input_request=MenuInput(
                    prompt="monopoly-pick-trade",
                    options="_trade_property_options",
                    option_label="_property_option_label",
                    bot_select="_bot_trade_property",
                ),
            )
        )
        action_set.add(
            Action(
                id="trade_cash",
                label=Localization.get(locale, "monopoly-trade-cash"),
                handler="_action_trade_cash",
                is_enabled="_is_trade_cash_enabled",
                is_hidden="_is_trade_cash_hidden",
                input_request=EditboxInput(
                    prompt="monopoly-enter-trade-cash",
                    default="0",
                    bot_input="_bot_trade_cash",
                ),
            )
        )
        action_set.add(
            Action(
                id="trade_target",
                label=Localization.get(locale, "monopoly-trade-target"),
                handler="_action_trade_target",
                is_enabled="_is_trade_target_enabled",
                is_hidden="_is_trade_target_hidden",
                input_request=MenuInput(
                    prompt="monopoly-pick-trade-target",
                    options="_trade_target_options",
                    bot_select="_bot_trade_target",
                ),
            )
        )
        action_set.add(
            Action(
                id="trade_get_property",
                label=Localization.get(locale, "monopoly-trade-get-property"),
                handler="_action_trade_get_property",
                is_enabled="_is_trade_get_property_enabled",
                is_hidden="_is_trade_get_property_hidden",
                input_request=MenuInput(
                    prompt="monopoly-pick-trade-get-property",
                    options="_trade_get_property_options",
                    option_label="_property_option_label",
                    bot_select="_bot_trade_get_property",
                ),
            )
        )
        action_set.add(
            Action(
                id="trade_get_cash",
                label=Localization.get(locale, "monopoly-trade-get-cash"),
                handler="_action_trade_get_cash",
                is_enabled="_is_trade_get_cash_enabled",
                is_hidden="_is_trade_get_cash_hidden",
                input_request=EditboxInput(
                    prompt="monopoly-enter-trade-get-cash",
                    default="0",
                    bot_input="_bot_trade_get_cash",
                ),
            )
        )
        action_set.add(
            Action(
                id="trade_post",
                label=Localization.get(locale, "monopoly-trade-post"),
                handler="_action_trade_post",
                is_enabled="_is_trade_post_enabled",
                is_hidden="_is_trade_post_hidden",
            )
        )
        action_set.add(
            Action(
                id="trade_cancel",
                label=Localization.get(locale, "monopoly-trade-cancel"),
                handler="_action_trade_cancel",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_trade_cancel_hidden",
            )
        )
        action_set.add(
            Action(
                id="accept_trade",
                label=Localization.get(locale, "monopoly-trade-accept"),
                handler="_action_accept_trade",
                is_enabled="_is_accept_trade_enabled",
                is_hidden="_is_accept_trade_hidden",
            )
        )
        action_set.add(
            Action(
                id="reject_trade",
                label=Localization.get(locale, "monopoly-trade-reject"),
                handler="_action_reject_trade",
                is_enabled="_is_reject_trade_enabled",
                is_hidden="_is_reject_trade_hidden",
            )
        )
        action_set.add(
            Action(
                id="cancel_offer",
                label=Localization.get(locale, "monopoly-cancel-offer"),
                handler="_action_cancel_offer",
                is_enabled="_is_cancel_offer_enabled",
                is_hidden="_is_cancel_offer_hidden",
            )
        )
        action_set.add(
            Action(
                id="end_turn",
                label=Localization.get(locale, "monopoly-end-turn", money=""),
                handler="_action_end_turn",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                get_label="_get_end_turn_label",
            )
        )
        return action_set

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("space", "Roll dice", ["roll"], state=KeybindState.ACTIVE)
        self.define_keybind("e", "End turn", ["end_turn"], state=KeybindState.ACTIVE)
        self.define_keybind("b", "Buy property", ["buy"], state=KeybindState.ACTIVE)


__all__ = [
    "MonopolyGame",
    "MonopolyPlayer",
    "MonopolyOptions",
    "SPACE_NAMES",
    "SPACE_NAMES_US",
    "SPACE_NAMES_UK",
    "RENT_TABLE",
]