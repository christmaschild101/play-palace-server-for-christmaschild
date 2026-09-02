"""
Monopoly Game Implementation for PlayPalace.

Full classic rules: 40-space American board, properties with house building
and mortgages, railroads and utilities, income/luxury taxes, Chance and
Community Chest cards, jail (doubles, bail, three-turn limit), auctions for
declined properties, and player-to-player trades. Players go bankrupt until
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
from ...game_utils.options import IntOption, option_field
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState

# fmt: off
SPACE_NAMES = {
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
# Houses 0-4 cost doubled each level; a 5th upgrade is a hotel (32x)
HOUSE_MULTIPLIERS = [1, 2, 4, 8, 16, 32]
MAX_BUILDINGS = 5  # 0-4 houses + hotel
TAXES = {4: 200, 38: 100}
START_MONEY = 1500
SALARY = 200
BAIL = 50

CHANCE_CARDS = [
    ("collect", 50), ("move_to", 0), ("jail", 0), ("move_to", 24),
    ("move_to", 11), ("move_nearest_railroad", 0), ("move_nearest_railroad", 0),
    ("collect", 150), ("pay", 15), ("move_to", 5), ("move_to", 39),
    ("back_3", 0), ("chairman", 50), ("move_nearest_utility", 0), ("pay", 50), ("collect", 100),
]
CHEST_CARDS = [
    ("move_to", 0), ("collect", 200), ("pay", 50), ("collect", 50),
    ("jail", 0), ("collect", 100), ("collect", 20), ("birthday", 10),
    ("pay", 100), ("pay", 150), ("collect", 25), ("collect", 10),
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
    # Trade flow state
    trade_property: int | None = None
    trade_target_id: str = ""


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


@dataclass
@register_game
class MonopolyGame(ActionGuardMixin, Game):
    """Monopoly board game (full classic rules)."""

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
        """Monopoly-specific leaderboard: richest finish."""
        return [
            {
                "id": "most_money",
                "path": "money.{player_name}",
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
        self.chance_deck = [{"kind": k, "value": v} for k, v in CHANCE_CARDS]
        self.chest_deck = [{"kind": k, "value": v} for k, v in CHEST_CARDS]
        random.shuffle(self.chance_deck)  # nosec B311
        random.shuffle(self.chest_deck)  # nosec B311
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
        """Advance the turn, counting full circuits for the round cap."""
        old_index = self.turn_index
        result = super().advance_turn(announce=announce)
        for p in self.players:
            p.built_this_turn = False
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

    def _space_name(self, space: int, locale: str) -> str:
        return Localization.get(locale, SPACE_NAMES.get(space, "monopoly-space-unknown"))

    # ==========================================================================
    # Money helpers
    # ==========================================================================

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
        self.play_sound("game_pig/lose.ogg")
        if creditor and not creditor.bankrupt:
            self.broadcast_l(
                "monopoly-bankrupt-to",
                player=player.name,
                creditor=creditor.name,
                amount=owed,
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
        return BASE_RENTS[space] * HOUSE_MULTIPLIERS[houses]

    # ==========================================================================
    # Movement and landing
    # ==========================================================================

    def _move(self, player: MonopolyPlayer, spaces: int, salary: bool = True) -> None:
        old = player.position
        new = (old + spaces) % 40
        if salary and old + spaces >= 40:
            player.money += SALARY
            self.broadcast_l("monopoly-passed-go", player=player.name)
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
                self.broadcast_l(
                    "monopoly-paid-rent",
                    player=player.name,
                    owner=owner.name,
                    rent=rent,
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
                    price=self._property_value(space),
                )
                self.rebuild_all_menus()
                return
            self._speak(player, "monopoly-your-property", space=self._space_name(space, "en"))
            return

        if space in TAXES:
            tax = TAXES[space]
            self.broadcast_l("monopoly-tax", player=player.name, tax=tax, space=self._space_name(space, "en"))
            self._charge(player, tax, None)
            return
        if space == 30:  # Go to Jail
            self._send_to_jail(player)
            return
        if space in (7, 22, 36):  # Chance
            card = self.chance_deck.pop(0)
            self.chance_deck.append(card)
            self._apply_card(player, card, "chance")
            return
        if space in (2, 17, 33):  # Community Chest
            card = self.chest_deck.pop(0)
            self.chest_deck.append(card)
            self._apply_card(player, card, "chest")
            return
        if space == 20:
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
        kind, value = card["kind"], card["value"]
        deck_text = "monopoly-chance" if deck_key == "chance" else "monopoly-chest"
        self.broadcast_l(
            "monopoly-card",
            player=player.name,
            deck=deck_text,
            card=self._card_name(card),
        )
        self.play_sound("game_cards/draw1.ogg")

        if kind == "collect":
            self._collect(player, value)
        elif kind == "pay":
            self._charge(player, value, None)
        elif kind == "chairman":
            self.broadcast_l("monopoly-chairman", player=player.name, amount=value)
            for other in self._alive():
                if other is not player:
                    self._charge(other, value, player)
        elif kind == "birthday":
            self.broadcast_l("monopoly-birthday", player=player.name, amount=value)
            for other in self._alive():
                if other is not player:
                    self._charge(other, value, player)
        elif kind == "jail":
            self._send_to_jail(player)
        elif kind == "move_to":
            old = player.position
            self._move(player, (value - old) % 40)
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
                self.broadcast_l(
                    "monopoly-paid-rent",
                    player=player.name,
                    owner=owner.name,
                    rent=rent,
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
                self.broadcast_l(
                    "monopoly-paid-rent",
                    player=player.name,
                    owner=owner.name,
                    rent=rent,
                    space=self._space_name(target, "en"),
                )
                self._charge(player, rent, owner)

    def _card_name(self, card: dict) -> str:
        kind, value = card["kind"], card["value"]
        keys = {
            "collect": "monopoly-card-collect",
            "pay": "monopoly-card-pay",
            "jail": "monopoly-card-jail",
            "move_to": "monopoly-card-move",
            "back_3": "monopoly-card-back-3",
            "move_nearest_railroad": "monopoly-card-railroad",
            "move_nearest_utility": "monopoly-card-utility",
            "chairman": "monopoly-card-chairman",
            "birthday": "monopoly-card-birthday",
        }
        key = keys.get(kind, "monopoly-card-collect")
        return Localization.get("en", key, amount=value)

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
                self.broadcast_l("monopoly-jail-pay", player=player.name, bail=BAIL)
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
            self.broadcast_l("monopoly-bought", player=player.name, space=self._space_name(space, "en"), price=price)
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
            self._speak(player, "monopoly-bid-higher", bid=self.auction_bid)
            return
        if player.bankrupt or player is self.get_player_by_id(self.auction_leader_id):
            return
        self.auction_bid = bid
        self.auction_leader_id = player.id
        self.auction_passed = []
        self.play_sound("game_farkle/takepoint.ogg")
        self.broadcast_l("monopoly-bid", player=player.name, bid=bid)
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
                bid=bid,
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
    # Building, mortgages, trades
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
            self._speak(player, "monopoly-cannot-afford-build", cost=cost)
            return
        mp.money -= cost
        mp.houses[space] = mp.houses.get(space, 0) + 1
        self.play_sound("game_dominos/play.ogg")
        self.broadcast_l(
            "monopoly-built",
            player=player.name,
            space=self._space_name(space, "en"),
            houses=mp.houses[space],
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
        self.broadcast_l("monopoly-mortgaged", player=player.name, space=self._space_name(space, "en"), value=value)
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
            self._speak(player, "monopoly-cannot-afford", amount=cost)
            return
        mp.money -= cost
        mp.mortgaged.remove(space)
        self.play_sound("game_farkle/bank1.ogg")
        self.broadcast_l("monopoly-unmortgaged", player=player.name, space=self._space_name(space, "en"), cost=cost)
        self.rebuild_all_menus()

    def _action_trade_property(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        try:
            space = int(input_value)
        except ValueError:
            return
        if space not in mp.properties:
            return
        mp.trade_property = space
        self.update_player_menu(player)

    def _action_trade_target(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player or mp.trade_property is None:
            return
        target = self.get_player_by_name(input_value)
        if target is None or target is player or target.bankrupt:
            return
        mp.trade_target_id = target.id
        self.update_player_menu(player)

    def _action_trade_price(self, player: Player, input_value: str, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        if self.phase != "roll" or self.current_player != player:
            return
        if mp.trade_property is None or not mp.trade_target_id:
            return
        try:
            price = max(0, int(input_value))
        except ValueError:
            return
        target = self.get_player_by_id(mp.trade_target_id)
        if target is None or target.bankrupt:
            mp.trade_property = None
            mp.trade_target_id = ""
            return
        space = mp.trade_property
        if target.money < price:
            self._speak(player, "monopoly-target-afford", player=target.name)
            return
        target.money -= price
        mp.money += price
        mp.properties.remove(space)
        mp.houses.pop(space, None)
        if space in mp.mortgaged:
            mp.mortgaged.remove(space)
        target.properties.append(space)
        mp.trade_property = None
        mp.trade_target_id = ""
        self.play_sound("game_cards/discard1.ogg")
        self.broadcast_l(
            "monopoly-traded",
            player=player.name,
            target=target.name,
            space=self._space_name(space, "en"),
            price=price,
        )
        self.rebuild_all_menus()

    def _action_end_turn(self, player: Player, action_id: str) -> None:
        if self.phase != "roll" or self.current_player != player:
            return
        self.advance_turn()
        self.phase = "roll"

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
        return Localization.get(locale, "monopoly-buy", price=price)

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
        return Localization.get(locale, "monopoly-bid-action", bid=self.auction_bid)

    def _get_end_turn_label(self, player: Player, action_id: str) -> str:
        mp: MonopolyPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "monopoly-end-turn", money=mp.money)

    def _get_status_label(self, player: Player, action_id: str) -> str:
        mp: MonopolyPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        pos = self._space_name(mp.position, locale)
        return Localization.get(locale, "monopoly-status", money=mp.money, space=pos)

    def _action_status(self, player: Player, action_id: str) -> None:
        mp: MonopolyPlayer = player  # type: ignore
        user = self.get_user(player)
        if user:
            pos = self._space_name(mp.position, user.locale)
            user.speak_l("monopoly-status-info", money=mp.money, space=pos, houses=sum(mp.houses.values()))

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
        return [str(s) for s in mp.properties]

    def _trade_target_options(self, player: Player) -> list[str]:
        return [p.name for p in self._alive() if p is not player]

    def _property_option_label(self, player: Player, option: str) -> str:
        try:
            space = int(option)
        except ValueError:
            return option
        return self._space_name(space, self._locale_for(player))

    def _bot_trade_target(self, player: Player, options: list[str]) -> str | None:
        for other in self._alive():
            if other is not player and other.name in options and other.money >= 50:
                return other.name
        return options[0] if options else None

    def _bot_trade_price(self, player: Player, options: list[str]) -> str:
        return ""

    def _bot_build_choice(self, player: Player, options: list[str]) -> str | None:
        mp: MonopolyPlayer = player  # type: ignore
        buildable = self._build_options(mp)
        if not buildable:
            return None
        # Build on the group's most expensive property
        best = max(buildable, key=self._property_value)
        return str(best)

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
                label=Localization.get(locale, "monopoly-status", money=0, space="-"),
                handler="_action_status",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                get_label="_get_status_label",
                show_in_actions_menu=False,
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
                label=Localization.get(locale, "monopoly-buy", price=0),
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
                label=Localization.get(locale, "monopoly-bid-action", bid=0),
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
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
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
                id="trade_target",
                label=Localization.get(locale, "monopoly-trade-target"),
                handler="_action_trade_target",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                input_request=MenuInput(
                    prompt="monopoly-pick-trade-target",
                    options="_trade_target_options",
                    bot_select="_bot_trade_target",
                ),
            )
        )
        action_set.add(
            Action(
                id="trade_price",
                label=Localization.get(locale, "monopoly-trade-price"),
                handler="_action_trade_price",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                input_request=EditboxInput(
                    prompt="monopoly-enter-trade-price",
                    default="0",
                    bot_input="_bot_trade_price",
                ),
            )
        )
        action_set.add(
            Action(
                id="end_turn",
                label=Localization.get(locale, "monopoly-end-turn", money=0),
                handler="_action_end_turn",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_manage_hidden",
                get_label="_get_end_turn_label",
            )
        )
        return action_set

    def _bot_trade_property(self, player: Player, options: list[str]) -> str | None:
        if not options:
            return None
        return str(min(map(int, options), key=self._property_value))

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("space", "Roll dice", ["roll"], state=KeybindState.ACTIVE)
        self.define_keybind("e", "End turn", ["end_turn"], state=KeybindState.ACTIVE)
        self.define_keybind("b", "Buy property", ["buy"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def _bot_wants_buy(self, player: MonopolyPlayer, space: int) -> bool:
        worth = self._property_value(space)
        base = 500
        if player.money >= worth + base:
            return True
        return False

    def _bot_should_build(self, player: MonopolyPlayer) -> bool:
        if not self._build_options(player):
            return False
        buildable = self._build_options(player)
        group = _group_of(buildable[0])
        cost = HOUSE_COSTS.get(group or "", 100)
        return player.money >= cost * 3

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
            worth = int(self._property_value(space) * 1.4)
            if player.id == self.auction_leader_id:
                return "auction_pass"
            if player.money > worth + 300 and self.auction_bid < worth:
                return "auction_bid"
            return "auction_pass"
        if self.phase == "roll":
            if len(player.properties) < 2:
                return "roll"
            if self._bot_should_build(player) and not player.built_this_turn:
                player.built_this_turn = True
                return "build"
            if player.money < 250:
                options = self._mortgage_options(player)
                if options:
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
                    money=rich.money,
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
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        money = result.custom_data.get("money", {})
        for name, value in sorted(money.items(), key=lambda kv: -kv[1]):
            lines.append(Localization.get(locale, "monopoly-score-line", player=name, money=value))
        return lines


__all__ = ["MonopolyGame", "MonopolyPlayer", "MonopolyOptions"]