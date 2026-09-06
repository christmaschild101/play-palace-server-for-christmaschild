"""Game Manager and Community menus for the PlayPalace server.

Two mixins composed onto :class:`server.core.server.Server`:

* :class:`GameManagerMixin` — developer-and-above management of per-game
  server defaults (starting with Monopoly board/rent/house-rule defaults
  applied to new tables) and review of player-submitted bot requests.
* :class:`CommunityMixin` — the all-players community menu: feature voting,
  a QCPlayroom-style forum, and bot requests.

Both follow the interaction conventions of ``core/administration.py``:
``show_menu`` + ``_user_states[username]["menu"]`` dispatch, editboxes for
text entry, and ``show_yes_no_menu`` for confirmations.
"""

from typing import TYPE_CHECKING, Any

from ..messages.localization import Localization
from .users.base import EscapeBehavior, MenuItem, TrustLevel
from .users.network_user import NetworkUser
from .ui.common_flows import show_yes_no_menu

if TYPE_CHECKING:
    from ..persistence.database import Database


def _speak(user: NetworkUser, key: str, buffer: str = "misc", **kwargs: Any) -> None:
    """Speak a localized message to one user (never raises on missing keys)."""
    user.speak_l(key, buffer=buffer, **kwargs)


# ============================================================================
# Game Manager (developers and above)
# ============================================================================


class GameManagerMixin:
    """Developer menu for per-game server defaults and bot-request review."""

    # -- Menu ----------------------------------------------------------------

    def _show_game_manager_menu(self, user: NetworkUser) -> None:
        """Show the Game Manager menu (developers and above)."""
        items = [
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-monopoly-defaults"),
                id="monopoly_defaults",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-bot-requests"),
                id="bot_requests",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "game_manager_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "game_manager_menu"}

    async def _handle_game_manager_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle Game Manager menu selection."""
        if selection_id == "monopoly_defaults":
            self._show_game_defaults_menu(user, "monopoly")
        elif selection_id == "bot_requests":
            self._show_bot_requests_menu(user)
        elif selection_id == "back":
            self._show_admin_menu(user)

    # -- Game defaults ---------------------------------------------------------

    def _load_defaults_dict(self, game_type: str) -> dict:
        """Load stored defaults for a game type as a dict (empty if none)."""
        db: Database | None = getattr(self, "_db", None)
        if not db:
            return {}
        import json

        raw = db.load_game_defaults(game_type)
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_defaults_dict(self, game_type: str, data: dict) -> None:
        """Persist defaults for a game type."""
        import json

        db: Database | None = getattr(self, "_db", None)
        if not db:
            return
        db.save_game_defaults(game_type, json.dumps(data, sort_keys=True))

    def _defaults_status_text(self, game_type: str, locale: str) -> str:
        """Human-readable one-line summary of stored defaults (or 'unset')."""
        data = self._load_defaults_dict(game_type)
        if not data:
            return Localization.get(locale, "gamemanager-defaults-none")
        parts = [f"{key}={value}" for key, value in sorted(data.items())]
        return ", ".join(parts)

    def _show_game_defaults_menu(self, user: NetworkUser, game_type: str) -> None:
        """Show the defaults editor for one game (Monopoly for now)."""
        if game_type != "monopoly":  # Future: more managed games
            self._show_game_manager_menu(user)
            return

        status = self._defaults_status_text(game_type, user.locale)
        items = [
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-defaults-status")
                + f" {status}",
                id="status",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-set-board"),
                id="set_board",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-set-rent"),
                id="set_rent",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-toggle-jackpot"),
                id="toggle_jackpot",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-toggle-tax"),
                id="toggle_tax",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-toggle-auction"),
                id="toggle_auction",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-defaults-clear"),
                id="clear",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "game_defaults_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "game_defaults_menu",
            "game_type": game_type,
        }

    async def _handle_game_defaults_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle the per-game defaults editor selection."""
        game_type = state.get("game_type", "monopoly")
        data = self._load_defaults_dict(game_type)

        if selection_id == "set_board":
            self._show_defaults_choice_menu(
                user, game_type, "board", ["us", "uk"], data
            )
            return
        if selection_id == "set_rent":
            self._show_defaults_choice_menu(
                user, game_type, "rent", ["classic", "simplified"], data
            )
            return
        if selection_id in ("toggle_jackpot", "toggle_tax", "toggle_auction"):
            field = {
                "toggle_jackpot": "free_parking_jackpot",
                "toggle_tax": "income_tax_10pct",
                "toggle_auction": "auction_start_10pct",
            }[selection_id]
            current = bool(data.get(field, False))
            data[field] = not current
            self._save_defaults_dict(game_type, data)
            _speak(
                user,
                "gamemanager-defaults-saved",
                field=field,
                value=str(not current).lower(),
            )
            self._show_game_defaults_menu(user, game_type)
            return
        if selection_id == "clear":
            db: Database | None = getattr(self, "_db", None)
            if db:
                db.clear_game_defaults(game_type)
            _speak(user, "gamemanager-defaults-cleared")
            self._show_game_defaults_menu(user, game_type)
            return
        if selection_id == "back":
            self._show_game_manager_menu(user)

    def _show_defaults_choice_menu(
        self,
        user: NetworkUser,
        game_type: str,
        field: str,
        choices: list[str],
        data: dict,
    ) -> None:
        """Show a choice menu for one defaults field."""
        items = []
        for choice in choices:
            marker = "*" if data.get(field) == choice else ""
            items.append(
                MenuItem(
                    text=f"{marker}{choice}",
                    id=f"choice_{choice}",
                )
            )
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "game_defaults_choice_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "game_defaults_choice_menu",
            "game_type": game_type,
            "field": field,
            "draft": data,
        }

    async def _handle_game_defaults_choice_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle choosing a value for one defaults field."""
        game_type = state.get("game_type", "monopoly")
        field = state.get("field", "")
        if selection_id == "back":
            self._show_game_defaults_menu(user, game_type)
            return
        if selection_id.startswith("choice_"):
            value = selection_id[len("choice_"):]
            data = self._load_defaults_dict(game_type)
            data[field] = value
            self._save_defaults_dict(game_type, data)
            _speak(user, "gamemanager-defaults-saved", field=field, value=value)
            self._show_game_defaults_menu(user, game_type)

    def _apply_game_defaults(self, game_type: str, game: Any) -> None:
        """Overlay stored server defaults onto a newly created game's options.

        Only keys that match declarative option fields are applied; hosts can
        still override everything per table via the normal options menu.
        Saved/restored tables are untouched (their options are serialized).
        """
        data = self._load_defaults_dict(game_type)
        options = getattr(game, "options", None)
        if not data or options is None:
            return
        try:
            valid = set(options.get_option_metas().keys())
        except Exception:
            return
        for key, value in data.items():
            if key in valid and isinstance(value, (bool, int, float, str)):
                try:
                    setattr(options, key, value)
                except Exception:
                    continue

    # -- Bot request review -----------------------------------------------------

    def _show_bot_requests_menu(self, user: NetworkUser) -> None:
        """List pending bot requests with review actions."""
        db: Database | None = getattr(self, "_db", None)
        requests = db.load_bot_requests("pending") if db else []

        items = []
        for req in requests:
            label = Localization.get(
                user.locale,
                "gamemanager-bot-request-item",
                name=req["name"],
                requester=req["requester"],
            )
            items.append(MenuItem(text=label, id=f"req_{req['id']}"))
        if not items:
            _speak(user, "gamemanager-bot-requests-none")
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "bot_requests_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "bot_requests_menu"}

    async def _handle_bot_requests_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle selecting a pending bot request (or back)."""
        if selection_id == "back":
            self._show_game_manager_menu(user)
            return
        if selection_id.startswith("req_"):
            request_id = int(selection_id[len("req_"):])
            self._show_bot_request_actions_menu(user, request_id)

    def _show_bot_request_actions_menu(self, user: NetworkUser, request_id: int) -> None:
        """Show accept/reject/delete actions for one bot request."""
        db: Database | None = getattr(self, "_db", None)
        req = db.get_bot_request(request_id) if db else None
        if not req:
            _speak(user, "gamemanager-bot-request-gone")
            self._show_bot_requests_menu(user)
            return

        desc = req["description"]
        _speak(
            user,
            "gamemanager-bot-request-detail",
            name=req["name"],
            requester=req["requester"],
            description=desc or "-",
        )
        items = [
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-bot-request-accept"),
                id="accept",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-bot-request-reject"),
                id="reject",
            ),
            MenuItem(
                text=Localization.get(user.locale, "gamemanager-bot-request-delete"),
                id="delete",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "bot_request_actions_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "bot_request_actions_menu",
            "request_id": request_id,
        }

    async def _handle_bot_request_actions_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle accept/reject/delete for one bot request."""
        request_id = state.get("request_id")
        db: Database | None = getattr(self, "_db", None)
        if selection_id == "back" or request_id is None:
            self._show_bot_requests_menu(user)
            return

        req = db.get_bot_request(request_id) if db else None
        if not req:
            _speak(user, "gamemanager-bot-request-gone")
            self._show_bot_requests_menu(user)
            return

        if selection_id == "accept":
            await self._accept_bot_request(user, req)
        elif selection_id == "reject":
            if db and db.set_bot_request_status(request_id, "rejected"):
                _speak(user, "gamemanager-bot-request-rejected", name=req["name"])
                self._notify_requester_if_online(req["requester"], "bot-request-rejected", name=req["name"])
        elif selection_id == "delete":
            if db and db.delete_bot_request(request_id):
                _speak(user, "gamemanager-bot-request-deleted", name=req["name"])
        self._show_bot_requests_menu(user)

    async def _accept_bot_request(self, user: NetworkUser, req: dict) -> None:
        """Create the real virtual bot for an accepted request."""
        manager = getattr(self, "_virtual_bots", None)
        name = req["name"].strip()
        if not manager:
            _speak(user, "virtual-bots-not-available")
            return

        error_key = self._validate_bot_name(name)
        if error_key:
            _speak(user, error_key)
            return  # Request stays pending; dev can rename flow later

        if manager.add_bot(name):
            # Persist the state row immediately (same as the admin add-bot
            # flow) so the accepted bot survives restarts and is restored
            # into the login rotation by load_state().
            manager.save_state()
            db: Database | None = getattr(self, "_db", None)
            if db:
                db.set_bot_request_status(req["id"], "accepted")
            _speak(user, "gamemanager-bot-request-accepted", name=name)
            self._notify_requester_if_online(req["requester"], "bot-request-accepted", name=name)
        else:
            _speak(user, "virtual-bots-name-taken")

    def _notify_requester_if_online(self, username: str, key: str, **kwargs: Any) -> None:
        """Send a community notification to the requester if they are online."""
        target = self._users.get(username)
        if target is not None and target.approved:
            _speak(target, key, buffer="activity", **kwargs)


# ============================================================================
# Community (all approved players)
# ============================================================================


class CommunityMixin:
    """All-players community menu: feature votes, forum, bot requests."""

    # -- Menu ----------------------------------------------------------------

    def _show_community_menu(self, user: NetworkUser) -> None:
        """Show the community menu."""
        items = [
            MenuItem(
                text=Localization.get(user.locale, "community-feature-votes"),
                id="feature_votes",
            ),
            MenuItem(
                text=Localization.get(user.locale, "community-forum"),
                id="forum",
            ),
            MenuItem(
                text=Localization.get(user.locale, "community-request-bot"),
                id="request_bot",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "community_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "community_menu"}

    async def _handle_community_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle community menu selection."""
        if selection_id == "feature_votes":
            self._show_feature_votes_menu(user)
        elif selection_id == "forum":
            self._show_forum_threads_menu(user)
        elif selection_id == "request_bot":
            self._show_request_bot_name_editbox(user)
        elif selection_id == "back":
            self._show_main_menu(user)

    # -- Feature votes -----------------------------------------------------------

    def _show_feature_votes_menu(self, user: NetworkUser) -> None:
        """Show the feature request list, most-voted first."""
        db: Database | None = getattr(self, "_db", None)
        requests = db.load_feature_requests() if db else []

        items = []
        for req in requests:
            voted = db.get_feature_vote(req["id"], user.username) if db else False
            marker = "*" if voted else ""
            label = Localization.get(
                user.locale,
                "community-feature-item",
                votes=req["votes"],
                text=req["text"],
                author=req["author"],
            )
            items.append(MenuItem(text=f"{marker}{label}", id=f"vote_{req['id']}"))
        items.append(
            MenuItem(
                text=Localization.get(user.locale, "community-feature-propose"),
                id="propose",
            )
        )
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "feature_votes_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "feature_votes_menu"}

    async def _handle_feature_votes_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle voting on or proposing a feature request."""
        db: Database | None = getattr(self, "_db", None)
        if selection_id == "back":
            self._show_community_menu(user)
            return
        if selection_id == "propose":
            self._show_feature_propose_editbox(user)
            return
        if selection_id.startswith("vote_") and db:
            request_id = int(selection_id[len("vote_"):])
            if db.add_feature_vote(request_id, user.username):
                _speak(user, "community-feature-voted")
            else:
                _speak(user, "community-feature-already-voted")
            self._show_feature_votes_menu(user)

    def _show_feature_propose_editbox(self, user: NetworkUser) -> None:
        """Editbox for proposing a feature request."""
        prompt = Localization.get(user.locale, "community-feature-propose-prompt")
        user.show_editbox(
            "feature_propose_editbox",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "feature_propose_editbox"}

    async def _handle_feature_propose_editbox(
        self, user: NetworkUser, text: str
    ) -> None:
        """Store a new feature proposal."""
        text = (text or "").strip()
        db: Database | None = getattr(self, "_db", None)
        if not text:
            _speak(user, "community-feature-empty")
        elif db:
            db.save_feature_request(text[:500], user.username)
            _speak(user, "community-feature-added")
        self._show_feature_votes_menu(user)

    # -- Forum -------------------------------------------------------------------

    def _show_forum_threads_menu(self, user: NetworkUser) -> None:
        """Show forum thread list, most recently active first."""
        db: Database | None = getattr(self, "_db", None)
        threads = db.load_forum_threads() if db else []

        items = []
        for thread in threads:
            label = Localization.get(
                user.locale,
                "community-forum-thread-item",
                title=thread["title"],
                author=thread["author"],
                posts=thread["posts"],
            )
            items.append(MenuItem(text=label, id=f"thread_{thread['id']}"))
        items.append(
            MenuItem(
                text=Localization.get(user.locale, "community-forum-new-thread"),
                id="new",
            )
        )
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "forum_threads_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "forum_threads_menu"}

    async def _handle_forum_threads_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle forum thread list selection."""
        if selection_id == "back":
            self._show_community_menu(user)
            return
        if selection_id == "new":
            self._show_forum_new_thread_title_editbox(user)
            return
        if selection_id.startswith("thread_"):
            thread_id = int(selection_id[len("thread_"):])
            self._show_forum_thread_menu(user, thread_id)

    def _show_forum_thread_menu(self, user: NetworkUser, thread_id: int) -> None:
        """Show a thread's posts in order with a reply action."""
        db: Database | None = getattr(self, "_db", None)
        posts = db.load_forum_posts(thread_id) if db else None
        if posts is None:
            _speak(user, "community-forum-thread-gone")
            self._show_forum_threads_menu(user)
            return

        import time as _time

        for i, post in enumerate(posts, 1):
            _speak(
                user,
                "community-forum-post",
                index=i,
                author=post["author"],
                body=post["body"],
            )
            _time.sleep(0.05)  # Pace the spoken posts slightly

        items = [
            MenuItem(
                text=Localization.get(user.locale, "community-forum-reply"),
                id="reply",
            ),
        ]
        if user.trust_level.value >= TrustLevel.ADMIN.value:
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "community-forum-delete-thread"),
                    id="delete_thread",
                )
            )
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "forum_thread_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "forum_thread_menu",
            "thread_id": thread_id,
        }

    async def _handle_forum_thread_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle actions inside one forum thread."""
        thread_id = state.get("thread_id")
        db: Database | None = getattr(self, "_db", None)
        if selection_id == "back" or thread_id is None:
            self._show_forum_threads_menu(user)
            return
        if selection_id == "reply":
            self._show_forum_reply_editbox(user, thread_id)
        elif selection_id == "delete_thread" and db:
            if db.delete_forum_thread(thread_id):
                _speak(user, "community-forum-thread-deleted")
            self._show_forum_threads_menu(user)

    def _show_forum_new_thread_title_editbox(self, user: NetworkUser) -> None:
        """Editbox for a new thread's title."""
        prompt = Localization.get(user.locale, "community-forum-title-prompt")
        user.show_editbox(
            "forum_title_editbox",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "forum_title_editbox"}

    async def _handle_forum_title_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Take the title, then ask for the first post body."""
        title = (text or "").strip()
        if not title:
            _speak(user, "community-forum-empty-title")
            self._show_forum_threads_menu(user)
            return
        prompt = Localization.get(user.locale, "community-forum-body-prompt")
        user.show_editbox(
            "forum_body_editbox",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {
            "menu": "forum_body_editbox",
            "thread_title": title[:200],
        }

    async def _handle_forum_body_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Create the thread with the collected title and body."""
        body = (text or "").strip()
        title = state.get("thread_title", "")
        db: Database | None = getattr(self, "_db", None)
        if not body or not title or not db:
            _speak(user, "community-forum-empty-body")
            self._show_forum_threads_menu(user)
            return
        db.create_forum_thread(title, user.username, body[:2000])
        _speak(user, "community-forum-thread-created", title=title)
        self._show_forum_threads_menu(user)

    def _show_forum_reply_editbox(self, user: NetworkUser, thread_id: int) -> None:
        """Editbox for replying inside a thread."""
        prompt = Localization.get(user.locale, "community-forum-reply-prompt")
        user.show_editbox(
            "forum_reply_editbox",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {
            "menu": "forum_reply_editbox",
            "thread_id": thread_id,
        }

    async def _handle_forum_reply_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Append a reply to the thread."""
        body = (text or "").strip()
        thread_id = state.get("thread_id")
        db: Database | None = getattr(self, "_db", None)
        if body and thread_id is not None and db:
            if db.add_forum_post(thread_id, user.username, body[:2000]):
                _speak(user, "community-forum-reply-posted")
        else:
            _speak(user, "community-forum-empty-body")
        self._show_forum_thread_menu(user, thread_id)

    # -- Bot requests ------------------------------------------------------------

    def _show_request_bot_name_editbox(self, user: NetworkUser) -> None:
        """Editbox for the requested bot's name."""
        prompt = Localization.get(user.locale, "community-request-bot-name-prompt")
        user.show_editbox(
            "bot_request_name_editbox",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "bot_request_name_editbox"}

    async def _handle_bot_request_name_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Take the bot name, then ask for a description."""
        name = (text or "").strip()
        if not name or len(name) > 40:
            _speak(user, "community-request-bot-invalid-name")
            self._show_community_menu(user)
            return
        prompt = Localization.get(user.locale, "community-request-bot-desc-prompt")
        user.show_editbox(
            "bot_request_desc_editbox",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {
            "menu": "bot_request_desc_editbox",
            "bot_request_name": name,
        }

    async def _handle_bot_request_desc_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Store the bot request for developer review."""
        description = (text or "").strip()
        name = state.get("bot_request_name", "")
        db: Database | None = getattr(self, "_db", None)
        if not name or not db:
            _speak(user, "community-request-bot-invalid-name")
            self._show_community_menu(user)
            return
        db.save_bot_request(name, description[:500], user.username)
        _speak(user, "community-request-bot-submitted", name=name)
        self._show_community_menu(user)
