# Server Changelog

This document records changes to the PlayPalace server. New entries are added at the top under the date the change ships.

## 2026-08-29

- Creating or joining a **Cards Against Humanity** table now shows a mature-content notice first, warning that the game contains highly immature content and is not recommended for players under 16 or those sensitive to certain topics. Players can choose **Keep playing** to proceed with the create/join or **Go back** to return to the previous menu.
- The **"Fill Server"** virtual-bot action is now blocked while localization is still compiling, with the message "While localization is in progress, you cannot bring bots online."
- Developers and the server owner can now bring a **specific virtual bot** online from the admin menu (Virtual Bots → Bring Bot Online), instead of only filling the whole server at once.
- Developers and the server owner can now **add, edit, and delete virtual bots** from the admin menu (Virtual Bots → Add/Edit/Delete Virtual Bot). Adding a bot brings it online immediately, editing can rename the bot or change its profile, and deleting removes it permanently (closing any table it is in). Changes persist across server restarts.
- Added a new **Developer** role. Developers have the full permissions of the server owner, except they cannot change the server owner (transfer ownership stays owner-only). Owners can promote an admin to developer and demote a developer back in-game. When a developer comes online, players are told "User is a developer of PlayPalace."
- Added an in-game **"Reboot server"** admin action. It warns all players, then stops the server, pulls the latest code, and restarts it. Clients automatically reconnect.
- Added a **"Random" team option** to Mile by Mile. The server picks team sizes from the player count and randomly assigns players at the start of the game.
- Documented the deployment workflow: agents push changes to the fork, and an admin triggers the reboot to deploy them.
- Hardened the localization bundle cache against interrupted compiles (stale temp files are swept, atomic writes prevent corruption).
