"""Moto Strike Game Implementation for PlayPalace.

A port of the TableEx card racing game. Riders race to be the first to cross
the finish line of a 2000-meter track. On each turn a rider plays one card
(or discards one) and the hand refills to five.

Concepts (unique to this game):
  - Movement cards (Easy Ride 25m / Speed Boost 50m / Power Dash 75m) advance
    the rider.
  - Trap cards (Mud / Spike / Rock) are played directly on an opponent. A Mud
    Trap stops them until they play a Rebalance card; Spike and Rock Traps
    damage the wheel as well, requiring both a Repair and a Rebalance card.
  - Attack cards: Smoke Bomb slows the rider directly behind (25m), Electric
    Shock forces the nearest rider within 50m to discard a random card, and
    Police Chase gives the rider ahead two turns to play a Maneuver card
    before they are immobilized until they play an Escape card.
  - Specials: Quick Kick knocks an opponent back 200m, Deadly Kick (usable
    after covering 1000m) eliminates a rider from the race, Kick Shield and
    Emergency Swerve are held and consumed automatically when they block a
    kick or a trap.
  - Maneuver cards (Slight/Full turns) escape an active Police Chase, and
    when played as a normal action move the rider 10m or 25m.
  - Recovery cards (Rebalance / Repair / Escape) clear bike statuses.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player
from ..registry import register_game
from ...game_utils.actions import Action, ActionSet, MenuInput, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.game_status import GameStatus
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState

from .cards import (
    Card,
    CardType,
    Deck,
    MANEUVER_VALUES,
    MOVEMENT_VALUES,
)
from .options import MotoStrikeOptions
from .player import MotoStrikePlayer

# Hand size (a new card is drawn automatically after any play or discard)
HAND_SIZE = 5

# Turns an opponent has to escape a Police Chase with a Maneuver card
CHASE_WINDOW = 2

# Distance the rider must cover before Deadly Kick becomes usable
DEADLY_KICK_MIN_DISTANCE = 1000

# Smoke Bomb and Quick Kick knock-backs in meters
SMOKE_KNOCKBACK = 25
QUICK_KICK_KNOCKBACK = 200

# Attack range for Electric Shock
SHOCK_RANGE = 50

# How close to the finish a healthy bot stops racing and attacks the leader
BOT_ATTACK_FINISH_MARGIN = 400


@dataclass
@register_game
class MotoStrikeGame(Game):
    """Moto Strike - card-based motorcycle racing."""

    players: list[MotoStrikePlayer] = field(default_factory=list)
    options: MotoStrikeOptions = field(default_factory=MotoStrikeOptions)

    # Game state
    deck: Deck = field(default_factory=Deck)
    discard_pile: list[Card] = field(default_factory=list)
    intro_wait_ticks: int = 0
    race_winner_id: str | None = None

    def __post_init__(self):
        super().__post_init__()

    # ==========================================================================
    # Metadata
    # ==========================================================================

    @classmethod
    def get_name(cls) -> str:
        return "Moto Strike"

    @classmethod
    def get_type(cls) -> str:
        return "motostrike"

    @classmethod
    def get_category(cls) -> str:
        return "category-card-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 6

    @classmethod
    def get_leaderboard_types(cls) -> list[dict]:
        return [
            {
                "id": "best_finish",
                "path": "final_distances.{player_name}",
                "aggregate": "max",
                "format": "score",
            },
            {
                "id": "avg_finish",
                "path": "final_distances.{player_name}",
                "aggregate": "avg",
                "format": "avg",
            },
        ]

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> MotoStrikePlayer:
        """Create a new rider."""
        return MotoStrikePlayer(id=player_id, name=name, is_bot=is_bot)

    # ==========================================================================
    # Game flow
    # ==========================================================================

    def on_start(self) -> None:
        """Set up the deck, deal hands, and start the race."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        self.round = 1
        self.race_winner_id = None
        self.intro_wait_ticks = 0

        self._team_manager.team_mode = "individual"
        self._team_manager.setup_teams([p.name for p in self.players if not p.is_spectator])

        self.play_music("game_pig/mus.ogg")

        # Fresh deck
        self.deck = Deck()
        self.deck.build_standard_deck()
        self.deck.shuffle()
        self.discard_pile = []

        active = [p for p in self.players if not p.is_spectator]
        for p in active:
            if isinstance(p, MotoStrikePlayer):
                p.reset()
                p.hand = []

        self.set_turn_players(active, reset_index=True)

        # Deal 5 cards to each rider
        for _ in range(HAND_SIZE):
            for p in active:
                if isinstance(p, MotoStrikePlayer):
                    card = self.deck.draw()
                    if card:
                        p.hand.append(card)

        # Random starting rider
        if active:
            self.turn_index = random.randrange(len(active))  # nosec B311

        self.broadcast_l("motostrike-race-start", meters=self.options.track_length)
        self.play_sound("game_pig/roundstart.ogg")
        self.intro_wait_ticks = 4 * 20

    def on_tick(self) -> None:
        super().on_tick()
        if not self.game_active:
            return
        if self.intro_wait_ticks > 0:
            self.intro_wait_ticks -= 1
            if self.intro_wait_ticks == 0:
                self._start_turn()
            return
        BotHelper.on_tick(self)

    def _start_turn(self) -> None:
        """Begin the current rider's turn (skipping eliminated riders)."""
        player = self.current_player
        if not isinstance(player, MotoStrikePlayer):
            return
        if player.eliminated:
            self.advance_turn(announce=False)
            self.rebuild_all_menus()
            self._start_turn()
            return
        if player.is_bot:
            BotHelper.jolt_bot(player, ticks=random.randint(30, 40))  # nosec B311
        self.announce_turn()
        self._sync_turn_actions(player)
        self.rebuild_all_menus()

    def _advance_turn(self) -> None:
        """Advance to the next rider's turn."""
        self.advance_turn(announce=False)
        self.rebuild_all_menus()
        self._start_turn()

    def _finish_play(self, player: MotoStrikePlayer, *, played_maneuver: bool) -> None:
        """Common end-of-action processing: refill, chase countdown, win check."""
        self._refill_hand(player)
        self._sync_team_scores()

        # Police Chase countdown: the rider's turn ended without playing a Maneuver
        if player.police_chase_turns > 0 and not played_maneuver:
            player.police_chase_turns -= 1
            if player.police_chase_turns == 0:
                player.immobilized = True
                self.play_sound("game_chess/moveking.ogg")
                self.broadcast_l("motostrike-chase-immobilized", target=player.name)
            else:
                self.broadcast_l(
                    "motostrike-chase-window", target=player.name, turns=player.police_chase_turns
                )

        if self._check_race_winner(player):
            return
        self._advance_turn()

    def _check_race_winner(self, player: MotoStrikePlayer) -> bool:
        """End the race if the rider crossed the finish line."""
        if player.distance >= self.options.track_length:
            self._end_race(player, by_elimination=False)
            return True
        return False

    def _end_race(self, winner: MotoStrikePlayer, *, by_elimination: bool) -> None:
        """Finish the race with the given winner."""
        self.race_winner_id = winner.id
        self.play_sound("game_pig/wingame.ogg")
        if by_elimination:
            self.broadcast_l("motostrike-winner-elimination", winner=winner.name)
        else:
            self.broadcast_l(
                "motostrike-winner", winner=winner.name, meters=self.options.track_length
            )
        for p in self.players:
            user = self.get_user(p)
            if user:
                user.remove_menu("turn_menu")
        self.finish_game()

    # ==========================================================================
    # Action sets / keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: MotoStrikePlayer) -> ActionSet:
        """Create the turn action set (card slots are synced dynamically)."""
        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="discard_card",
                label="Discard selected card",
                handler="_action_discard_card",
                is_enabled="_is_turn_action_enabled",
                is_hidden="_is_always_hidden",
                show_in_actions_menu=False,
            )
        )
        return action_set

    def create_standard_action_set(self, player: Player) -> ActionSet:
        """Add race status actions to the standard set."""
        action_set = super().create_standard_action_set(player)
        user = self.get_user(player)
        locale = user.locale if user else "en"
        local_actions = [
            Action(
                id="bike_status",
                label=Localization.get(locale, "motostrike-bike-status-action"),
                handler="_action_bike_status",
                is_enabled="_is_check_enabled",
                is_hidden="_is_check_hidden",
            ),
            Action(
                id="race_status",
                label=Localization.get(locale, "motostrike-race-status-action"),
                handler="_action_race_status",
                is_enabled="_is_check_enabled",
                is_hidden="_is_check_hidden",
            ),
        ]
        for action in reversed(local_actions):
            action_set.add(action)
            if action.id in action_set._order:
                action_set._order.remove(action.id)
            action_set._order.insert(0, action.id)
        return action_set

    def setup_keybinds(self) -> None:
        super().setup_keybinds()
        self.define_keybind(
            "space",
            "Bike status",
            ["bike_status"],
            state=KeybindState.ACTIVE,
        )
        self.define_keybind(
            "c",
            "Race status",
            ["race_status"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )
        # Shift+Enter / Backspace discard the currently selected card
        self.define_keybind(
            "shift+enter",
            "Discard selected card",
            ["discard_card"],
            state=KeybindState.ACTIVE,
        )
        self.define_keybind(
            "backspace",
            "Discard selected card",
            ["discard_card"],
            state=KeybindState.ACTIVE,
        )

    # ==========================================================================
    # Menu syncing
    # ==========================================================================

    def rebuild_player_menu(self, player: Player) -> None:
        self._sync_turn_actions(player)
        super().rebuild_player_menu(player)

    def update_player_menu(self, player: Player, selection_id: str | None = None) -> None:
        self._sync_turn_actions(player)
        super().update_player_menu(player, selection_id=selection_id)

    def rebuild_all_menus(self) -> None:
        for player in self.players:
            self._sync_turn_actions(player)
        super().rebuild_all_menus()

    def _sync_turn_actions(self, player: Player) -> None:
        """Rebuild card slot actions to match the rider's current hand."""
        if not isinstance(player, MotoStrikePlayer):
            return
        turn_set = self.get_action_set(player, "turn")
        if not turn_set:
            return
        turn_set.remove_by_prefix("card_slot_")
        if self.status != GameStatus.PLAYING or player.is_spectator:
            return
        for i, card in enumerate(player.hand, 1):
            action_id = f"card_slot_{i}"
            turn_set.add(
                Action(
                    id=action_id,
                    label="",
                    handler="_action_play_card",
                    is_enabled="_is_turn_action_enabled",
                    is_hidden="_is_card_action_hidden",
                    get_label="_get_card_label",
                    input_request=self._input_for_card(card),
                    show_in_actions_menu=False,
                )
            )

    def _input_for_card(self, card: Card) -> MenuInput | None:
        """Return a target-selection menu for cards that need one."""
        needs_target = card.card_type == CardType.TRAP or (
            card.card_type == CardType.SPECIAL and card.value in ("quick_kick", "deadly_kick")
        )
        if needs_target:
            return MenuInput(
                prompt="motostrike-target-prompt",
                options="_target_options",
                bot_select="_bot_select_target",
            )
        return None

    # ==========================================================================
    # Action guards
    # ==========================================================================

    def _is_check_enabled(self, player: Player) -> str | None:
        if self.status != GameStatus.PLAYING:
            return "action-not-playing"
        return None

    def _is_check_hidden(self, player: Player) -> Visibility:
        return Visibility.HIDDEN

    def _is_turn_action_enabled(self, player: Player) -> str | None:
        if self.status != GameStatus.PLAYING:
            return "action-not-playing"
        if player.is_spectator:
            return "action-spectator"
        if self.current_player != player:
            return "action-not-your-turn"
        if self.intro_wait_ticks > 0:
            return "action-not-available"
        return None

    def _is_card_action_hidden(self, player: Player) -> Visibility:
        if self.status != GameStatus.PLAYING:
            return Visibility.HIDDEN
        if player.is_spectator:
            return Visibility.HIDDEN
        if not isinstance(player, MotoStrikePlayer):
            return Visibility.HIDDEN
        if self.current_player != player:
            return Visibility.HIDDEN
        if self.intro_wait_ticks > 0:
            return Visibility.HIDDEN
        return Visibility.VISIBLE

    def _is_always_hidden(self, player: Player) -> Visibility:
        return Visibility.HIDDEN

    # ==========================================================================
    # Card label / localization
    # ==========================================================================

    def _localized_card_name(self, card: Card, locale: str) -> str:
        """Get the localized name for a card."""
        key = "motostrike-card-" + card.value.replace("_", "-")
        name = Localization.get(locale, key)
        if name.startswith("[") and name.endswith("]"):
            return card.name
        return name

    def _card_en(self, card: Card) -> str:
        """Get the English card name for table broadcasts."""
        return card.name

    def _player_locale(self, player: Player) -> str:
        user = self.get_user(player)
        return user.locale if user else "en"

    def _get_card_label(self, player: Player, action_id: str) -> str:
        if not isinstance(player, MotoStrikePlayer):
            return action_id
        try:
            slot = int(action_id.split("_")[-1]) - 1
        except (ValueError, IndexError):
            return action_id
        if slot < 0 or slot >= len(player.hand):
            return action_id
        card = player.hand[slot]
        locale = self._player_locale(player)
        name = self._localized_card_name(card, locale)
        if card.card_type == CardType.MOVEMENT:
            return f"{name} {MOVEMENT_VALUES.get(card.value, 0)}"
        if card.card_type == CardType.MANEUVER:
            return f"{name} {MANEUVER_VALUES.get(card.value, 0)}"
        return name

    # ==========================================================================
    # Card playability
    # ==========================================================================

    def _can_play(self, player: MotoStrikePlayer, card: Card) -> tuple[bool, str | None]:
        """Check if a card can be played. Returns (playable, reason key)."""
        if player.eliminated:
            return False, "motostrike-reason-eliminated"

        card_type = card.card_type

        if card_type == CardType.MOVEMENT:
            if not player.can_move():
                return False, self._movement_blocked_reason(player)
            return True, None

        if card_type == CardType.MANEUVER:
            # Maneuvers always work as a Police Chase escape
            if player.police_chase_turns > 0:
                return True, None
            if not player.can_move():
                return False, self._movement_blocked_reason(player)
            return True, None

        if card_type == CardType.RECOVERY:
            if card.value == "rebalance":
                return player.stuck, "motostrike-reason-not-stuck"
            if card.value == "repair":
                return player.wheel_damaged, "motostrike-reason-wheel-fine"
            if card.value == "escape":
                return player.immobilized, "motostrike-reason-not-immobilized"
            return False, "motostrike-reason-generic"

        if card_type == CardType.TRAP:
            return bool(self._opponents(player)), "motostrike-reason-no-target"

        if card_type == CardType.SPECIAL:
            if card.value == "quick_kick":
                return bool(self._opponents(player)), "motostrike-reason-no-target"
            if card.value == "deadly_kick":
                if not self.options.deadly_kick:
                    return False, "motostrike-reason-disabled"
                if player.distance < DEADLY_KICK_MIN_DISTANCE:
                    return False, "motostrike-reason-need-1000"
                return bool(self._opponents(player)), "motostrike-reason-no-target"
            # Shields are held for protection, not played
            return False, "motostrike-reason-hold-only"

        if card_type == CardType.ATTACK:
            if card.value == "smoke_bomb":
                return self._rider_behind(player) is not None, "motostrike-reason-no-one-behind"
            if card.value == "electric_shock":
                nearest = self._nearest_rider(player)
                ok = nearest is not None and abs(nearest.distance - player.distance) <= SHOCK_RANGE
                return ok, "motostrike-reason-no-one-within"
            if card.value == "police_chase":
                ahead = self._rider_ahead(player)
                if ahead is None:
                    return False, "motostrike-reason-no-one-ahead"
                if ahead.police_chase_turns > 0 or ahead.immobilized:
                    return False, "motostrike-reason-chase-active"
                return True, None

        return False, "motostrike-reason-generic"

    def _movement_blocked_reason(self, player: MotoStrikePlayer) -> str:
        if player.stuck:
            return "motostrike-reason-stuck"
        if player.wheel_damaged:
            return "motostrike-reason-wheel"
        if player.immobilized:
            return "motostrike-reason-immobilized"
        return "motostrike-reason-eliminated"

    # ==========================================================================
    # Rider helpers
    # ==========================================================================

    def _active_riders(self) -> list[MotoStrikePlayer]:
        """All riders still in the race (spectators and eliminated excluded)."""
        return [
            p
            for p in self.players
            if not p.is_spectator and isinstance(p, MotoStrikePlayer) and not p.eliminated
        ]

    def _opponents(self, player: MotoStrikePlayer) -> list[MotoStrikePlayer]:
        """All active riders except the given player."""
        return [p for p in self._active_riders() if p.id != player.id]

    def _rider_behind(self, player: MotoStrikePlayer) -> MotoStrikePlayer | None:
        """The active rider directly behind the given player (closest behind)."""
        behind = [p for p in self._opponents(player) if p.distance < player.distance]
        if not behind:
            return None
        return max(behind, key=lambda p: p.distance)

    def _rider_ahead(self, player: MotoStrikePlayer) -> MotoStrikePlayer | None:
        """The active rider directly ahead of the given player (closest ahead)."""
        ahead = [p for p in self._opponents(player) if p.distance > player.distance]
        if not ahead:
            return None
        return min(ahead, key=lambda p: p.distance)

    def _nearest_rider(self, player: MotoStrikePlayer) -> MotoStrikePlayer | None:
        """The active rider nearest in position to the given player."""
        others = self._opponents(player)
        if not others:
            return None
        return min(others, key=lambda p: abs(p.distance - player.distance))

    def _leader(self) -> MotoStrikePlayer | None:
        """The active rider with the greatest distance."""
        riders = self._active_riders()
        if not riders:
            return None
        return max(riders, key=lambda p: p.distance)

    def _has_card(self, player: MotoStrikePlayer, value: str) -> bool:
        """Check if the rider holds a card with the given value."""
        return any(card.value == value for card in player.hand)

    def _find_card_slot(self, player: MotoStrikePlayer, value: str) -> int | None:
        """Find the slot index of the first card with the given value."""
        for i, card in enumerate(player.hand):
            if card.value == value:
                return i
        return None

    # ==========================================================================
    # Action handlers
    # ==========================================================================

    def _action_play_card(self, player: Player, *args) -> None:
        """Play (or auto-discard) a card from the rider's hand."""
        if not isinstance(player, MotoStrikePlayer):
            return
        if self.current_player != player:
            return
        if self.intro_wait_ticks > 0:
            return

        if len(args) == 1:
            action_id = args[0]
            input_value = None
        elif len(args) == 2:
            input_value, action_id = args
        else:
            return

        try:
            slot = int(action_id.split("_")[-1]) - 1
        except ValueError:
            return
        if slot < 0 or slot >= len(player.hand):
            return

        card = player.hand[slot]
        playable, reason = self._can_play(player, card)
        if not playable:
            # Bots auto-discard unusable cards; humans keep the card and are
            # told why (discarding is a deliberate gesture, per the docs).
            if player.is_bot:
                self._discard_card(player, slot)
            else:
                user = self.get_user(player)
                if user:
                    reason_text = Localization.get(user.locale, reason) if reason else ""
                    card_name = self._localized_card_name(card, user.locale)
                    user.speak_l(
                        "motostrike-cant-play",
                        card=card_name,
                        reason=reason_text,
                    )
            return

        self._play_card(player, slot, card, input_value)

    def _action_discard_card(self, player: Player, action_id: str) -> None:
        """Discard the currently selected card (shift+enter / backspace)."""
        if not isinstance(player, MotoStrikePlayer):
            return
        if self.current_player != player:
            return
        if self.intro_wait_ticks > 0:
            return

        context = self.get_action_context(player)
        menu_item_id = context.menu_item_id
        if not menu_item_id or not menu_item_id.startswith("card_slot_"):
            user = self.get_user(player)
            if user:
                user.speak_l("motostrike-no-card-selected")
            return

        try:
            slot = int(menu_item_id.split("_")[-1]) - 1
        except ValueError:
            return
        if slot < 0 or slot >= len(player.hand):
            return

        self._discard_card(player, slot)

    def _discard_card(self, player: MotoStrikePlayer, slot: int) -> None:
        """Discard a card without using its effect."""
        if slot < 0 or slot >= len(player.hand):
            return
        card = player.hand.pop(slot)
        self.discard_pile.append(card)
        self.play_sound(f"game_cards/discard{random.randint(1, 3)}.ogg")  # nosec B311
        self.broadcast_l(
            "motostrike-discards", player=player.name, card=self._card_en(card)
        )
        self._finish_play(player, played_maneuver=False)

    # ==========================================================================
    # Card effects
    # ==========================================================================

    def _play_card(
        self,
        player: MotoStrikePlayer,
        slot: int,
        card: Card,
        target_selection: str | None = None,
    ) -> None:
        """Resolve the effect of a played card."""
        card_type = card.card_type
        if card_type == CardType.MOVEMENT:
            self._play_movement(player, slot, card)
        elif card_type == CardType.MANEUVER:
            self._play_maneuver(player, slot, card)
        elif card_type == CardType.RECOVERY:
            self._play_recovery(player, slot, card)
        elif card_type == CardType.TRAP:
            self._play_trap(player, slot, card, target_selection)
        elif card_type == CardType.ATTACK:
            self._play_attack(player, slot, card)
        elif card_type == CardType.SPECIAL:
            self._play_special(player, slot, card, target_selection)

    def _play_movement(self, player: MotoStrikePlayer, slot: int, card: Card) -> None:
        """Play a Movement card to advance the bike."""
        meters = MOVEMENT_VALUES.get(card.value, 0)
        player.hand.pop(slot)
        self.discard_pile.append(card)
        player.distance += meters
        self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")  # nosec B311
        self.broadcast_l(
            "motostrike-rides", player=player.name, distance=meters, total=player.distance
        )
        self._finish_play(player, played_maneuver=False)

    def _play_maneuver(self, player: MotoStrikePlayer, slot: int, card: Card) -> None:
        """Play a Maneuver card: escape the police and/or move a little."""
        player.hand.pop(slot)
        self.discard_pile.append(card)

        escaped = False
        if player.police_chase_turns > 0:
            player.police_chase_turns = 0
            escaped = True
            self.play_sound("game_chess/moveknight.ogg")
            self.broadcast_l("motostrike-chase-escaped", target=player.name)

        meters = MANEUVER_VALUES.get(card.value, 0)
        moved = False
        if player.can_move() and meters > 0:
            player.distance += meters
            moved = True

        self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")  # nosec B311
        if moved:
            self.broadcast_l(
                "motostrike-maneuvers",
                player=player.name,
                distance=meters,
                total=player.distance,
            )
        else:
            self.broadcast_l("motostrike-maneuvers-no-move", player=player.name)

        self._finish_play(player, played_maneuver=True)

    def _play_recovery(self, player: MotoStrikePlayer, slot: int, card: Card) -> None:
        """Play a Recovery card to fix the bike."""
        player.hand.pop(slot)
        self.discard_pile.append(card)
        if card.value == "rebalance":
            player.stuck = False
        elif card.value == "repair":
            player.wheel_damaged = False
        elif card.value == "escape":
            player.immobilized = False
        self.play_sound(f"game_cards/play{random.randint(1, 4)}.ogg")  # nosec B311
        self.broadcast_l(
            "motostrike-recovers", player=player.name, card=self._card_en(card)
        )
        self._finish_play(player, played_maneuver=False)

    def _play_trap(
        self,
        player: MotoStrikePlayer,
        slot: int,
        card: Card,
        target_selection: str | None,
    ) -> None:
        """Play a trap on an opponent."""
        target = self._resolve_target(player, target_selection)
        if target is None:
            self._notify_no_target(player)
            return

        player.hand.pop(slot)
        self.discard_pile.append(card)

        if self._has_card(target, "emergency_swerve"):
            self._consume_shield(target, "emergency_swerve")
            self.play_sound("game_chess/moveknight.ogg")
            self.broadcast_l(
                "motostrike-trap-blocked",
                player=player.name,
                target=target.name,
                trap=self._card_en(card),
            )
            self._finish_play(player, played_maneuver=False)
            return

        self.play_sound("game_battleship/hit.ogg")
        if card.value == "mud_trap":
            target.stuck = True
            self.broadcast_l("motostrike-mud-hit", player=player.name, target=target.name)
        else:
            target.wheel_damaged = True
            target.stuck = True
            self.broadcast_l(
                "motostrike-wreck-hit",
                player=player.name,
                target=target.name,
                trap=self._card_en(card),
            )
        self._finish_play(player, played_maneuver=False)

    def _play_attack(self, player: MotoStrikePlayer, slot: int, card: Card) -> None:
        """Play an attack card (Smoke Bomb / Electric Shock / Police Chase)."""
        if card.value == "smoke_bomb":
            target = self._rider_behind(player)
            if target is None:
                self._notify_no_target(player)
                return
            player.hand.pop(slot)
            self.discard_pile.append(card)
            target.distance = max(0, target.distance - SMOKE_KNOCKBACK)
            self.play_sound("game_battleship/fire.ogg")
            self.broadcast_l(
                "motostrike-smoke-hit",
                player=player.name,
                target=target.name,
                distance=SMOKE_KNOCKBACK,
                total=target.distance,
            )

        elif card.value == "electric_shock":
            target = self._nearest_rider(player)
            if target is None or abs(target.distance - player.distance) > SHOCK_RANGE:
                self._notify_no_target(player)
                return
            player.hand.pop(slot)
            self.discard_pile.append(card)
            self.play_sound("game_battleship/hit.ogg")
            if target.hand:
                dropped = random.choice(target.hand)  # nosec B311
                target.hand.remove(dropped)
                self.discard_pile.append(dropped)
                self.broadcast_l(
                    "motostrike-shock-hit",
                    player=player.name,
                    target=target.name,
                    card=self._card_en(dropped),
                )
            else:
                self.broadcast_l("motostrike-shock-empty", player=player.name, target=target.name)

        elif card.value == "police_chase":
            target = self._rider_ahead(player)
            if target is None:
                self._notify_no_target(player)
                return
            if target.police_chase_turns > 0 or target.immobilized:
                self._notify_no_target(player)
                return
            player.hand.pop(slot)
            self.discard_pile.append(card)
            target.police_chase_turns = CHASE_WINDOW
            self.play_sound("game_chess/moveking.ogg")
            self.broadcast_l(
                "motostrike-chase-started",
                player=player.name,
                target=target.name,
                turns=CHASE_WINDOW,
            )

        self._finish_play(player, played_maneuver=False)

    def _play_special(
        self,
        player: MotoStrikePlayer,
        slot: int,
        card: Card,
        target_selection: str | None,
    ) -> None:
        """Play a special card (Quick Kick / Deadly Kick)."""
        target = self._resolve_target(player, target_selection)
        if target is None:
            self._notify_no_target(player)
            return

        player.hand.pop(slot)
        self.discard_pile.append(card)

        if self._has_card(target, "kick_shield"):
            self._consume_shield(target, "kick_shield")
            self.play_sound("game_chess/moveknight.ogg")
            self.broadcast_l(
                "motostrike-kick-blocked", player=player.name, target=target.name
            )
            self._finish_play(player, played_maneuver=False)
            return

        self.play_sound("game_battleship/fire.ogg")
        if card.value == "quick_kick":
            target.distance = max(0, target.distance - QUICK_KICK_KNOCKBACK)
            self.broadcast_l(
                "motostrike-quick-kick",
                player=player.name,
                target=target.name,
                distance=QUICK_KICK_KNOCKBACK,
                total=target.distance,
            )
        else:  # deadly_kick
            target.eliminated = True
            target.police_chase_turns = 0
            self.play_sound("game_pig/lose.ogg")
            self.broadcast_l(
                "motostrike-deadly-kick", player=player.name, target=target.name
            )
            remaining = self._active_riders()
            if len(remaining) == 1 and remaining[0].id == player.id:
                # Last rider standing
                self._end_race(player, by_elimination=True)
                return

        self._finish_play(player, played_maneuver=False)

    def _consume_shield(self, player: MotoStrikePlayer, value: str) -> None:
        """Remove a held shield/swerve card from the rider's hand."""
        for i, card in enumerate(player.hand):
            if card.value == value:
                card = player.hand.pop(i)
                self.discard_pile.append(card)
                return

    # ==========================================================================
    # Targeting
    # ==========================================================================

    def _pending_card(self, player: Player) -> Card | None:
        """Get the card whose action is awaiting target input."""
        action_id = self._pending_actions.get(player.id)
        if not action_id or not action_id.startswith("card_slot_"):
            return None
        try:
            slot = int(action_id.split("_")[-1]) - 1
        except ValueError:
            return None
        if not isinstance(player, MotoStrikePlayer):
            return None
        if slot < 0 or slot >= len(player.hand):
            return None
        return player.hand[slot]

    def _target_options(self, player: Player) -> list[str]:
        """Options for the target-selection menu."""
        if not isinstance(player, MotoStrikePlayer):
            return []
        card = self._pending_card(player)
        if card is None:
            return []
        return [f"{opp.name} ({opp.distance} meters)" for opp in self._opponents(player)]

    def _bot_select_target(self, player: Player, options: list[str]) -> str | None:
        """Bot target selection: pick the leading rider."""
        best_option = None
        best_distance = -1
        for option in options:
            name = option.split(" (")[0]
            opp = self.get_player_by_name(name)
            if isinstance(opp, MotoStrikePlayer) and opp.distance > best_distance:
                best_option = option
                best_distance = opp.distance
        return best_option

    def _resolve_target(
        self, player: MotoStrikePlayer, selection: str | None
    ) -> MotoStrikePlayer | None:
        """Resolve a menu selection (or single opponent) into a target."""
        opponents = self._opponents(player)
        if selection:
            name = selection.split(" (")[0]
            for opp in opponents:
                if opp.name == name:
                    return opp
            return None
        if len(opponents) == 1:
            return opponents[0]
        return None

    def _notify_no_target(self, player: MotoStrikePlayer) -> None:
        """Tell the rider their play had no valid target (card stays in hand)."""
        user = self.get_user(player)
        if user:
            user.speak_l("motostrike-no-valid-target")

    # ==========================================================================
    # Deck management
    # ==========================================================================

    def _draw_card(self) -> Card | None:
        """Draw a card, reshuffling the discard pile when the deck runs out."""
        if self.deck.is_empty():
            if self.discard_pile:
                self.deck.add_all(self.discard_pile)
                self.discard_pile = []
                self.deck.shuffle()
                self.play_sound(f"game_cards/shuffle{random.randint(1, 3)}.ogg")  # nosec B311
                self.broadcast_l("motostrike-deck-reshuffled")
            else:
                return None
        return self.deck.draw()

    def _refill_hand(self, player: MotoStrikePlayer) -> None:
        """Draw cards until the rider's hand is back to HAND_SIZE."""
        drew = 0
        while len(player.hand) < HAND_SIZE:
            card = self._draw_card()
            if card is None:
                break
            player.hand.append(card)
            drew += 1
        if drew > 0:
            self.play_sound(f"game_cards/draw{random.randint(1, 4)}.ogg")  # nosec B311

    # ==========================================================================
    # Status actions
    # ==========================================================================

    def _status_parts(self, player: MotoStrikePlayer, locale: str) -> list[str]:
        """Localized list of a rider's bike statuses."""
        parts = []
        if player.stuck:
            parts.append(Localization.get(locale, "motostrike-status-stuck"))
        if player.wheel_damaged:
            parts.append(Localization.get(locale, "motostrike-status-wheel"))
        if player.immobilized:
            parts.append(Localization.get(locale, "motostrike-status-immobilized"))
        if player.police_chase_turns > 0:
            parts.append(
                Localization.get(locale, "motostrike-status-chased", turns=player.police_chase_turns)
            )
        if player.eliminated:
            parts.append(Localization.get(locale, "motostrike-status-eliminated"))
        return parts

    def _status_text(self, player: MotoStrikePlayer, locale: str) -> str:
        """Comma-joined statuses or an empty string when the bike is fine."""
        parts = self._status_parts(player, locale)
        if not parts:
            return Localization.get(locale, "motostrike-status-clear")
        return ", ".join(parts)

    def _action_bike_status(self, player: Player, action_id: str) -> None:
        """Speak the rider's own position, bike status, and needed cards."""
        user = self.get_user(player)
        if not user or not isinstance(player, MotoStrikePlayer):
            return
        locale = user.locale
        status = self._status_text(player, locale)

        hints = []
        if player.wheel_damaged:
            hints.append(Localization.get(locale, "motostrike-bike-hint-wheel"))
        if player.stuck:
            hints.append(Localization.get(locale, "motostrike-bike-hint-stuck"))
        if player.immobilized:
            hints.append(Localization.get(locale, "motostrike-bike-hint-immobilized"))
        if player.police_chase_turns > 0:
            hints.append(
                Localization.get(locale, "motostrike-bike-hint-chase", turns=player.police_chase_turns)
            )
        hint = " " + " ".join(hints) if hints else ""

        user.speak_l(
            "motostrike-bike-status",
            distance=player.distance,
            status=status,
            hint=hint,
        )

    def _action_race_status(self, player: Player, action_id: str) -> None:
        """Speak every rider's position and status."""
        user = self.get_user(player)
        if not user:
            return
        locale = user.locale
        parts = []
        for p in self.players:
            if p.is_spectator or not isinstance(p, MotoStrikePlayer):
                continue
            parts.append(
                Localization.get(
                    locale,
                    "motostrike-race-status-line",
                    name=p.name,
                    distance=p.distance,
                    status=self._status_text(p, locale),
                )
            )
        user.speak(", ".join(parts))

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def bot_think(self, player: MotoStrikePlayer) -> str | None:
        """Choose the bot's next action (returns an action id or None)."""
        if not isinstance(player, MotoStrikePlayer):
            return None

        # 1. Fix the bike first
        if player.stuck:
            slot = self._find_card_slot(player, "rebalance")
            if slot is not None:
                return self._slot_action(slot)
        if player.wheel_damaged:
            slot = self._find_card_slot(player, "repair")
            if slot is not None:
                return self._slot_action(slot)
        if player.immobilized:
            slot = self._find_card_slot(player, "escape")
            if slot is not None:
                return self._slot_action(slot)

        # 2. Escape an active police chase
        if player.police_chase_turns > 0:
            slot = self._find_maneuver_slot(player)
            if slot is not None:
                return self._slot_action(slot)

        # 3. Deadly Kick when ready
        if player.distance >= DEADLY_KICK_MIN_DISTANCE:
            slot = self._find_card_slot(player, "deadly_kick")
            if slot is not None:
                kickable = [o for o in self._opponents(player) if not self._has_card(o, "kick_shield")]
                if kickable:
                    return self._slot_action(slot)

        leader = self._leader()

        # 4. Sabotage the leader: when this rider is stuck (they can't race
        # anyway) or when the leader is about to cross the finish line.
        if leader and leader.id != player.id and self._should_attack_leader(player, leader):
            slot = self._find_card_slot(player, "quick_kick")
            if slot is not None:
                kickable = [o for o in self._opponents(player) if not self._has_card(o, "kick_shield")]
                if kickable:
                    return self._slot_action(slot)
            slot = self._find_trap_slot(player)
            if slot is not None:
                trappable = [o for o in self._opponents(player) if not self._has_card(o, "emergency_swerve")]
                if trappable:
                    return self._slot_action(slot)

        # 5. Race when able (movement cards, or a maneuver as a small move)
        if player.can_move():
            slot = self._best_movement_slot(player)
            if slot is not None:
                return self._slot_action(slot)

        # 6. Cheap attacks when the bike is broken
        if not player.can_move():
            slot = self._find_card_slot(player, "smoke_bomb")
            if slot is not None and self._rider_behind(player) is not None:
                return self._slot_action(slot)
            slot = self._find_card_slot(player, "electric_shock")
            if slot is not None:
                nearest = self._nearest_rider(player)
                if nearest is not None and abs(nearest.distance - player.distance) <= SHOCK_RANGE:
                    return self._slot_action(slot)

        # 7. Discard the least useful card
        return self._discard_slot_action(player)

    def _should_attack_leader(self, player: MotoStrikePlayer, leader: MotoStrikePlayer) -> bool:
        """Whether the bot attacks the leader instead of racing.

        Healthy bots race by default; they only sabotage a leader who is about
        to cross the finish line. Bots whose bikes are broken (and therefore
        can't race) use their attacks on the leader while waiting to recover.
        This keeps races progressing instead of degenerating into both riders
        trading traps forever.
        """
        if leader.distance <= player.distance:
            return False
        if not player.can_move():
            return True
        return leader.distance >= self.options.track_length - BOT_ATTACK_FINISH_MARGIN

    def _slot_action(self, slot: int) -> str:
        return f"card_slot_{slot + 1}"

    def _find_maneuver_slot(self, player: MotoStrikePlayer) -> int | None:
        for i, card in enumerate(player.hand):
            if card.card_type == CardType.MANEUVER:
                return i
        return None

    def _find_trap_slot(self, player: MotoStrikePlayer) -> int | None:
        for i, card in enumerate(player.hand):
            if card.card_type == CardType.TRAP:
                return i
        return None

    def _best_movement_slot(self, player: MotoStrikePlayer) -> int | None:
        """Pick the movement/maneuver card that best advances the rider."""
        best_slot = None
        best_value = -1
        for i, card in enumerate(player.hand):
            if card.card_type == CardType.MOVEMENT:
                value = MOVEMENT_VALUES.get(card.value, 0)
                if value > best_value:
                    best_value = value
                    best_slot = i
        if best_slot is not None:
            return best_slot
        # No movement card: a maneuver moves a little when not chased
        if player.police_chase_turns == 0:
            for i, card in enumerate(player.hand):
                if card.card_type == CardType.MANEUVER:
                    return i
        return None

    def _discard_slot_action(self, player: MotoStrikePlayer) -> str:
        """Pick the least useful card to discard (unplayable cards first)."""
        for i, card in enumerate(player.hand):
            playable, _ = self._can_play(player, card)
            if not playable:
                return self._slot_action(i)
        # Everything is playable: discard the weakest card
        worst_slot = 0
        worst_value = 10**9
        for i, card in enumerate(player.hand):
            value = MOVEMENT_VALUES.get(card.value, MANEUVER_VALUES.get(card.value, 1000))
            if value < worst_value:
                worst_value = value
                worst_slot = i
        return self._slot_action(worst_slot)

    # ==========================================================================
    # Scores / result
    # ==========================================================================

    def _sync_team_scores(self) -> None:
        """Keep team scores in sync with rider distances (powers check-scores)."""
        for team in self._team_manager.teams:
            team.total_score = 0
        for p in self.players:
            if p.is_spectator or not isinstance(p, MotoStrikePlayer):
                continue
            team = self._team_manager.get_team(p.name)
            if team:
                team.total_score = p.distance

    def build_game_result(self) -> GameResult:
        active = [p for p in self.players if not p.is_spectator]
        winner = None
        if self.race_winner_id:
            winner = self.get_player_by_id(self.race_winner_id)
        if winner is None and active:
            winner = max(active, key=lambda p: p.distance)
        final_distances = {p.name: p.distance for p in active}
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
                for p in active
            ],
            custom_data={
                "winner_name": winner.name if winner else None,
                "winner_distance": winner.distance if winner else 0,
                "final_distances": final_distances,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        lines = [Localization.get(locale, "motostrike-final-standings")]
        final_distances = result.custom_data.get("final_distances", {})
        winner_name = result.custom_data.get("winner_name")
        sorted_distances = sorted(final_distances.items(), key=lambda item: item[1], reverse=True)
        for i, (name, distance) in enumerate(sorted_distances, 1):
            marker = " *" if name == winner_name else ""
            lines.append(f"{i}. {name}: {distance} meters{marker}")
        return lines