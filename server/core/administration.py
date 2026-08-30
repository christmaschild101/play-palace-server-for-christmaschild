"""Administration functionality for the PlayPalace server."""

import asyncio
import functools
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .users.network_user import NetworkUser
from .users.base import MenuItem, EscapeBehavior, TrustLevel
from ..messages.localization import Localization
from .ui.common_flows import show_yes_no_menu

if TYPE_CHECKING:
    from ..persistence.database import Database

LOG = logging.getLogger("playpalace.admin")

# Deploy helper invoked on in-game reboot (<repo>/scripts/restart-server.sh)
_RESTART_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "restart-server.sh"


# Activity buffer helper for admin/system announcements
def _speak_activity(user, message_id: str, **kwargs) -> None:
    """Speak a localized activity message to the admin/user."""
    user.speak_l(message_id, buffer="activity", **kwargs)


def require_admin(func):
    """Decorator that checks if the user is still an admin before executing an admin action."""

    @functools.wraps(func)
    async def wrapper(self, admin, *args, **kwargs):
        """Run the wrapped action if the user still has admin privileges."""
        if admin.trust_level.value < TrustLevel.ADMIN.value:
            _speak_activity(admin, "not-admin-anymore")
            self._show_main_menu(admin)
            return
        return await func(self, admin, *args, **kwargs)

    return wrapper


def require_server_owner(func):
    """Decorator that checks if the user is the server owner before executing a server owner action."""

    @functools.wraps(func)
    async def wrapper(self, owner, *args, **kwargs):
        """Run the wrapped action if the user is still the server owner."""
        if owner.trust_level.value < TrustLevel.SERVER_OWNER.value:
            _speak_activity(owner, "not-server-owner")
            self._show_main_menu(owner)
            return
        return await func(self, owner, *args, **kwargs)

    return wrapper


def require_developer(func):
    """Decorator that checks if the user has owner-level privileges (developer or
    server owner) before executing the action."""

    @functools.wraps(func)
    async def wrapper(self, user, *args, **kwargs):
        """Run the wrapped action if the user still has owner-level privileges."""
        if user.trust_level.value < TrustLevel.DEVELOPER.value:
            _speak_activity(user, "not-server-owner")
            self._show_main_menu(user)
            return
        return await func(self, user, *args, **kwargs)

    return wrapper


class AdministrationMixin:
    """Provide administration menu actions and account moderation flows.

    Expected attributes:
        _db: Database instance.
        _users: dict[str, NetworkUser] of online users.
        _user_states: dict[str, dict] of user menu states.
        _show_main_menu(user): Method to show the main menu.
    """

    _db: "Database"
    _users: dict[str, NetworkUser]
    _user_states: dict[str, dict]

    def _show_main_menu(self, user: NetworkUser) -> None:
        """Show main menu - to be implemented by the main class."""
        raise NotImplementedError

    def _notify_admins(
        self, message_id: str, sound: str, exclude_username: str | None = None
    ) -> None:
        """Notify all online admins with a message and sound, optionally excluding one admin."""
        for username, user in self._users.items():
            if user.trust_level.value < TrustLevel.ADMIN.value:
                continue  # Not an admin
            if exclude_username and username == exclude_username:
                continue  # Skip the excluded admin
            _speak_activity(user, message_id)
            user.play_sound(sound)

    # ==================== Menu Display Functions ====================

    def _show_admin_menu(self, user: NetworkUser) -> None:
        """Show administration menu."""
        items = [
            MenuItem(
                text=Localization.get(user.locale, "account-approval"),
                id="account_approval",
            ),
            MenuItem(
                text=Localization.get(user.locale, "reset-user-password"),
                id="reset_user_password",
            ),
            MenuItem(
                text=Localization.get(user.locale, "ban-user"),
                id="ban_user",
            ),
            MenuItem(
                text=Localization.get(user.locale, "unban-user"),
                id="unban_user",
            ),
            MenuItem(
                text=Localization.get(user.locale, "server-status"),
                id="server_status",
            ),
            MenuItem(
                text=Localization.get(user.locale, "kick-user"),
                id="kick_user",
            ),
            MenuItem(
                text=Localization.get(user.locale, "admin-reboot-server"),
                id="reboot_server",
            ),
        ]
        # Developers and server owners can promote/demote admins and manage virtual bots
        if user.trust_level.value >= TrustLevel.DEVELOPER.value:
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "promote-admin"),
                    id="promote_admin",
                )
            )
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "demote-admin"),
                    id="demote_admin",
                )
            )
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "virtual-bots"),
                    id="virtual_bots",
                )
            )
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "broadcast-announcement"),
                    id="broadcast_announcement",
                )
            )
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "lookup-user"),
                    id="lookup_user",
                )
            )
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "reload-caches"),
                    id="admin_reload_caches",
                )
            )
        # Only the server owner can change the server owner or manage developers
        if user.trust_level.value >= TrustLevel.SERVER_OWNER.value:
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "promote-developer"),
                    id="promote_developer",
                )
            )
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "demote-developer"),
                    id="demote_developer",
                )
            )
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "transfer-ownership"),
                    id="transfer_ownership",
                )
            )
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "scheduled-actions"),
                    id="scheduled_actions",
                )
            )
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "admin_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "admin_menu"}

    def _show_user_list_menu(
        self, user: NetworkUser, menu_id: str, users, id_prefix: str
    ) -> None:
        """Show a menu built from a list of user records.

        Args:
            user: The admin viewing the menu.
            menu_id: Menu identifier for the client.
            users: Iterable of objects with a ``.username`` attribute.
            id_prefix: Prefix for menu item IDs (e.g. ``"pending"``).
        """
        items = [MenuItem(text=u.username, id=f"{id_prefix}_{u.username}") for u in users]
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            menu_id, items, multiletter=True, escape_behavior=EscapeBehavior.SELECT_LAST
        )
        self._user_states[user.username] = {"menu": menu_id}

    def _show_account_approval_menu(self, user: NetworkUser) -> None:
        """Show account approval menu with pending users."""
        pending = self._db.get_pending_users()

        if not pending:
            _speak_activity(user, "no-pending-accounts")
            self._show_admin_menu(user)
            return

        self._show_user_list_menu(user, "account_approval_menu", pending, "pending")

    def _show_pending_user_actions_menu(self, user: NetworkUser, pending_username: str) -> None:
        """Show actions for a pending user (approve, decline)."""
        items = [
            MenuItem(text=Localization.get(user.locale, "approve-account"), id="approve"),
            MenuItem(text=Localization.get(user.locale, "decline-account"), id="decline"),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "pending_user_actions_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "pending_user_actions_menu",
            "pending_username": pending_username,
        }

    def _show_promote_admin_menu(self, user: NetworkUser) -> None:
        """Show promote admin menu with list of non-admin users."""
        non_admins = self._db.get_non_admin_users()

        if not non_admins:
            user.speak_l("no-users-to-promote", buffer="misc")
            self._show_admin_menu(user)
            return

        self._show_user_list_menu(user, "promote_admin_menu", non_admins, "promote")

    def _show_demote_admin_menu(self, user: NetworkUser) -> None:
        """Show demote admin menu with list of admin users."""
        # Exclude server owner from demotion list
        admins = self._db.get_admin_users(include_server_owner=False)

        # Filter out the current user (can't demote yourself)
        admins = [a for a in admins if a.username != user.username]

        if not admins:
            user.speak_l("no-admins-to-demote", buffer="misc")
            self._show_admin_menu(user)
            return

        self._show_user_list_menu(user, "demote_admin_menu", admins, "demote")

    def _show_reset_password_user_menu(self, user: NetworkUser) -> None:
        """Show reset password menu with users admins may reset."""
        resettable_users = self._db.get_non_admin_users(exclude_banned=True)

        if not resettable_users:
            user.speak_l("no-users-to-reset-password", buffer="misc")
            self._show_admin_menu(user)
            return

        items = []
        for resettable_user in resettable_users:
            items.append(
                MenuItem(
                    text=resettable_user.username,
                    id=f"reset_password_{resettable_user.username}",
                )
            )
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))

        user.show_menu(
            "reset_password_user_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "reset_password_user_menu"}

    def _show_reset_password_editbox(self, user: NetworkUser, target_username: str) -> None:
        """Show editbox for entering a replacement password."""
        prompt = Localization.get(user.locale, "reset-user-password-prompt", player=target_username)
        user.show_editbox(
            "reset_user_password",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {
            "menu": "reset_password_editbox",
            "target_username": target_username,
        }

    def _show_promote_confirm_menu(self, user: NetworkUser, target_username: str) -> None:
        """Show confirmation menu for promoting a user to admin."""
        question = Localization.get(user.locale, "confirm-promote", player=target_username)
        show_yes_no_menu(user, "promote_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "promote_confirm_menu",
            "target_username": target_username,
        }

    def _show_demote_confirm_menu(self, user: NetworkUser, target_username: str) -> None:
        """Show confirmation menu for demoting an admin."""
        question = Localization.get(user.locale, "confirm-demote", player=target_username)
        show_yes_no_menu(user, "demote_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "demote_confirm_menu",
            "target_username": target_username,
        }

    def _show_promote_developer_menu(self, user: NetworkUser) -> None:
        """Show promote developer menu with list of admin users."""
        admins = self._db.get_admin_users(include_server_owner=False)

        if not admins:
            user.speak_l("no-admins-to-promote-developer", buffer="misc")
            self._show_admin_menu(user)
            return

        self._show_user_list_menu(user, "promote_developer_menu", admins, "promote_dev")

    def _show_demote_developer_menu(self, user: NetworkUser) -> None:
        """Show demote developer menu with list of developer users."""
        developers = self._db.get_developers()

        if not developers:
            user.speak_l("no-developers-to-demote", buffer="misc")
            self._show_admin_menu(user)
            return

        self._show_user_list_menu(user, "demote_developer_menu", developers, "demote_dev")

    def _show_promote_developer_confirm_menu(
        self, user: NetworkUser, target_username: str
    ) -> None:
        """Show confirmation menu for promoting an admin to developer."""
        question = Localization.get(
            user.locale, "confirm-promote-developer", player=target_username
        )
        show_yes_no_menu(user, "promote_developer_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "promote_developer_confirm_menu",
            "target_username": target_username,
        }

    def _show_demote_developer_confirm_menu(
        self, user: NetworkUser, target_username: str
    ) -> None:
        """Show confirmation menu for demoting a developer to admin."""
        question = Localization.get(
            user.locale, "confirm-demote-developer", player=target_username
        )
        show_yes_no_menu(user, "demote_developer_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "demote_developer_confirm_menu",
            "target_username": target_username,
        }

    def _show_broadcast_choice_menu(
        self, user: NetworkUser, action: str, target_username: str
    ) -> None:
        """Show menu to choose broadcast audience (all users, admins only, or nobody/silent)."""
        items = [
            MenuItem(text=Localization.get(user.locale, "broadcast-to-all"), id="all"),
            MenuItem(text=Localization.get(user.locale, "broadcast-to-admins"), id="admins"),
            MenuItem(text=Localization.get(user.locale, "broadcast-to-nobody"), id="nobody"),
        ]
        user.show_menu(
            "broadcast_choice_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "broadcast_choice_menu",
            "action": action,  # "promote", "demote", "ban", or "unban"
            "target_username": target_username,
        }

    def _show_transfer_ownership_menu(self, user: NetworkUser) -> None:
        """Show transfer ownership menu with list of admin users."""
        # Only admins can receive ownership (exclude server owner)
        admins = self._db.get_admin_users(include_server_owner=False)

        if not admins:
            user.speak_l("no-admins-for-transfer", buffer="misc")
            self._show_admin_menu(user)
            return

        self._show_user_list_menu(user, "transfer_ownership_menu", admins, "transfer")

    def _show_transfer_ownership_confirm_menu(
        self, user: NetworkUser, target_username: str
    ) -> None:
        """Show confirmation menu for transferring ownership."""
        question = Localization.get(
            user.locale, "confirm-transfer-ownership", player=target_username
        )
        show_yes_no_menu(user, "transfer_ownership_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "transfer_ownership_confirm_menu",
            "target_username": target_username,
        }

    def _show_transfer_broadcast_choice_menu(self, user: NetworkUser, target_username: str) -> None:
        """Show menu to choose broadcast audience for ownership transfer."""
        items = [
            MenuItem(text=Localization.get(user.locale, "broadcast-to-all"), id="all"),
            MenuItem(text=Localization.get(user.locale, "broadcast-to-admins"), id="admins"),
            MenuItem(text=Localization.get(user.locale, "broadcast-to-nobody"), id="nobody"),
        ]
        user.show_menu(
            "transfer_broadcast_choice_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "transfer_broadcast_choice_menu",
            "target_username": target_username,
        }

    def _show_ban_user_menu(self, user: NetworkUser) -> None:
        """Show ban user menu with list of non-admin users who aren't banned."""
        # Get non-admin users who aren't banned (admins must be demoted first)
        bannable_users = self._db.get_non_admin_users(exclude_banned=True)

        if not bannable_users:
            user.speak_l("no-users-to-ban", buffer="misc")
            self._show_admin_menu(user)
            return

        self._show_user_list_menu(user, "ban_user_menu", bannable_users, "ban")

    def _show_unban_user_menu(self, user: NetworkUser) -> None:
        """Show unban user menu with list of banned users."""
        banned_users = self._db.get_banned_users()

        if not banned_users:
            user.speak_l("no-users-to-unban", buffer="misc")
            self._show_admin_menu(user)
            return

        self._show_user_list_menu(user, "unban_user_menu", banned_users, "unban")

    def _show_ban_confirm_menu(self, user: NetworkUser, target_username: str) -> None:
        """Show confirmation menu for banning a user."""
        question = Localization.get(user.locale, "confirm-ban", player=target_username)
        show_yes_no_menu(user, "ban_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "ban_confirm_menu",
            "target_username": target_username,
        }

    def _show_unban_confirm_menu(self, user: NetworkUser, target_username: str) -> None:
        """Show confirmation menu for unbanning a user."""
        question = Localization.get(user.locale, "confirm-unban", player=target_username)
        show_yes_no_menu(user, "unban_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "unban_confirm_menu",
            "target_username": target_username,
        }

    def _show_reboot_server_confirm_menu(self, user: NetworkUser) -> None:
        """Show confirmation menu for rebooting the server."""
        question = Localization.get(user.locale, "confirm-reboot-server")
        show_yes_no_menu(user, "reboot_server_confirm_menu", question)
        self._user_states[user.username] = {"menu": "reboot_server_confirm_menu"}

    def _show_reboot_server_bots_confirm_menu(self, user: NetworkUser) -> None:
        """Warn the admin that virtual bots are connected before rebooting."""
        status = self._virtual_bots.get_status()
        bots = status.get("online", 0) + status.get("in_game", 0)
        question = Localization.get(
            user.locale, "confirm-reboot-server-bots-connected", bots=bots
        )
        show_yes_no_menu(user, "reboot_server_bots_confirm_menu", question)
        self._user_states[user.username] = {"menu": "reboot_server_bots_confirm_menu"}

    def _show_server_status_menu(self, user: NetworkUser) -> None:
        """Show a read-only snapshot of the server's runtime state."""
        import time

        started_at = getattr(self, "_started_at", None)
        if started_at is not None:
            uptime_minutes = int((time.monotonic() - started_at) // 60)
        else:
            uptime_minutes = 0

        online_users = len(self._users)
        approved_users = sum(
            1 for u in self._users.values() if getattr(u, "approved", True)
        )
        open_tables = len(self._tables.get_all_tables())
        db_users = self._db.get_user_count()
        bot_status = self._virtual_bots.get_status()
        tick_scheduler = getattr(self, "_tick_scheduler", None)
        tick = getattr(tick_scheduler, "tick", 0) if tick_scheduler else 0

        lines = [
            Localization.get(user.locale, "server-status-title"),
            "",
            Localization.get(user.locale, "server-status-uptime", minutes=uptime_minutes),
            Localization.get(user.locale, "server-status-tick", tick=tick),
            Localization.get(user.locale, "server-status-online-users", count=online_users),
            Localization.get(user.locale, "server-status-approved", count=approved_users),
            Localization.get(user.locale, "server-status-tables", count=open_tables),
            Localization.get(user.locale, "server-status-db-users", count=db_users),
            Localization.get(
                user.locale,
                "server-status-virtual-bots",
                total=bot_status.get("total", 0),
                online=bot_status.get("online", 0),
                in_game=bot_status.get("in_game", 0),
            ),
        ]
        user.show_menu(
            "server_status_menu",
            [MenuItem(text=line, id=f"line_{i}") for i, line in enumerate(lines)]
            + [MenuItem(text=Localization.get(user.locale, "back"), id="back")],
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "server_status_menu"}

    def _show_kick_user_menu(self, user: NetworkUser) -> None:
        """Show menu of online users the requesting admin may kick."""
        kickable = []
        for username, online_user in self._users.items():
            if username == user.username:
                continue
            if online_user.trust_level.value >= user.trust_level.value:
                continue
            kickable.append(online_user)
        kickable.sort(key=lambda u: u.username.lower())

        if not kickable:
            user.speak_l("no-users-to-kick", buffer="misc")
            self._show_admin_menu(user)
            return

        items = [MenuItem(text=u.username, id=f"kick_{u.username}") for u in kickable]
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "kick_user_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "kick_user_menu"}

    def _show_kick_confirm_menu(self, user: NetworkUser, target_username: str) -> None:
        """Show confirmation menu for kicking a user."""
        question = Localization.get(user.locale, "confirm-kick-user", player=target_username)
        show_yes_no_menu(user, "kick_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "kick_confirm_menu",
            "target_username": target_username,
        }

    def _show_broadcast_announcement_editbox(self, user: NetworkUser) -> None:
        """Show editbox for composing a server-wide announcement."""
        prompt = Localization.get(user.locale, "broadcast-announcement-prompt")
        user.show_editbox(
            "broadcast_announcement",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "broadcast_announcement_editbox"}

    def _show_lookup_user_editbox(self, user: NetworkUser) -> None:
        """Show editbox for entering a username to look up."""
        prompt = Localization.get(user.locale, "lookup-user-prompt")
        user.show_editbox(
            "lookup_user",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "lookup_user_editbox"}

    def _show_reload_caches_confirm_menu(self, user: NetworkUser) -> None:
        """Show confirmation menu for force-reloading server caches."""
        question = Localization.get(user.locale, "confirm-reload-caches")
        show_yes_no_menu(user, "reload_caches_confirm_menu", question)
        self._user_states[user.username] = {"menu": "reload_caches_confirm_menu"}

    def _show_scheduled_actions_menu(self, user: NetworkUser) -> None:
        """Show the scheduled actions management menu."""
        actions = self._scheduler.list_actions()
        items = []
        if not actions:
            items.append(
                MenuItem(
                    text=Localization.get(user.locale, "scheduled-actions-none"),
                    id="_none",
                )
            )
        for action in actions:
            label = self._scheduled_action_label(user, action)
            items.append(MenuItem(text=label, id=f"sa_{action.id}"))
        items.append(
            MenuItem(text=Localization.get(user.locale, "scheduled-actions-add"), id="sa_add")
        )
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "scheduled_actions_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "scheduled_actions_menu"}

    def _scheduled_action_label(self, user: NetworkUser, action) -> str:
        """Build a localized label row for a scheduled action."""
        type_name = Localization.get(
            user.locale,
            "scheduled-action-reboot"
            if action.action_type == "reboot"
            else "scheduled-action-broadcast",
        )
        when = (
            Localization.get(
                user.locale,
                "repeating-every-minutes",
                minutes=int(action.repeat_interval_seconds // 60),
            )
            if action.repeating
            else Localization.get(user.locale, "one-shot")
        )
        run_text = Localization.get(
            user.locale,
            "scheduled-action-run-at",
            time=action.run_at.strftime("%Y-%m-%d %H:%M"),
        )
        state_text = (
            Localization.get(user.locale, "scheduled-action-enabled")
            if action.enabled
            else Localization.get(user.locale, "scheduled-action-disabled")
        )
        return f"#{action.id} {type_name} • {run_text} • {when} • {state_text}"

    def _show_schedule_type_menu(self, user: NetworkUser) -> None:
        """Choose the type of action to schedule."""
        items = [
            MenuItem(text=Localization.get(user.locale, "scheduled-action-reboot"), id="type_reboot"),
            MenuItem(
                text=Localization.get(user.locale, "scheduled-action-broadcast"),
                id="type_broadcast",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "schedule_type_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "schedule_type_menu"}

    def _show_schedule_message_editbox(self, user: NetworkUser) -> None:
        """Show editbox for the announcement text."""
        prompt = Localization.get(user.locale, "scheduled-actions-message-prompt")
        user.show_editbox(
            "schedule_message",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "schedule_message_editbox"}

    def _show_schedule_when_editbox(self, user: NetworkUser) -> None:
        """Show editbox for how many minutes from now to run."""
        prompt = Localization.get(user.locale, "scheduled-actions-when-prompt")
        user.show_editbox(
            "schedule_when",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "schedule_when_editbox"}

    def _show_schedule_repeat_editbox(self, user: NetworkUser) -> None:
        """Show editbox for the repeat interval in minutes (0 = one-shot)."""
        prompt = Localization.get(user.locale, "scheduled-actions-repeat-prompt")
        user.show_editbox(
            "schedule_repeat",
            prompt,
            default_value="0",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "schedule_repeat_editbox"}

    def _show_schedule_confirm_menu(self, user: NetworkUser, summary: str) -> None:
        """Show confirmation for the composed scheduled action."""
        show_yes_no_menu(user, "schedule_confirm_menu", summary)
        self._user_states[user.username] = {
            "menu": "schedule_confirm_menu",
            "schedule_summary": summary,
        }

    def _show_scheduled_action_actions_menu(self, user: NetworkUser, action_id: int) -> None:
        """Show actions (enable/disable/delete) for one scheduled action."""
        items = [
            MenuItem(
                text=Localization.get(user.locale, "scheduled-action-toggle"),
                id=f"sa_toggle_{action_id}",
            ),
            MenuItem(
                text=Localization.get(user.locale, "scheduled-action-delete"),
                id=f"sa_delete_{action_id}",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "scheduled_action_actions_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "scheduled_action_actions_menu",
            "scheduled_action_id": action_id,
        }

    def _show_schedule_delete_confirm_menu(self, user: NetworkUser, action_id: int) -> None:
        """Show confirmation before deleting a scheduled action."""
        question = Localization.get(user.locale, "scheduled-action-delete-confirm", id=action_id)
        show_yes_no_menu(user, "schedule_delete_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "schedule_delete_confirm_menu",
            "scheduled_action_id": action_id,
        }

    def _show_ban_reason_editbox(
        self, user: NetworkUser, target_username: str, broadcast_scope: str
    ) -> None:
        """Show editbox for entering ban reason."""
        prompt = Localization.get(user.locale, "ban-reason-prompt")
        user.show_editbox(
            "ban_reason",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {
            "menu": "ban_reason_editbox",
            "target_username": target_username,
            "broadcast_scope": broadcast_scope,
        }

    def _show_unban_reason_editbox(
        self, user: NetworkUser, target_username: str, broadcast_scope: str
    ) -> None:
        """Show editbox for entering unban reason."""
        prompt = Localization.get(user.locale, "unban-reason-prompt")
        user.show_editbox(
            "unban_reason",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {
            "menu": "unban_reason_editbox",
            "target_username": target_username,
            "broadcast_scope": broadcast_scope,
        }

    def _show_virtual_bots_menu(self, user: NetworkUser) -> None:
        """Show virtual bots management menu."""
        # Get current status if manager exists
        status_text = ""
        if hasattr(self, "_virtual_bots") and self._virtual_bots:
            status = self._virtual_bots.get_status()
            status_text = f" ({status['online']}/{status['total']})"

        items = [
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-fill") + status_text,
                id="fill",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-clear"),
                id="clear",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-bring-online"),
                id="online",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-take-offline"),
                id="offline",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-status"),
                id="status",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-guided-overview"),
                id="guided",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-groups-overview"),
                id="groups",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-profiles-overview"),
                id="profiles",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-presence"),
                id="presence",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-add"),
                id="add",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-edit"),
                id="edit",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-delete"),
                id="delete",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "virtual_bots_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "virtual_bots_menu"}

    def _show_virtual_bots_clear_confirm_menu(self, user: NetworkUser) -> None:
        """Show confirmation menu for clearing all virtual bots."""
        question = Localization.get(user.locale, "virtual-bots-clear-confirm")
        show_yes_no_menu(user, "virtual_bots_clear_confirm_menu", question)
        self._user_states[user.username] = {"menu": "virtual_bots_clear_confirm_menu"}

    def _show_add_bot_name_editbox(self, user: NetworkUser) -> None:
        """Show editbox for entering a new virtual bot name."""
        prompt = Localization.get(user.locale, "virtual-bots-add-prompt")
        user.show_editbox(
            "bot_name_editbox",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {"menu": "bot_name_editbox", "mode": "add"}

    def _show_edit_bot_menu(self, user: NetworkUser) -> None:
        """Show list of virtual bots to edit."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(user, "virtual-bots-not-available")
            self._show_virtual_bots_menu(user)
            return
        roster = manager.get_roster()
        if not roster:
            user.speak_l("virtual-bots-no-bots", buffer="misc")
            self._show_virtual_bots_menu(user)
            return
        items = [MenuItem(text=entry["name"], id=f"edit_{entry['name']}") for entry in roster]
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "edit_bot_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "edit_bot_menu"}

    def _show_edit_bot_actions_menu(self, user: NetworkUser, bot_name: str) -> None:
        """Show actions for editing a single virtual bot."""
        items = [
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-rename"),
                id="rename",
            ),
            MenuItem(
                text=Localization.get(user.locale, "virtual-bots-change-profile"),
                id="profile",
            ),
            MenuItem(text=Localization.get(user.locale, "back"), id="back"),
        ]
        user.show_menu(
            "edit_bot_actions_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "edit_bot_actions_menu",
            "bot_name": bot_name,
        }

    def _show_rename_bot_editbox(self, user: NetworkUser, bot_name: str) -> None:
        """Show editbox for renaming a virtual bot (pre-filled with current name)."""
        prompt = Localization.get(user.locale, "virtual-bots-rename-prompt", name=bot_name)
        user.show_editbox(
            "rename_bot_editbox",
            prompt,
            default_value=bot_name,
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {
            "menu": "rename_bot_editbox",
            "bot_name": bot_name,
        }

    def _show_bot_profile_menu(self, user: NetworkUser, bot_name: str) -> None:
        """Show profile selection menu for a virtual bot."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(user, "virtual-bots-not-available")
            self._show_virtual_bots_menu(user)
            return
        profiles = manager.get_profiles()
        if not profiles:
            user.speak_l("virtual-bots-no-profiles", buffer="misc")
            self._show_edit_bot_actions_menu(user, bot_name)
            return
        items = [MenuItem(text=profile, id=profile) for profile in profiles]
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "bot_profile_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {
            "menu": "bot_profile_menu",
            "bot_name": bot_name,
        }

    def _show_delete_bot_menu(self, user: NetworkUser) -> None:
        """Show list of virtual bots to delete."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(user, "virtual-bots-not-available")
            self._show_virtual_bots_menu(user)
            return
        roster = manager.get_roster()
        if not roster:
            user.speak_l("virtual-bots-no-bots", buffer="misc")
            self._show_virtual_bots_menu(user)
            return
        items = [MenuItem(text=entry["name"], id=f"del_{entry['name']}") for entry in roster]
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "delete_bot_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "delete_bot_menu"}

    def _show_delete_bot_confirm_menu(self, user: NetworkUser, bot_name: str) -> None:
        """Show confirmation menu for deleting a virtual bot."""
        question = Localization.get(user.locale, "virtual-bots-delete-confirm", name=bot_name)
        show_yes_no_menu(user, "delete_bot_confirm_menu", question)
        self._user_states[user.username] = {
            "menu": "delete_bot_confirm_menu",
            "bot_name": bot_name,
        }

    def _show_bring_online_bot_menu(self, user: NetworkUser) -> None:
        """Show list of offline virtual bots that can be brought online."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(user, "virtual-bots-not-available")
            self._show_virtual_bots_menu(user)
            return
        roster = manager.get_roster()
        offline = [entry for entry in roster if not entry["online"]]
        if not offline:
            user.speak_l("virtual-bots-all-online", buffer="misc")
            self._show_virtual_bots_menu(user)
            return
        items = [MenuItem(text=entry["name"], id=f"online_{entry['name']}") for entry in offline]
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "bring_online_bot_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "bring_online_bot_menu"}

    def _show_take_offline_bot_menu(self, user: NetworkUser) -> None:
        """Show list of online virtual bots that can be taken offline."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(user, "virtual-bots-not-available")
            self._show_virtual_bots_menu(user)
            return
        roster = manager.get_roster()
        online = [entry for entry in roster if entry["online"]]
        if not online:
            user.speak_l("virtual-bots-all-offline", buffer="misc")
            self._show_virtual_bots_menu(user)
            return
        items = [MenuItem(text=entry["name"], id=f"offline_{entry['name']}") for entry in online]
        items.append(MenuItem(text=Localization.get(user.locale, "back"), id="back"))
        user.show_menu(
            "take_offline_bot_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[user.username] = {"menu": "take_offline_bot_menu"}

    # ==================== Menu Selection Handlers ====================

    async def _handle_admin_menu_selection(self, user: NetworkUser, selection_id: str) -> None:
        """Handle admin menu selection."""
        if selection_id == "account_approval":
            self._show_account_approval_menu(user)
        elif selection_id == "reset_user_password":
            self._show_reset_password_user_menu(user)
        elif selection_id == "promote_admin":
            self._show_promote_admin_menu(user)
        elif selection_id == "demote_admin":
            self._show_demote_admin_menu(user)
        elif selection_id == "transfer_ownership":
            self._show_transfer_ownership_menu(user)
        elif selection_id == "ban_user":
            self._show_ban_user_menu(user)
        elif selection_id == "unban_user":
            self._show_unban_user_menu(user)
        elif selection_id == "virtual_bots":
            self._show_virtual_bots_menu(user)
        elif selection_id == "server_status":
            self._show_server_status_menu(user)
        elif selection_id == "kick_user":
            self._show_kick_user_menu(user)
        elif selection_id == "broadcast_announcement":
            self._show_broadcast_announcement_editbox(user)
        elif selection_id == "lookup_user":
            self._show_lookup_user_editbox(user)
        elif selection_id == "admin_reload_caches":
            self._show_reload_caches_confirm_menu(user)
        elif selection_id == "scheduled_actions":
            self._show_scheduled_actions_menu(user)
        elif selection_id == "reboot_server":
            self._show_reboot_server_confirm_menu(user)
        elif selection_id == "promote_developer":
            self._show_promote_developer_menu(user)
        elif selection_id == "demote_developer":
            self._show_demote_developer_menu(user)
        elif selection_id == "back":
            self._show_main_menu(user)

    async def _handle_account_approval_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle account approval menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("pending_"):
            pending_username = selection_id[8:]  # Remove "pending_" prefix
            self._show_pending_user_actions_menu(user, pending_username)

    async def _handle_pending_user_actions_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle pending user actions menu selection."""
        pending_username = state.get("pending_username")
        if not pending_username:
            self._show_account_approval_menu(user)
            return

        if selection_id == "approve":
            await self._approve_user(user, pending_username)
        elif selection_id == "decline":
            self._show_decline_reason_editbox(user, pending_username)
        elif selection_id == "back":
            self._show_account_approval_menu(user)

    def _show_decline_reason_editbox(self, user: NetworkUser, pending_username: str) -> None:
        """Show editbox for entering decline reason."""
        prompt = Localization.get(user.locale, "decline-reason-prompt")
        user.show_editbox(
            "decline_reason",
            prompt,
            default_value="",
            multiline=False,
            read_only=False,
        )
        self._user_states[user.username] = {
            "menu": "decline_reason_editbox",
            "pending_username": pending_username,
        }

    async def _handle_decline_reason_editbox(
        self, admin: NetworkUser, text: str, state: dict
    ) -> None:
        """Handle decline reason editbox submission."""
        pending_username = state.get("pending_username")
        if not pending_username:
            self._show_account_approval_menu(admin)
            return

        # Proceed with decline, passing the reason (empty text uses fallback)
        await self._decline_user(admin, pending_username, reason=text)

    async def _handle_promote_admin_selection(self, user: NetworkUser, selection_id: str) -> None:
        """Handle promote admin menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("promote_"):
            target_username = selection_id[8:]  # Remove "promote_" prefix
            self._show_promote_confirm_menu(user, target_username)

    async def _handle_demote_admin_selection(self, user: NetworkUser, selection_id: str) -> None:
        """Handle demote admin menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("demote_"):
            target_username = selection_id[7:]  # Remove "demote_" prefix
            self._show_demote_confirm_menu(user, target_username)

    async def _handle_promote_developer_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle promote developer menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("promote_dev_"):
            target_username = selection_id[12:]  # Remove "promote_dev_" prefix
            self._show_promote_developer_confirm_menu(user, target_username)

    async def _handle_demote_developer_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle demote developer menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("demote_dev_"):
            target_username = selection_id[11:]  # Remove "demote_dev_" prefix
            self._show_demote_developer_confirm_menu(user, target_username)

    async def _handle_reset_password_user_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle reset password user menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("reset_password_"):
            target_username = selection_id[15:]
            self._show_reset_password_editbox(user, target_username)

    async def _handle_reset_password_editbox(
        self, admin: NetworkUser, text: str, state: dict
    ) -> None:
        """Handle replacement password submission."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_reset_password_user_menu(admin)
            return

        password = text or ""
        min_length = self._password_min_length
        max_length = self._password_max_length
        if not (min_length <= len(password) <= max_length):
            admin.speak_l(
                "credential-password-length",
                min=min_length,
                max=max_length,
                buffer="activity",
            )
            self._show_reset_password_editbox(admin, target_username)
            return

        await self._reset_user_password(admin, target_username, password)

    async def _handle_promote_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle promote confirmation menu selection."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_promote_admin_menu(user)
            return

        if selection_id == "yes":
            # Show broadcast choice menu
            self._show_broadcast_choice_menu(user, "promote", target_username)
        else:
            # No or back - return to promote admin menu
            self._show_promote_admin_menu(user)

    async def _handle_demote_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle demote confirmation menu selection."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_demote_admin_menu(user)
            return

        if selection_id == "yes":
            # Show broadcast choice menu
            self._show_broadcast_choice_menu(user, "demote", target_username)
        else:
            # No or back - return to demote admin menu
            self._show_demote_admin_menu(user)

    async def _handle_promote_developer_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle promote developer confirmation menu selection."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_promote_developer_menu(user)
            return

        if selection_id == "yes":
            # Show broadcast choice menu
            self._show_broadcast_choice_menu(user, "promote_developer", target_username)
        else:
            # No or back - return to promote developer menu
            self._show_promote_developer_menu(user)

    async def _handle_demote_developer_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle demote developer confirmation menu selection."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_demote_developer_menu(user)
            return

        if selection_id == "yes":
            # Show broadcast choice menu
            self._show_broadcast_choice_menu(user, "demote_developer", target_username)
        else:
            # No or back - return to demote developer menu
            self._show_demote_developer_menu(user)

    async def _handle_broadcast_choice_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle broadcast choice menu selection."""
        action = state.get("action")
        target_username = state.get("target_username")

        if not action or not target_username:
            self._show_admin_menu(user)
            return

        # Determine broadcast scope: "all", "admins", or "nobody"
        broadcast_scope = selection_id  # "all", "admins", or "nobody"

        if action == "promote":
            await self._promote_to_admin(user, target_username, broadcast_scope)
        elif action == "demote":
            await self._demote_from_admin(user, target_username, broadcast_scope)
        elif action == "promote_developer":
            await self._promote_to_developer(user, target_username, broadcast_scope)
        elif action == "demote_developer":
            await self._demote_from_developer(user, target_username, broadcast_scope)
        elif action == "ban":
            self._show_ban_reason_editbox(user, target_username, broadcast_scope)
        elif action == "unban":
            self._show_unban_reason_editbox(user, target_username, broadcast_scope)

    async def _handle_transfer_ownership_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle transfer ownership menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("transfer_"):
            target_username = selection_id[9:]  # Remove "transfer_" prefix
            self._show_transfer_ownership_confirm_menu(user, target_username)

    async def _handle_transfer_ownership_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle transfer ownership confirmation menu selection."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_transfer_ownership_menu(user)
            return

        if selection_id == "yes":
            # Show broadcast choice menu
            self._show_transfer_broadcast_choice_menu(user, target_username)
        else:
            # No or back - return to transfer ownership menu
            self._show_transfer_ownership_menu(user)

    async def _handle_transfer_broadcast_choice_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle transfer broadcast choice menu selection."""
        target_username = state.get("target_username")

        if not target_username:
            self._show_admin_menu(user)
            return

        # Determine broadcast scope: "all", "admins", or "nobody"
        broadcast_scope = selection_id

        await self._transfer_ownership(user, target_username, broadcast_scope)

    async def _handle_ban_user_selection(self, user: NetworkUser, selection_id: str) -> None:
        """Handle ban user menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("ban_"):
            target_username = selection_id[4:]  # Remove "ban_" prefix
            self._show_ban_confirm_menu(user, target_username)

    async def _handle_unban_user_selection(self, user: NetworkUser, selection_id: str) -> None:
        """Handle unban user menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("unban_"):
            target_username = selection_id[6:]  # Remove "unban_" prefix
            self._show_unban_confirm_menu(user, target_username)

    async def _handle_ban_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle ban confirmation menu selection."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_ban_user_menu(user)
            return

        if selection_id == "yes":
            # Show broadcast choice menu
            self._show_broadcast_choice_menu(user, "ban", target_username)
        else:
            # No or back - return to ban user menu
            self._show_ban_user_menu(user)

    async def _handle_unban_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle unban confirmation menu selection."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_unban_user_menu(user)
            return

        if selection_id == "yes":
            # Show broadcast choice menu
            self._show_broadcast_choice_menu(user, "unban", target_username)
        else:
            # No or back - return to unban user menu
            self._show_unban_user_menu(user)

    async def _handle_reboot_server_confirm_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle reboot server confirmation menu selection.

        If any virtual bots are online, route through an extra confirmation
        so the admin explicitly approves disconnecting them before reboot.
        """
        if selection_id != "yes":
            self._show_admin_menu(user)
            return

        if self._bots_connected():
            self._show_reboot_server_bots_confirm_menu(user)
        else:
            await self._reboot_server(user)

    def _bots_connected(self) -> bool:
        """Return True if any virtual bots are currently online or in game."""
        status = self._virtual_bots.get_status()
        return status.get("online", 0) + status.get("in_game", 0) > 0

    async def _handle_reboot_server_bots_confirm_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle the bots-connected reboot warning confirmation."""
        if selection_id == "yes":
            self._virtual_bots.disconnect_all_bots()
            await self._reboot_server(user)
        else:
            self._show_admin_menu(user)

    async def _handle_server_status_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle server status menu selection (read-only, so just go back)."""
        self._show_admin_menu(user)

    async def _handle_reload_caches_confirm_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle force-reload cache confirmation."""
        if selection_id == "yes":
            await self._reload_caches(user)
        else:
            self._show_admin_menu(user)

    async def _reload_caches(self, user: NetworkUser) -> None:
        """Force-reload localization bundles and documents from disk."""
        from ..messages.localization import Localization as _Localization

        locale_count = _Localization.reload(force=True)
        doc_count = self._documents.load()
        user.speak_l(
            "reload-caches-done",
            locales=locale_count,
            documents=doc_count,
            buffer="activity",
        )
        # Recompile any missing locale bundles in a background thread.
        self._start_localization_warmup()
        self._show_admin_menu(user)

    async def _handle_scheduled_actions_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle the scheduled actions list menu."""
        if selection_id == "back" or selection_id.startswith("sa_add"):
            if selection_id == "sa_add":
                self._show_schedule_type_menu(user)
            else:
                self._show_admin_menu(user)
        elif selection_id.startswith("sa_"):
            try:
                action_id = int(selection_id[3:])
            except ValueError:
                self._show_scheduled_actions_menu(user)
                return
            self._show_scheduled_action_actions_menu(user, action_id)
        else:
            self._show_scheduled_actions_menu(user)

    async def _handle_schedule_type_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle the schedule type menu."""
        if selection_id == "back":
            self._show_scheduled_actions_menu(user)
            return
        if selection_id == "type_reboot":
            self._user_states[user.username]["schedule_type"] = "reboot"
            self._show_schedule_when_editbox(user)
        elif selection_id == "type_broadcast":
            self._user_states[user.username]["schedule_type"] = "broadcast"
            self._show_schedule_message_editbox(user)
        else:
            self._show_schedule_type_menu(user)

    async def _handle_schedule_message_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Store the announcement text, then ask when to run."""
        message = (text or "").strip()
        if not message:
            user.speak_l("scheduled-actions-empty-message", buffer="misc")
            self._show_schedule_message_editbox(user)
            return
        state["schedule_message"] = message
        self._show_schedule_when_editbox(user)

    async def _handle_schedule_when_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Store minutes-from-now, then ask for the repeat interval."""
        try:
            minutes = int(text.strip())
        except (TypeError, ValueError):
            user.speak_l("scheduled-actions-invalid-number", buffer="misc")
            self._show_schedule_when_editbox(user)
            return
        if minutes < 0:
            user.speak_l("scheduled-actions-invalid-number", buffer="misc")
            self._show_schedule_when_editbox(user)
            return
        state["schedule_minutes"] = minutes
        self._show_schedule_repeat_editbox(user)

    async def _handle_schedule_repeat_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Store repeat interval and show confirmation."""
        try:
            repeat_minutes = int(text.strip())
        except (TypeError, ValueError):
            user.speak_l("scheduled-actions-invalid-number", buffer="misc")
            self._show_schedule_repeat_editbox(user)
            return
        if repeat_minutes < 0:
            user.speak_l("scheduled-actions-invalid-number", buffer="misc")
            self._show_schedule_repeat_editbox(user)
            return
        state["schedule_repeat_minutes"] = repeat_minutes
        action_type = state.get("schedule_type")
        minutes = state.get("schedule_minutes", 0)
        summary = self._compose_schedule_summary(user, action_type, minutes, repeat_minutes)
        self._show_schedule_confirm_menu(user, summary)

    def _compose_schedule_summary(
        self, user: NetworkUser, action_type: str | None, minutes: int, repeat_minutes: int
    ) -> str:
        """Build a localized confirmation summary for a new scheduled action."""
        type_name = Localization.get(
            user.locale,
            "scheduled-action-reboot" if action_type == "reboot" else "scheduled-action-broadcast",
        )
        parts = [
            Localization.get(user.locale, "scheduled-actions-summary-type", type=type_name),
            Localization.get(
                user.locale, "scheduled-actions-summary-when", minutes=minutes
            ),
        ]
        if repeat_minutes and repeat_minutes > 0:
            parts.append(
                Localization.get(
                    user.locale,
                    "scheduled-actions-summary-repeat",
                    minutes=repeat_minutes,
                )
            )
        return "".join(parts)

    async def _handle_schedule_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Create the scheduled action on confirmation."""
        if selection_id != "yes":
            self._show_scheduled_actions_menu(user)
            return
        action_type = state.get("schedule_type")
        minutes = state.get("schedule_minutes", 0)
        repeat_minutes = state.get("schedule_repeat_minutes", 0)
        if action_type not in ("reboot", "broadcast"):
            self._show_scheduled_actions_menu(user)
            return
        payload = {}
        if action_type == "broadcast":
            payload["message"] = state.get("schedule_message", "")
        run_at = self._scheduler.run_at_from_minutes_from_now(minutes)
        self._scheduler.create_action(
            action_type=action_type,
            run_at=run_at,
            repeat_interval_seconds=repeat_minutes * 60,
            payload=payload,
            created_by=user.username,
        )
        user.speak_l("scheduled-actions-created", buffer="activity")
        self._show_scheduled_actions_menu(user)

    async def _handle_scheduled_action_actions_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle actions on one scheduled action (toggle/delete)."""
        action_id = state.get("scheduled_action_id")
        if action_id is None:
            self._show_scheduled_actions_menu(user)
            return
        if selection_id.startswith(f"sa_toggle_{action_id}"):
            actions = {a.id: a for a in self._scheduler.list_actions()}
            action = actions.get(action_id)
            if action:
                self._scheduler.set_enabled(action_id, not action.enabled)
            self._show_scheduled_actions_menu(user)
        elif selection_id.startswith(f"sa_delete_{action_id}"):
            self._show_schedule_delete_confirm_menu(user, action_id)
        elif selection_id == "back":
            self._show_scheduled_actions_menu(user)
        else:
            self._show_scheduled_actions_menu(user)

    async def _handle_schedule_delete_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle deleting a scheduled action confirmation."""
        action_id = state.get("scheduled_action_id")
        if action_id is not None and selection_id == "yes":
            self._scheduler.delete_action(action_id)
            user.speak_l("scheduled-actions-deleted", buffer="activity")
        self._show_scheduled_actions_menu(user)

    async def _handle_kick_user_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle kick user menu selection."""
        if selection_id == "back":
            self._show_admin_menu(user)
        elif selection_id.startswith("kick_"):
            target_username = selection_id[5:]
            self._show_kick_confirm_menu(user, target_username)

    async def _handle_kick_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle kick confirmation menu selection."""
        target_username = state.get("target_username")
        if not target_username:
            self._show_kick_user_menu(user)
            return

        if selection_id != "yes":
            self._show_admin_menu(user)
            return

        target = self._users.get(target_username)
        if not target:
            if user.username != target_username:
                user.speak_l("user-not-online", player=target_username, buffer="activity")
            self._show_admin_menu(user)
            return
        if target.trust_level.value >= user.trust_level.value:
            user.speak_l("cannot-kick-higher-rank", player=target_username, buffer="activity")
            self._show_admin_menu(user)
            return

        try:
            await target.connection.send({"type": "disconnect", "reconnect": True})
            await target.connection.close()
        except Exception:  # noqa: BLE001 - best effort kick
            LOG.exception("Failed to kick user %s", target_username)
        user.speak_l("user-kicked", player=target_username, buffer="activity")
        self._show_admin_menu(user)

    async def _handle_broadcast_announcement_editbox(
        self, admin: NetworkUser, text: str, state: dict
    ) -> None:
        """Broadcast a free-text announcement to every approved online user."""
        message = (text or "").strip()
        if not message:
            admin.speak_l("broadcast-empty-message", buffer="misc")
            self._show_admin_menu(admin)
            return

        recipients = 0
        for _username, online_user in self._iter_approved_users():
            online_user.speak(message, buffer="activity")
            online_user.play_sound("accountactionnotify.ogg")
            recipients += 1
        admin.speak_l("broadcast-sent", count=recipients, buffer="activity")
        self._show_admin_menu(admin)

    def _pretty_trust_level(self, trust_level: TrustLevel, locale: str) -> str:
        """Localized display name for a trust level."""
        key = {
            TrustLevel.BANNED: "trust-banned",
            TrustLevel.USER: "trust-user",
            TrustLevel.ADMIN: "trust-admin",
            TrustLevel.DEVELOPER: "trust-developer",
            TrustLevel.SERVER_OWNER: "trust-server-owner",
        }.get(trust_level)
        if key:
            return Localization.get(locale, key)
        return str(trust_level)

    async def _handle_lookup_user_editbox(
        self, admin: NetworkUser, text: str, state: dict
    ) -> None:
        """Show account details for the entered username."""
        username = (text or "").strip()
        if not username:
            admin.speak_l("user-not-found", player="", buffer="misc")
            self._show_admin_menu(admin)
            return

        record = self._db.get_user(username)
        online_user = self._users.get(username)
        if not record:
            admin.speak_l("user-not-found", player=username, buffer="misc")
            self._show_admin_menu(admin)
            return

        trust_name = self._pretty_trust_level(record.trust_level, admin.locale)
        yes = Localization.get(admin.locale, "confirm-yes")
        no = Localization.get(admin.locale, "confirm-no")
        online_text = yes if online_user else no
        approved_text = yes if record.approved else no
        banned_text = (
            yes if record.trust_level == TrustLevel.BANNED else no
        )

        lines = [
            Localization.get(admin.locale, "lookup-user-title", player=record.username),
            "",
            Localization.get(admin.locale, "lookup-user-trust", role=trust_name),
            Localization.get(admin.locale, "lookup-user-approved", state=approved_text),
            Localization.get(admin.locale, "lookup-user-online", state=online_text),
            Localization.get(admin.locale, "lookup-user-banned", state=banned_text),
        ]
        admin.show_menu(
            "lookup_user_result_menu",
            [MenuItem(text=line, id=f"line_{i}") for i, line in enumerate(lines)]
            + [MenuItem(text=Localization.get(admin.locale, "back"), id="back")],
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[admin.username] = {"menu": "lookup_user_result_menu"}

    async def _handle_ban_reason_editbox(self, admin: NetworkUser, text: str, state: dict) -> None:
        """Handle ban reason editbox submission."""
        target_username = state.get("target_username")
        broadcast_scope = state.get("broadcast_scope", "nobody")
        if not target_username:
            self._show_ban_user_menu(admin)
            return

        # Proceed with ban, passing the reason and broadcast scope
        await self._ban_user(admin, target_username, reason=text, broadcast_scope=broadcast_scope)

    async def _handle_unban_reason_editbox(
        self, admin: NetworkUser, text: str, state: dict
    ) -> None:
        """Handle unban reason editbox submission."""
        target_username = state.get("target_username")
        broadcast_scope = state.get("broadcast_scope", "nobody")
        if not target_username:
            self._show_unban_user_menu(admin)
            return

        # Proceed with unban, passing the reason and broadcast scope
        await self._unban_user(admin, target_username, reason=text, broadcast_scope=broadcast_scope)

    async def _handle_virtual_bots_selection(self, user: NetworkUser, selection_id: str) -> None:
        """Handle virtual bots menu selection."""
        if selection_id == "fill":
            await self._fill_virtual_bots(user)
        elif selection_id == "online":
            self._show_bring_online_bot_menu(user)
        elif selection_id == "offline":
            self._show_take_offline_bot_menu(user)
        elif selection_id == "clear":
            self._show_virtual_bots_clear_confirm_menu(user)
        elif selection_id == "status":
            await self._show_virtual_bots_status(user)
        elif selection_id == "guided":
            await self._show_virtual_bots_guided_overview(user)
        elif selection_id == "groups":
            await self._show_virtual_bots_groups_overview(user)
        elif selection_id == "profiles":
            await self._show_virtual_bots_profiles_overview(user)
        elif selection_id == "presence":
            await self._show_virtual_bots_presence_menu(user)
        elif selection_id == "add":
            self._show_add_bot_name_editbox(user)
        elif selection_id == "edit":
            self._show_edit_bot_menu(user)
        elif selection_id == "delete":
            self._show_delete_bot_menu(user)
        elif selection_id == "back":
            self._show_admin_menu(user)

    async def _handle_virtual_bots_clear_confirm_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle virtual bots clear confirmation menu selection."""
        if selection_id == "yes":
            await self._clear_virtual_bots(user)
        else:
            self._show_virtual_bots_menu(user)

    async def _handle_edit_bot_selection(self, user: NetworkUser, selection_id: str) -> None:
        """Handle edit bot menu selection."""
        if selection_id == "back":
            self._show_virtual_bots_menu(user)
        elif selection_id.startswith("edit_"):
            bot_name = selection_id[5:]
            self._show_edit_bot_actions_menu(user, bot_name)

    async def _handle_edit_bot_actions_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle edit bot actions menu selection."""
        bot_name = state.get("bot_name")
        if not bot_name:
            self._show_edit_bot_menu(user)
            return
        if selection_id == "rename":
            self._show_rename_bot_editbox(user, bot_name)
        elif selection_id == "profile":
            self._show_bot_profile_menu(user, bot_name)
        elif selection_id == "back":
            self._show_edit_bot_menu(user)

    async def _handle_bot_name_editbox(self, user: NetworkUser, text: str, state: dict) -> None:
        """Handle new virtual bot name submission."""
        error = self._validate_bot_name(text)
        if error:
            _speak_activity(user, error)
            self._show_add_bot_name_editbox(user)
            return
        await self._add_virtual_bot(user, text)

    async def _handle_rename_bot_editbox(
        self, user: NetworkUser, text: str, state: dict
    ) -> None:
        """Handle virtual bot rename submission."""
        bot_name = state.get("bot_name")
        if not bot_name:
            self._show_edit_bot_menu(user)
            return
        error = self._validate_bot_name(text, exclude=bot_name)
        if error:
            _speak_activity(user, error)
            self._show_rename_bot_editbox(user, bot_name)
            return
        await self._rename_virtual_bot(user, bot_name, text)

    async def _handle_bot_profile_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle bot profile selection."""
        bot_name = state.get("bot_name")
        if not bot_name:
            self._show_edit_bot_menu(user)
            return
        if selection_id == "back":
            self._show_edit_bot_actions_menu(user, bot_name)
            return
        await self._change_bot_profile(user, bot_name, selection_id)

    async def _handle_delete_bot_selection(self, user: NetworkUser, selection_id: str) -> None:
        """Handle delete bot menu selection."""
        if selection_id == "back":
            self._show_virtual_bots_menu(user)
        elif selection_id.startswith("del_"):
            bot_name = selection_id[4:]
            self._show_delete_bot_confirm_menu(user, bot_name)

    async def _handle_delete_bot_confirm_selection(
        self, user: NetworkUser, selection_id: str, state: dict
    ) -> None:
        """Handle delete bot confirmation menu selection."""
        bot_name = state.get("bot_name")
        if not bot_name:
            self._show_delete_bot_menu(user)
            return
        if selection_id == "yes":
            await self._delete_virtual_bot(user, bot_name)
        else:
            self._show_delete_bot_menu(user)

    async def _handle_bring_bot_online_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle bring bot online menu selection."""
        if selection_id == "back":
            self._show_virtual_bots_menu(user)
        elif selection_id.startswith("online_"):
            bot_name = selection_id[7:]  # Remove "online_" prefix
            await self._bring_one_bot_online(user, bot_name)

    async def _handle_take_bot_offline_selection(
        self, user: NetworkUser, selection_id: str
    ) -> None:
        """Handle take bot offline menu selection."""
        if selection_id == "back":
            self._show_virtual_bots_menu(user)
        elif selection_id.startswith("offline_"):
            bot_name = selection_id[8:]  # Remove "offline_" prefix
            await self._take_one_bot_offline(user, bot_name)

    # ==================== Admin Actions ====================

    @require_admin
    async def _approve_user(self, admin: NetworkUser, username: str) -> None:
        """Approve a pending user account."""
        if self._db.approve_user(username):
            _speak_activity(admin, "account-approved", player=username)

            # Notify other admins of the account action
            self._notify_admins(
                "account-action", "accountactionnotify.ogg", exclude_username=admin.username
            )

            # Check if the user is online and waiting for approval
            waiting_user = self._users.get(username)
            if waiting_user:
                # Update the user's approved status so they can now interact
                waiting_user.set_approved(True)

                # Broadcast online presence now that the user is approved
                self._broadcast_login_presence(waiting_user)

                waiting_state = self._user_states.get(username, {})
                if waiting_state.get("menu") == "main_menu":
                    # User is online and waiting - welcome them and show full main menu
                    _speak_activity(waiting_user, "account-approved-welcome")
                    waiting_user.play_sound("accountapprove.ogg")
                    self._show_main_menu(waiting_user)

        self._show_account_approval_menu(admin)

    @require_admin
    async def _reset_user_password(
        self, admin: NetworkUser, username: str, new_password: str
    ) -> None:
        """Reset a user's password to an admin-provided temporary value."""
        target_record = self._db.get_user(username)
        if not target_record or target_record.trust_level.value >= TrustLevel.ADMIN.value:
            _speak_activity(admin, "reset-user-password-unavailable", player=username)
            self._show_reset_password_user_menu(admin)
            return

        if self._auth.reset_password(username, new_password):
            _speak_activity(admin, "reset-user-password-done", player=username)
            target_user = self._users.get(username)
            if target_user:
                target_user.speak_l("your-password-was-reset", buffer="activity")
                for msg in target_user.get_queued_messages():
                    await target_user.connection.send(msg)
                await target_user.connection.send(
                    {
                        "type": "disconnect",
                        "reconnect": False,
                        "show_message": True,
                        "return_to_login": True,
                        "message": Localization.get(
                            target_user.locale, "your-password-was-reset"
                        ),
                    }
                )
        else:
            _speak_activity(admin, "reset-user-password-unavailable", player=username)

        self._show_reset_password_user_menu(admin)

    @require_admin
    async def _decline_user(self, admin: NetworkUser, username: str, reason: str = "") -> None:
        """Decline and delete a pending user account."""
        # Check if the user is online first
        waiting_user = self._users.get(username)

        if self._db.delete_user(username):
            _speak_activity(admin, "account-declined", player=username)

            # Notify other admins of the account action
            self._notify_admins(
                "account-action", "accountactionnotify.ogg", exclude_username=admin.username
            )

            # If user is online, disconnect them with the reason
            if waiting_user:
                # Build the full decline message with reason
                decline_message = Localization.get(waiting_user.locale, "account-declined-goodbye")
                display_reason = reason.strip() if reason else ""
                if not display_reason:
                    display_reason = Localization.get(
                        waiting_user.locale, "approval-reject-no-reason"
                    )
                # Combine into single message for the dialog
                full_message = f"{decline_message}\n{display_reason}"
                waiting_user.play_sound("accountdeny.ogg")
                waiting_user.speak(full_message, buffer="activity")
                # Flush queued messages before disconnect so client receives them
                for msg in waiting_user.get_queued_messages():
                    await waiting_user.connection.send(msg)
                await waiting_user.connection.send(
                    {
                        "type": "disconnect",
                        "reconnect": False,
                        "show_message": True,
                        "return_to_login": True,
                        "message": full_message,
                    }
                )

        self._show_account_approval_menu(admin)

    @require_developer
    async def _promote_to_admin(
        self, owner: NetworkUser, username: str, broadcast_scope: str
    ) -> None:
        """Promote a user to admin. Developers and server owners can do this."""
        # Update trust level in database
        self._db.update_user_trust_level(username, TrustLevel.ADMIN)

        # Update the user's trust level if they are online
        target_user = self._users.get(username)
        if target_user:
            target_user.set_trust_level(TrustLevel.ADMIN)

        # Always notify the target user with personalized message
        if target_user:
            _speak_activity(target_user, "promote-announcement-you")
            target_user.play_sound("accountpromoteadmin.ogg")

        # Broadcast the announcement to others based on scope
        if broadcast_scope == "nobody":
            # Silent mode - only notify the server owner who performed the action
            _speak_activity(owner, "promote-announcement", player=username)
            owner.play_sound("accountpromoteadmin.ogg")
        else:
            # Broadcast to all or admins (excluding the target user who already got personalized message)
            self._broadcast_admin_change(
                "promote-announcement",
                "accountpromoteadmin.ogg",
                username,
                broadcast_scope,
                exclude_username=username,
            )

        self._show_admin_menu(owner)

    @require_developer
    async def _demote_from_admin(
        self, owner: NetworkUser, username: str, broadcast_scope: str
    ) -> None:
        """Demote an admin to regular user. Developers and server owners can do this."""
        # Update trust level in database
        self._db.update_user_trust_level(username, TrustLevel.USER)

        # Update the user's trust level if they are online
        target_user = self._users.get(username)
        if target_user:
            target_user.set_trust_level(TrustLevel.USER)

        # Always notify the target user with personalized message
        if target_user:
            _speak_activity(target_user, "demote-announcement-you")
            target_user.play_sound("accountdemoteadmin.ogg")

        # Broadcast the announcement to others based on scope
        if broadcast_scope == "nobody":
            # Silent mode - only notify the server owner who performed the action
            _speak_activity(owner, "demote-announcement", player=username)
            owner.play_sound("accountdemoteadmin.ogg")
        else:
            # Broadcast to all or admins (excluding the target user who already got personalized message)
            self._broadcast_admin_change(
                "demote-announcement",
                "accountdemoteadmin.ogg",
                username,
                broadcast_scope,
                exclude_username=username,
            )

        self._show_admin_menu(owner)

    @require_server_owner
    async def _promote_to_developer(
        self, owner: NetworkUser, username: str, broadcast_scope: str
    ) -> None:
        """Promote an admin to developer. Only server owner can do this."""
        target_record = self._db.get_user(username)
        if not target_record or target_record.trust_level.value != TrustLevel.ADMIN.value:
            _speak_activity(owner, "promote-developer-unavailable", player=username)
            self._show_admin_menu(owner)
            return

        # Update trust level in database
        self._db.update_user_trust_level(username, TrustLevel.DEVELOPER)

        # Update the user's trust level if they are online
        target_user = self._users.get(username)
        if target_user:
            target_user.set_trust_level(TrustLevel.DEVELOPER)

        # Always notify the target user with personalized message
        if target_user:
            _speak_activity(target_user, "promote-developer-announcement-you")
            target_user.play_sound("accountpromoteadmin.ogg")

        # Broadcast the announcement to others based on scope
        if broadcast_scope == "nobody":
            # Silent mode - only notify the server owner who performed the action
            _speak_activity(owner, "promote-developer-announcement", player=username)
            owner.play_sound("accountpromoteadmin.ogg")
        else:
            # Broadcast to all or admins (excluding the target user who already got personalized message)
            self._broadcast_admin_change(
                "promote-developer-announcement",
                "accountpromoteadmin.ogg",
                username,
                broadcast_scope,
                exclude_username=username,
            )

        self._show_admin_menu(owner)

    @require_server_owner
    async def _demote_from_developer(
        self, owner: NetworkUser, username: str, broadcast_scope: str
    ) -> None:
        """Demote a developer to admin. Only server owner can do this."""
        target_record = self._db.get_user(username)
        if not target_record or target_record.trust_level.value != TrustLevel.DEVELOPER.value:
            _speak_activity(owner, "demote-developer-unavailable", player=username)
            self._show_admin_menu(owner)
            return

        # Update trust level in database
        self._db.update_user_trust_level(username, TrustLevel.ADMIN)

        # Update the user's trust level if they are online
        target_user = self._users.get(username)
        if target_user:
            target_user.set_trust_level(TrustLevel.ADMIN)

        # Always notify the target user with personalized message
        if target_user:
            _speak_activity(target_user, "demote-developer-announcement-you")
            target_user.play_sound("accountdemoteadmin.ogg")

        # Broadcast the announcement to others based on scope
        if broadcast_scope == "nobody":
            # Silent mode - only notify the server owner who performed the action
            _speak_activity(owner, "demote-developer-announcement", player=username)
            owner.play_sound("accountdemoteadmin.ogg")
        else:
            # Broadcast to all or admins (excluding the target user who already got personalized message)
            self._broadcast_admin_change(
                "demote-developer-announcement",
                "accountdemoteadmin.ogg",
                username,
                broadcast_scope,
                exclude_username=username,
            )

        self._show_admin_menu(owner)

    def _broadcast_admin_change(
        self,
        message_id: str,
        sound: str,
        player_name: str,
        broadcast_scope: str,
        exclude_username: str | None = None,
    ) -> None:
        """Broadcast an admin promotion/demotion announcement."""
        for username, user in self._users.items():
            if not user.approved:
                continue  # Don't send broadcasts to unapproved users
            if exclude_username and username == exclude_username:
                continue  # Skip the excluded user
            if broadcast_scope == "admins" and user.trust_level.value < TrustLevel.ADMIN.value:
                continue  # Only admins if broadcasting to admins only
            _speak_activity(user, message_id, player=player_name)
            user.play_sound(sound)

    @require_server_owner
    async def _transfer_ownership(
        self, owner: NetworkUser, username: str, broadcast_scope: str
    ) -> None:
        """Transfer server ownership to another admin. Only server owner can do this."""
        # Update new owner to SERVER_OWNER
        self._db.update_user_trust_level(username, TrustLevel.SERVER_OWNER)

        # Demote current owner to ADMIN
        self._db.update_user_trust_level(owner.username, TrustLevel.ADMIN)

        # Update the new owner's trust level if they are online
        target_user = self._users.get(username)
        if target_user:
            target_user.set_trust_level(TrustLevel.SERVER_OWNER)

        # Update current owner's trust level
        owner.set_trust_level(TrustLevel.ADMIN)

        # Always notify the target user with personalized message
        if target_user:
            _speak_activity(target_user, "transfer-ownership-announcement-you")
            target_user.play_sound("accounttransferownership.ogg")

        # Broadcast the announcement to others based on scope
        if broadcast_scope == "nobody":
            # Silent mode - only notify the former owner who performed the action
            _speak_activity(owner, "transfer-ownership-announcement", player=username)
            owner.play_sound("accounttransferownership.ogg")
        else:
            # Broadcast to all or admins (excluding the target user who already got personalized message)
            self._broadcast_admin_change(
                "transfer-ownership-announcement",
                "accounttransferownership.ogg",
                username,
                broadcast_scope,
                exclude_username=username,
            )

        self._show_admin_menu(owner)

    @require_admin
    async def _ban_user(
        self, admin: NetworkUser, username: str, reason: str = "", broadcast_scope: str = "nobody"
    ) -> None:
        """Ban a user. Admins and server owner can do this."""
        # Check if the user is online first
        target_user = self._users.get(username)

        # Update trust level in database to BANNED
        self._db.update_user_trust_level(username, TrustLevel.BANNED)

        # Broadcast the ban announcement based on scope
        if broadcast_scope == "nobody":
            # Silent mode - only notify the admin who performed the action
            _speak_activity(admin, "user-banned", player=username)
            admin.play_sound("accountban.ogg")
        else:
            # Broadcast to all or admins
            self._broadcast_admin_change(
                "user-banned",
                "accountban.ogg",
                username,
                broadcast_scope,
            )

        # If user is online, disconnect them with the reason
        if target_user:
            # Update the user's trust level
            target_user.set_trust_level(TrustLevel.BANNED)

            # Build the full ban message with reason
            ban_message = Localization.get(target_user.locale, "you-have-been-banned")
            display_reason = reason.strip() if reason else ""
            if not display_reason:
                display_reason = Localization.get(target_user.locale, "ban-no-reason")
            # Combine into single message for the dialog
            full_message = f"{ban_message}\n{display_reason}"
            target_user.play_sound("accountban.ogg")
            target_user.speak(full_message, buffer="activity")
            # Flush queued messages before disconnect so client receives them
            for msg in target_user.get_queued_messages():
                await target_user.connection.send(msg)
            await target_user.connection.send(
                {
                    "type": "disconnect",
                    "reconnect": False,
                    "show_message": True,
                    "message": full_message,
                }
            )

        self._show_ban_user_menu(admin)

    @require_admin
    async def _unban_user(
        self, admin: NetworkUser, username: str, reason: str = "", broadcast_scope: str = "nobody"
    ) -> None:
        """Unban a user. Admins and server owner can do this."""
        # Update trust level in database to USER
        self._db.update_user_trust_level(username, TrustLevel.USER)

        # Also set approved to True when unbanning
        self._db.approve_user(username)

        # Broadcast the unban announcement based on scope
        if broadcast_scope == "nobody":
            # Silent mode - only notify the admin who performed the action
            _speak_activity(admin, "user-unbanned", player=username)
            admin.play_sound("accountapprove.ogg")
        else:
            # Broadcast to all or admins
            self._broadcast_admin_change(
                "user-unbanned",
                "accountapprove.ogg",
                username,
                broadcast_scope,
            )

        self._show_unban_user_menu(admin)

    @require_admin
    async def _reboot_server(self, admin: NetworkUser) -> None:
        """Warn all players, then reboot the server (git pull + restart).

        Wraps :meth:`_execute_reboot` to surface helper-launch failures back to
        the requesting admin. See :meth:`_execute_reboot` for details of the
        reboot sequence itself.
        """
        try:
            await self._execute_reboot()
        except Exception as exc:  # noqa: BLE001 - helper spawn failure
            LOG.warning("Failed to launch server reboot helper: %s", exc)
            _speak_activity(admin, "server-reboot-failed")
            self._show_admin_menu(admin)

    async def _execute_reboot(self) -> None:
        """Warn all players, then reboot the server (git pull + restart).

        Players receive a countdown warning, then are disconnected with an
        auto-reconnect request before the server shuts down gracefully. A
        detached helper (spawned via ``systemd-run``) waits for the server
        process to exit, pulls the latest code, and restarts the service.
        Absolutely requires the helper to launch successfully; otherwise a
        :class:`RuntimeError` is raised and the server keeps running (callers
        decide whether to surface a failure to a user or keep a scheduled
        action eligible for retry).

        Raises:
            RuntimeError: If the deploy helper cannot be launched.
        """
        reboot_seconds = 10
        retry_after = 15

        # 1) Warn all online approved players (virtual bots have no connection to push to)
        for username, user in self._users.items():
            if not user.approved or getattr(user, "is_virtual_bot", False):
                continue
            _speak_activity(user, "server-reboot-warning", seconds=reboot_seconds)
            user.play_sound("accountactionnotify.ogg")

        await asyncio.sleep(reboot_seconds)

        # 2) Launch the detached deploy helper; abort quietly if it cannot spawn
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemd-run",
                "--user",
                "--collect",
                "--unit=playpalace-deploy",
                str(_RESTART_SCRIPT),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            rc = await asyncio.wait_for(proc.wait(), timeout=15)
            if rc != 0:
                raise RuntimeError(f"systemd-run exited with code {rc}")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Failed to launch server reboot helper") from exc

        # 3) Disconnect all clients with an auto-reconnect request (bots excluded)
        for username, user in list(self._users.items()):
            if not user.approved or getattr(user, "is_virtual_bot", False):
                continue
            for msg in user.get_queued_messages():
                await user.connection.send(msg)
            await user.connection.send(
                {
                    "type": "disconnect",
                    "reconnect": True,
                    "retry_after": retry_after,
                    "message": Localization.get(user.locale, "server-restarting"),
                }
            )

        # 4) Graceful shutdown; run_server loop breaks, server.stop() saves state
        self.request_shutdown()

    # ==================== Virtual Bot Actions ====================

    def _validate_bot_name(self, name: str, exclude: str | None = None) -> str | None:
        """Validate a virtual bot name.

        Returns an error message id, or None if the name is acceptable.
        """
        name = name.strip()
        if not name:
            return "virtual-bots-name-invalid"
        if not (self._username_min_length <= len(name) <= self._username_max_length):
            return "virtual-bots-name-invalid"
        manager = getattr(self, "_virtual_bots", None)
        if manager and manager.is_roster_name(name):
            if not (exclude and exclude.lower() == name.lower()):
                return "virtual-bots-name-taken"
        for username in self._users:
            if username.lower() == name.lower():
                if not (exclude and exclude.lower() == name.lower()):
                    return "virtual-bots-name-taken"
        return None

    @require_developer
    async def _add_virtual_bot(self, owner: NetworkUser, name: str) -> None:
        """Add a new virtual bot and bring it online."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(owner, "virtual-bots-not-available")
            self._show_virtual_bots_menu(owner)
            return
        name = name.strip()
        if not manager.add_bot(name):
            _speak_activity(owner, "virtual-bots-name-taken")
            self._show_add_bot_name_editbox(owner)
            return
        manager.save_state()
        _speak_activity(owner, "virtual-bots-added", name=name)
        self._show_virtual_bots_menu(owner)

    @require_developer
    async def _rename_virtual_bot(self, owner: NetworkUser, old_name: str, new_name: str) -> None:
        """Rename a virtual bot, preserving its profile and online status."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(owner, "virtual-bots-not-available")
            self._show_virtual_bots_menu(owner)
            return
        new_name = new_name.strip()
        if old_name.lower() == new_name.lower():
            self._show_edit_bot_actions_menu(owner, old_name)
            return
        if not manager.rename_bot(old_name, new_name):
            _speak_activity(owner, "virtual-bots-name-taken")
            self._show_rename_bot_editbox(owner, old_name)
            return
        manager.save_state()
        _speak_activity(owner, "virtual-bots-renamed", old_name=old_name, new_name=new_name)
        self._show_edit_bot_menu(owner)

    @require_developer
    async def _change_bot_profile(self, owner: NetworkUser, bot_name: str, profile: str) -> None:
        """Change a virtual bot's profile."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(owner, "virtual-bots-not-available")
            self._show_virtual_bots_menu(owner)
            return
        if not manager.set_bot_profile(bot_name, profile):
            _speak_activity(owner, "virtual-bots-no-profiles")
            self._show_edit_bot_actions_menu(owner, bot_name)
            return
        _speak_activity(owner, "virtual-bots-profile-changed", name=bot_name, profile=profile)
        self._show_edit_bot_actions_menu(owner, bot_name)

    @require_developer
    async def _delete_virtual_bot(self, owner: NetworkUser, bot_name: str) -> None:
        """Delete a virtual bot, killing any table it is in."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(owner, "virtual-bots-not-available")
            self._show_virtual_bots_menu(owner)
            return
        removed, tables_killed = manager.remove_bot(bot_name)
        if not removed:
            _speak_activity(owner, "virtual-bots-no-bots")
            self._show_delete_bot_menu(owner)
            return
        _speak_activity(owner, "virtual-bots-deleted", name=bot_name, tables=tables_killed)
        self._show_delete_bot_menu(owner)

    @require_developer
    async def _fill_virtual_bots(self, owner: NetworkUser) -> None:
        """Fill the server with virtual bots from config."""
        if Localization.is_warmup_active():
            owner.speak_l("virtual-bots-fill-localization-in-progress", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return
        if not hasattr(self, "_virtual_bots") or not self._virtual_bots:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return

        added, online = self._virtual_bots.fill_server()
        if added > 0:
            owner.speak_l("virtual-bots-filled", added=added, online=online, buffer="misc")
            # Save state after filling
            self._virtual_bots.save_state()
        else:
            owner.speak_l("virtual-bots-already-filled", buffer="misc")

        self._show_virtual_bots_menu(owner)

    @require_developer
    async def _bring_one_bot_online(self, owner: NetworkUser, bot_name: str) -> None:
        """Bring a single virtual bot online."""
        if Localization.is_warmup_active():
            owner.speak_l("virtual-bots-fill-localization-in-progress", buffer="misc")
            self._show_bring_online_bot_menu(owner)
            return
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return
        if not manager.bring_bot_online(bot_name):
            owner.speak_l("virtual-bots-already-online", name=bot_name, buffer="misc")
            self._show_bring_online_bot_menu(owner)
            return
        manager.save_state()
        owner.speak_l("virtual-bots-brought-online", name=bot_name, buffer="misc")
        self._show_bring_online_bot_menu(owner)

    @require_developer
    async def _take_one_bot_offline(self, owner: NetworkUser, bot_name: str) -> None:
        """Take a single virtual bot offline."""
        if Localization.is_warmup_active():
            owner.speak_l("virtual-bots-fill-localization-in-progress", buffer="misc")
            self._show_take_offline_bot_menu(owner)
            return
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return
        if not manager.take_bot_offline(bot_name):
            owner.speak_l("virtual-bots-already-offline", name=bot_name, buffer="misc")
            self._show_take_offline_bot_menu(owner)
            return
        manager.save_state()
        owner.speak_l("virtual-bots-taken-offline", name=bot_name, buffer="misc")
        self._show_take_offline_bot_menu(owner)

    @require_developer
    async def _clear_virtual_bots(self, owner: NetworkUser) -> None:
        """Clear all virtual bots from the server."""
        if not hasattr(self, "_virtual_bots") or not self._virtual_bots:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return

        bots_cleared, tables_killed = self._virtual_bots.clear_bots()
        if bots_cleared > 0:
            owner.speak_l(
                "virtual-bots-cleared",
                bots=bots_cleared,
                tables=tables_killed,
                buffer="misc",
            )
        else:
            owner.speak_l("virtual-bots-none-to-clear", buffer="misc")

        self._show_virtual_bots_menu(owner)

    @require_developer
    async def _show_virtual_bots_status(self, owner: NetworkUser) -> None:
        """Show virtual bots status."""
        if not hasattr(self, "_virtual_bots") or not self._virtual_bots:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return

        status = self._virtual_bots.get_status()
        owner.speak_l(
            "virtual-bots-status-report",
            total=status["total"],
            online=status["online"],
            offline=status["offline"],
            in_game=status["in_game"],
            buffer="misc",
        )
        self._show_virtual_bots_menu(owner)

    @require_developer
    async def _show_virtual_bots_presence_menu(self, owner: NetworkUser) -> None:
        """Show the bot presence tuning menu (server-side, opt-in per profile)."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return

        status = manager.presence_status()
        locale = owner.locale
        kill_label = Localization.get(locale, "virtual-bots-presence-resume")
        if status["kill_switch"]:
            kill_label = Localization.get(locale, "virtual-bots-presence-pause")
        owner.speak_l(
            "virtual-bots-presence-report",
            enabled=status["enabled"],
            kill_switch=status["kill_switch"],
            in_quiet_hours=status["in_quiet_hours"],
            chats_sent=status["chats_sent"],
            chats_blocked=status["chats_blocked"],
            buffer="misc",
        )
        items = [
            MenuItem(
                text=Localization.get(locale, "virtual-bots-presence-status"),
                id="status",
            ),
            MenuItem(
                text=Localization.get(locale, "virtual-bots-presence-enable"),
                id="enable",
            ),
            MenuItem(
                text=Localization.get(locale, "virtual-bots-presence-disable"),
                id="disable",
            ),
            MenuItem(
                text=kill_label,
                id="kill_switch",
            ),
            MenuItem(
                text=Localization.get(locale, "virtual-bots-presence-profiles"),
                id="profiles",
            ),
            MenuItem(text=Localization.get(locale, "back"), id="back"),
        ]
        owner.show_menu(
            "virtual_bots_presence_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[owner.username] = {"menu": "virtual_bots_presence_menu"}

    @require_developer
    async def _show_virtual_bots_presence_profiles_menu(self, owner: NetworkUser) -> None:
        """Show per-profile presence toggle menu."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_presence_menu(owner)
            return
        profiles = manager.get_profiles()
        if not profiles:
            owner.speak_l("virtual-bots-no-profiles", buffer="misc")
            self._show_virtual_bots_presence_menu(owner)
            return
        locale = owner.locale
        items = [
            MenuItem(text=profile, id=f"profile_{profile}") for profile in profiles
        ]
        items.append(MenuItem(text=Localization.get(locale, "back"), id="back"))
        owner.show_menu(
            "virtual_bots_presence_profiles_menu",
            items,
            multiletter=True,
            escape_behavior=EscapeBehavior.SELECT_LAST,
        )
        self._user_states[owner.username] = {"menu": "virtual_bots_presence_profiles_menu"}

    @require_developer
    async def _handle_virtual_bots_presence_selection(
        self, owner: NetworkUser, selection_id: str
    ) -> None:
        """Handle virtual bots presence menu selection."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return

        if selection_id == "status":
            await self._show_virtual_bots_presence_menu(owner)
        elif selection_id == "enable":
            manager.set_presence_enabled(True)
            manager.save_state()
            owner.speak_l("virtual-bots-presence-enabled", buffer="misc")
            await self._show_virtual_bots_presence_menu(owner)
        elif selection_id == "disable":
            manager.set_presence_enabled(False)
            manager.save_state()
            owner.speak_l("virtual-bots-presence-disabled", buffer="misc")
            await self._show_virtual_bots_presence_menu(owner)
        elif selection_id == "kill_switch":
            manager.set_presence_kill_switch(not manager.presence_status()["kill_switch"])
            status = manager.presence_status()
            if status["kill_switch"]:
                owner.speak_l("virtual-bots-presence-paused", buffer="misc")
            else:
                owner.speak_l("virtual-bots-presence-resumed", buffer="misc")
            await self._show_virtual_bots_presence_menu(owner)
        elif selection_id == "profiles":
            await self._show_virtual_bots_presence_profiles_menu(owner)
        else:
            self._show_virtual_bots_menu(owner)

    @require_developer
    async def _handle_virtual_bots_presence_profile_selection(
        self, owner: NetworkUser, selection_id: str
    ) -> None:
        """Toggle presence for a single profile (opt-in)."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            owner.speak_l("virtual-bots-not-available", buffer="misc")
            self._show_virtual_bots_menu(owner)
            return
        if selection_id == "back":
            await self._show_virtual_bots_presence_menu(owner)
            return
        if selection_id.startswith("profile_"):
            profile = selection_id[8:]
            new_value = not manager.profile_presence_enabled(profile)
            manager.set_profile_presence(profile, new_value)
            manager.save_state()
            key = "virtual-bots-presence-profile-enabled" if new_value else "virtual-bots-presence-profile-disabled"
            owner.speak_l(key, profile=profile, buffer="misc")
        await self._show_virtual_bots_presence_profiles_menu(owner)

    @require_developer
    async def _show_virtual_bots_guided_overview(self, owner: NetworkUser) -> None:
        """Show guided table overview."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(owner, "virtual-bots-not-available")
            self._show_virtual_bots_menu(owner)
            return

        snapshot = manager.get_admin_snapshot()
        locale = owner.locale
        config = snapshot["config"]
        lines = [
            Localization.get(
                locale,
                "virtual-bots-guided-header",
                count=len(snapshot["guided_tables"]),
                allocation=config["allocation_mode"],
                fallback=config["fallback_behavior"],
                default_profile=config["default_profile"],
            )
        ]
        tables = snapshot["guided_tables"]
        if not tables:
            lines.append(Localization.get(locale, "virtual-bots-guided-empty"))
        else:
            status_keys = {
                True: "virtual-bots-guided-status-active",
                False: "virtual-bots-guided-status-inactive",
            }
            table_state_keys = {
                "linked": "virtual-bots-guided-table-linked",
                "stale": "virtual-bots-guided-table-stale",
                "unassigned": "virtual-bots-guided-table-unassigned",
            }
            for entry in tables:
                status_text = Localization.get(locale, status_keys[entry["active"]])
                table_state_text = Localization.get(
                    locale,
                    table_state_keys[entry["table_state"]],
                    table_id=entry["table_id"] or "-",
                    host=entry.get("host") or "-",
                    players=entry.get("total_players", 0),
                    humans=entry.get("human_players", 0),
                )
                if entry["ticks_until_next_change"] is None:
                    next_change_text = Localization.get(locale, "virtual-bots-guided-no-schedule")
                else:
                    next_change_text = Localization.get(
                        locale,
                        "virtual-bots-guided-next-change",
                        ticks=entry["ticks_until_next_change"],
                    )
                warning_text = (
                    Localization.get(locale, "virtual-bots-guided-warning")
                    if entry["warning"]
                    else ""
                )
                groups = entry["bot_groups"]
                groups_text = (
                    Localization.format_list_and(locale, groups)
                    if groups
                    else Localization.get(locale, "virtual-bots-groups-no-rules")
                )
                profile_text = (
                    entry["profile"]
                    if entry["profile"]
                    else Localization.get(locale, "virtual-bots-profile-inherit-default")
                )
                max_label = entry["max_bots"] if entry["max_bots"] is not None else "∞"
                lines.append(
                    Localization.get(
                        locale,
                        "virtual-bots-guided-line",
                        table=entry["name"],
                        game=entry["game"],
                        priority=entry["priority"],
                        assigned=entry["assigned_bots"],
                        min_bots=entry["min_bots"],
                        max_bots=max_label,
                        waiting=entry["waiting_bots"],
                        unavailable=entry["unavailable_bots"],
                        status=status_text,
                        profile=profile_text,
                        groups=groups_text,
                        table_state=table_state_text,
                        next_change=next_change_text,
                        warning_text=warning_text,
                    )
                )

        owner.speak("\n".join(lines), buffer="misc")
        self._show_virtual_bots_menu(owner)

    @require_developer
    async def _show_virtual_bots_groups_overview(self, owner: NetworkUser) -> None:
        """Show bot group inventory."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(owner, "virtual-bots-not-available")
            self._show_virtual_bots_menu(owner)
            return

        snapshot = manager.get_admin_snapshot()
        groups = snapshot["groups"]
        locale = owner.locale
        lines = [
            Localization.get(
                locale,
                "virtual-bots-groups-header",
                count=len(groups),
                bots=snapshot["config"]["configured_bots"],
            )
        ]
        if not groups:
            lines.append(Localization.get(locale, "virtual-bots-groups-empty"))
        else:
            for entry in groups:
                counts = entry["counts"]
                profile_text = (
                    entry["profile"]
                    if entry["profile"]
                    else Localization.get(locale, "virtual-bots-no-profile")
                )
                rules_text = (
                    Localization.format_list_and(locale, entry["assigned_rules"])
                    if entry["assigned_rules"]
                    else Localization.get(locale, "virtual-bots-groups-no-rules")
                )
                lines.append(
                    Localization.get(
                        locale,
                        "virtual-bots-groups-line",
                        group=entry["name"],
                        profile=profile_text,
                        total=counts["total"],
                        online=counts["online"],
                        waiting=counts["waiting"],
                        in_game=counts["in_game"],
                        offline=counts["offline"],
                        rules=rules_text,
                    )
                )

        owner.speak("\n".join(lines), buffer="misc")
        self._show_virtual_bots_menu(owner)

    @require_developer
    async def _show_virtual_bots_profiles_overview(self, owner: NetworkUser) -> None:
        """Show profile override summary."""
        manager = getattr(self, "_virtual_bots", None)
        if not manager:
            _speak_activity(owner, "virtual-bots-not-available")
            self._show_virtual_bots_menu(owner)
            return

        snapshot = manager.get_admin_snapshot()
        profiles = snapshot["profiles"]
        locale = owner.locale
        lines = [
            Localization.get(
                locale,
                "virtual-bots-profiles-header",
                count=len(profiles),
                default_profile=snapshot["config"]["default_profile"],
            )
        ]
        if not profiles:
            lines.append(Localization.get(locale, "virtual-bots-profiles-empty"))
        else:
            for entry in profiles:
                overrides = entry["overrides"]
                if overrides:
                    formatted = ", ".join(f"{key}={value}" for key, value in overrides.items())
                else:
                    formatted = Localization.get(locale, "virtual-bots-profiles-no-overrides")
                lines.append(
                    Localization.get(
                        locale,
                        "virtual-bots-profiles-line",
                        profile=entry["name"],
                        bot_count=entry["bot_count"],
                        overrides=formatted,
                    )
                )

        owner.speak("\n".join(lines), buffer="misc")
        self._show_virtual_bots_menu(owner)
