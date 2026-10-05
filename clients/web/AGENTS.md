# Web Client Notes

## Scope
- This folder contains the browser client for PlayPalace v11.
- Keep changes focused and aligned with server packet behavior.

## Versioning
- `version.js` is the single source of truth for web client version.
- Increment `window.PLAYPALACE_WEB_VERSION` on every commit in this branch.
- Format is `YYYY.MM.DD.N`.
- `N` is monotonic and should not reset when the date changes (example: after `2026.02.08.32`, use `2026.02.09.33`).
- `index.html` uses that value for `app.js?v=...` cache busting and footer display.

## Deployment Config
- Deployment-specific settings belong in `config.js` (copied from `config.sample.js`).
- Do not put maintainer-only values (like app version) in deployment config.

## Packet Schema Sync
- Keep `clients/web/packet_schema.json` in sync with `clients/desktop/packet_schema.json`.
- After packet model changes, regenerate schema from `server/tools/export_packet_schema.py` and copy the updated client schema into `clients/web/packet_schema.json`.

## Input/Accessibility
- Preserve keyboard-first behavior and screen-reader friendliness.
- Avoid focus jumps unless explicitly required by flow (dialogs, reconnect, etc.).
- Keep menu selection stable across refresh packets unless server sends an explicit selection.

## Audio
- Default sound base URL is `./sounds`.
- Keep music/effects/ambience handling consistent with the desktop client where practical.

## Voice Chat
- `voice.js` mirrors `clients/desktop/voice_manager.py`: the same wire format (16kHz mono s16le, 20ms frames), the same transmit gating, and the same packets. Keep the two in step so browser and desktop players stay interoperable.
- `voice-worklet.js` holds the AudioWorklet processors. It is loaded by URL at runtime and is deliberately dependency-free so it can also be evaluated directly in tests.
- Every Web Audio object is created lazily and reachable through injectable options, so the logic is testable in Node without audio hardware.
- Browsers only expose real device labels after permission is granted; unlabeled devices get placeholder names and the panel explains why.
- `AudioContext.setSinkId` is not implemented everywhere. Report support honestly rather than offering a control that silently does nothing, and never pass the literal string `"default"` as a sink id - browsers reject it.

## Tests
- Run with `node --test "tests/*.test.js"` from this folder (Node 18+; no dependencies to install).
- `tests/voice_worklet.test.js` evaluates the worklet source against stub globals, so processor-only bugs stay covered outside a browser.
- Keep new behaviour covered here; there is no other test harness for this client.
