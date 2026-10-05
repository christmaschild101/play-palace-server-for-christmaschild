# Web Client Notes

## Scope
- This folder contains the browser client for PlayPalace v12.
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
- **`.htaccess` caches `.ogg`/`.mp3`/`.wav` for a year (`immutable`) but keeps code assets `no-store`.** Sounds used to match the `no-store` rule, so the browser re-downloaded the file on *every play*; measured in Chromium, six plays of a 10KB effect pulled 65KB over the network instead of 11KB. Sound files are named after the effect and never edited in place, so a renamed file is still fetched fresh. Do not widen the `no-store` rule to cover sounds.
- `audio.js` keeps a bounded LRU cache of decoded `AudioBuffer`s (`MAX_CACHED_BUFFERS`, `MAX_CACHED_BYTES`). A sound plays through a media element on a cache miss and from memory once decoded. The cache is warmed in the background on first play, so the play path stays synchronous and the existing autoplay-retry behaviour is unchanged. Cross-origin URLs are never cached (no CORS, and Web Audio would silence them) and fall back to the element path; any fetch or decode failure falls back too.
- Music and ambience deliberately stay on the media-element path - they are long, loop, and would blow the decode cache budget.

## Audio Playlists
- `playlist.js` mirrors the desktop client's playlist support in `clients/desktop/sound_manager.py`. The server sends `add_playlist` / `start_playlist` / `remove_playlist` / `get_playlist_duration`, and the **client** does the sequencing - nothing about playlists is server state.
- Keep these semantics identical to the desktop client, since the same server feature drives both: `repeats` of `0` means forever and anything else is clamped to at least one pass; `auto_start` begins playback when tracks exist; `auto_remove` drops the playlist once its repeats run out.
- Track advancement relies on the `onEnded` hook that `audio.js`'s `playMusic` accepts. The playlist calls `stopMusic()` before each track on purpose: without it a repeating single-track playlist would hit `playMusic`'s "already playing this track" short-circuit and resume a finished element instead of starting over.
- `get_playlist_duration` replies with a `playlist_duration_response` packet (a **client-to-server** packet; `duration` is whole seconds). Track lengths come from browser metadata, so they can be unknown - the result carries a `complete` flag rather than reporting "0 seconds" for a track it has not measured.
- Playlists are dropped on disconnect in `resetDisconnectedUi`; they belong to the session that ended.

## Voice Chat
- `voice.js` mirrors `clients/desktop/voice_manager.py`: the same wire format (16kHz mono s16le, 20ms frames), the same transmit gating, and the same packets. Keep the two in step so browser and desktop players stay interoperable.
- `voice-worklet.js` holds the AudioWorklet processors. It is loaded by URL at runtime and is deliberately dependency-free so it can also be evaluated directly in tests.
- Every Web Audio object is created lazily and reachable through injectable options, so the logic is testable in Node without audio hardware.
- Browsers only expose real device labels after permission is granted; unlabeled devices get placeholder names and the panel explains why.
- `AudioContext.setSinkId` is not implemented everywhere. Report support honestly rather than offering a control that silently does nothing, and never pass the literal string `"default"` as a sink id - browsers reject it.

## Tests
- Run with `node --test "tests/*.test.js"` from this folder (Node 18+; no dependencies to install).
- `tests/voice_worklet.test.js` evaluates the worklet source against stub globals, so processor-only bugs stay covered outside a browser.
- `tests/audio.test.js` covers the decode cache with injected `fetch`, `Audio` and `AudioContext`. The fake `window.location` must include `origin`, not just `href`: the engine compares `URL#origin` against `location.origin`, and a missing `origin` makes every sound look cross-origin.
- `tests/playlist.test.js` injects both the audio engine and an RNG, so shuffle order and track advancement are asserted deterministically without audio hardware.
- Keep new behaviour covered here; there is no other test harness for this client.
