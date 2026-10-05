# Server Changelog

This document records changes to the PlayPalace server. New entries are added at the top under the date the change ships.

## 2026-10-04

- Added **voice chat** to the web client, so browser players can talk to each other and to desktop players in the same room. The **Join voice** button sits under the volume sliders, alongside a **Mute mic** toggle, **microphone** and **speaker** pickers, a **Transmit** mode picker (**Voice activation** or **Push to talk**, with a hold-to-talk button), and **mic gain**, **sensitivity**, **hold open**, and **voice volume** sliders. Audio is the same 16kHz mono PCM in 20ms frames the desktop client already sends, so no server changes were needed and the two clients interoperate in the same rooms. Settings are remembered between visits, and the status line announces the room, who else is in it, and whether you are talking or muted. Capture and playback run in an AudioWorklet off the main thread, so talking never stutters the interface; browsers without one fall back automatically.

- Added **voice chat** to the desktop client. A **Join Voice** button beside the menu flips to **Unjoin Voice** once you're in, and the voice panel adds a microphone-gain slider (0–200%), a voice-activation sensitivity slider, a transmit-mode picker (**Voice activation** or **Push to talk**), and a mute toggle, with a status line that announces when the microphone is live and who else is in the room. Audio runs as 16kHz mono PCM over the existing websocket in 20ms frames, relayed by the server and played back per speaker. Rooms mirror chat: you hear everyone seated at your table, and everyone not at a table shares a lobby room; moving between a table and the lobby moves you to the matching room automatically. Voice is **never recorded or stored** — frames are relayed and discarded, nothing touches disk, and there is no moderator playback. Everyone can still be muted locally, the server drops audio from anyone who hasn't joined or is muted, and frame-rate and bandwidth limits protect the connection. The Audio tab of the client options dialog gained **voice input and output device pickers** (microphone and speakers, defaulting to whatever PlayPalace's own sounds are using), plus voice volume, mic gain, transmit mode, and voice-activation sensitivity.

- Fixed two hangs in **Aircraft Extreme** that could leave a table stuck forever. A downed bot could no longer take any action, and the turn-advance safety net deliberately skipped downed bots, so a bot shot down mid-turn could never respawn and the game froze. Separately, a refused action (firing with no target in range, firing from your own runway, or flying with a dead engine or into a blocked square) spoke its reason but neither spent the action nor advanced the turn, so a bot that kept trying the same impossible move looped indefinitely. Refused actions now consume the action and end the turn, so bot games always reach a result.

## 2026-09-30

- New board game: **Aircraft Extreme** (2–4 pilots). Fly from your corner runway across a 6x6 storm-filled sky, bank laps by touching the opposite corner, and dogfight along the way. Two actions per turn: flying costs 1 engine power, cannons hit at 2 squares (orthogonal or diagonal), and barrel rolls, climbs, and cloud dives cover the classic aerial moves. Thunderstorms strike planes that stray near the storm block. First pilot to fly the set number of laps home wins — or be the last plane still flying. Shot-down pilots respawn on their runway (three downs and you're out). Option-configurable: laps to win, storm damage, plane health, and respawn health. Ships with laps leaderboards and full screen-reader navigation using the sky grid.

## 2026-09-05

- In Monopoly, when a player begins a two-way trade with another player (the moment they pick who they're trading with), the whole table is now told "**{player} has started a trade with {target}**" so nobody mistakes a silent trade draft for the player going idle. Re-picking the same target without clearing the draft doesn't repeat the notice, and if the player cancels the draft after choosing a target, the table hears that they **stopped working on a trade**.

## 2026-09-04

- All approved players now have an **"Online users"** entry in the main lobby menu. Selecting it opens a read-only list of everyone currently online, showing how long each user has been connected, what they're doing (game or not), their language, and which client they're using — **Desktop** or **Web** (plus the platform, e.g. Windows or a browser). Previously this list was only reachable through the undocumented Shift+F2 shortcut; the shortcut still works, including while sitting at a table.

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
