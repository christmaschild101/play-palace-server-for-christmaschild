# Server Changelog

This document records changes to the PlayPalace server. New entries are added at the top under the date the change ships.

## 2026-08-29

- Added a new **Developer** role. Developers have the full permissions of the server owner, except they cannot change the server owner (transfer ownership stays owner-only). Owners can promote an admin to developer and demote a developer back in-game. When a developer comes online, players are told "User is a developer of PlayPalace."
- Added an in-game **"Reboot server"** admin action. It warns all players, then stops the server, pulls the latest code, and restarts it. Clients automatically reconnect.
- Added a **"Random" team option** to Mile by Mile. The server picks team sizes from the player count and randomly assigns players at the start of the game.
- Documented the deployment workflow: agents push changes to the fork, and an admin triggers the reboot to deploy them.
- Hardened the localization bundle cache against interrupted compiles (stale temp files are swept, atomic writes prevent corruption).
