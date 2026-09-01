# Server Changelog

This document records changes to the PlayPalace server. New entries are added at the top under the date the change ships.

## 2026-08-31

- Admins can now **Freeze the server** from the admin menu (with a confirmation prompt). While frozen, regular players stay connected but can't do anything — menu selections, chat, editbox inputs, keybinds, and in-game actions are all blocked, and any in-progress game pauses mid-turn. Admins, developers, and the server owner are unaffected and can unfreeze instantly from the same admin menu item (which flips to "Unfreeze server"). Everyone gets a localized "server frozen / unfrozen" announcement with a sound, and a frozen player who tries to act sees a brief "server is frozen" notice. The freeze state is in-memory only, so a server restart automatically unfreezes.

## 2026-08-30

- Added account-level online and offline sound preferences. Users can now pick the sound played when they log in and when they log out from a small built-in menu (Default, Chime, Alert) in the existing Sounds preferences category; the option is server-side only and needs no client changes. The previous role-based distinction (admins vs non-admins getting distinct audio) is preserved unless the user overrides it.

- Added two owner/developer server-management features, both driven from in-game menus (no client changes):
  - **Reload Caches** (developer): force-reloads localization and documents from disk, rebuilding locale bundles from source and re-scanning documents without a server restart.
  - **Scheduled Actions** (server owner): schedules one-shot or recurring reboots and broadcast announcements, persisted in the database so they survive restarts. A background scheduler executes due actions; scheduled reboots disconnect virtual bots first, matching the manual reboot flow.

- Added four new server-side admin actions, all built as in-game menus (no client changes, no new packet types):
  - **Server Status** (admin): a read-only snapshot showing uptime, tick number, online/approved users, open tables, registered users, and the virtual-bot roster — so admins can gauge server health without leaving the game.
  - **Kick User** (admin): immediately disconnect a single online player without banning them (handy for stuck or AFK clients). You can't kick yourself or anyone of equal/higher rank, and it asks for confirmation first.
  - **Broadcast Announcement** (developer): send a custom server-wide message with a chime to every approved online user — e.g. "restart in 10 minutes".
  - **Look Up User** (developer): search any account and see its role, approval status, whether it's online, and whether it's banned.
- Rebooting the server now protects connected virtual bots. If any bots are online when an admin confirms a reboot, an extra confirmation appears showing how many bots are connected and warning that they'll be disconnected. Choosing yes disconnects all bots immediately (raising any bot table and taking the bots offline, while keeping the roster intact) before the reboot proceeds; choosing no cancels. If no bots are connected, the extra prompt never appears.

## 2026-08-30 (earlier)

- Server startup is much faster: locale bundles are now **cached in compiled form** (the generated Python code objects), so subsequent restarts load all languages in under a second instead of recompiling every `.ftl` file from scratch. The cache is per-locale and version-aware — a changed translation, a new language, a Python upgrade, or a `fluent-compiler` upgrade only triggers a one-time recompile for what actually changed, and anything missing or corrupt falls back to the normal compile path automatically. The existing cache can still be disabled with `PLAYPALACE_DISABLE_LOCALE_CACHE=true`.

## 2026-08-30 (earlier)

- Fixed the game categories menu showing broken labels like `[dice]` and `[poker]` for Battle, Bunko, Citadels, Color Game, Dead Man's Deck, Dead Man's Poker, and Tien Len. These games now use the same localized category identifiers as every other game, so the menu is fully translated again and the error log stops filling with localization KeyErrors.
- Added a server-side **bot presence & chat** system for virtual bots. When enabled, virtual bots emit real chat lines (greetings, in-game banter, "gg" after games, idle chatter) through the existing chat packet, plus more human-like session cadence (burst logins, AFK stretches, hesitation before actions). It is fully **opt-in per profile** — existing bots behave exactly as before until a profile opts in via the admin menu (Virtual Bots → Presence & Chat) or `config.toml`. Guardrails include a persisted kill switch, per-bot hourly and global per-minute chat caps, a minimum gap between bot messages, and quiet hours. All of it is server-side: no client changes and no new packet types.

## 2026-08-29

- Developers and the server owner can now take a **specific virtual bot offline** from the admin menu (Virtual Bots → Take Bot Offline). The bot leaves any table it is in and its departure is announced to everyone, mirroring the existing "Bring Bot Online" action.
- Creating or joining a **Cards Against Humanity** table now shows a mature-content notice first, warning that the game contains highly immature content and is not recommended for players under 16 or those sensitive to certain topics. Players can choose **Keep playing** to proceed with the create/join or **Go back** to return to the previous menu.
- The **"Fill Server"** virtual-bot action is now blocked while localization is still compiling, with the message "While localization is in progress, you cannot bring bots online."
- Developers and the server owner can now bring a **specific virtual bot** online from the admin menu (Virtual Bots → Bring Bot Online), instead of only filling the whole server at once.
- Developers and the server owner can now **add, edit, and delete virtual bots** from the admin menu (Virtual Bots → Add/Edit/Delete Virtual Bot). Adding a bot brings it online immediately, editing can rename the bot or change its profile, and deleting removes it permanently (closing any table it is in). Changes persist across server restarts.
- Added a new **Developer** role. Developers have the full permissions of the server owner, except they cannot change the server owner (transfer ownership stays owner-only). Owners can promote an admin to developer and demote a developer back in-game. When a developer comes online, players are told "User is a developer of PlayPalace."
- Added an in-game **"Reboot server"** admin action. It warns all players, then stops the server, pulls the latest code, and restarts it. Clients automatically reconnect.
- Added a **"Random" team option** to Mile by Mile. The server picks team sizes from the player count and randomly assigns players at the start of the game.
- Documented the deployment workflow: agents push changes to the fork, and an admin triggers the reboot to deploy them.
- Hardened the localization bundle cache against interrupted compiles (stale temp files are swept, atomic writes prevent corruption).
