// Tests for the web client's audio playlists.
//
// Run with: node --test clients/web/tests/
//
// Mirrors the semantics of the desktop client's AudioPlaylist so both clients
// sequence playlists identically. The audio engine is a recording fake, so no
// audio hardware or browser is involved.

import assert from "node:assert/strict";
import test from "node:test";

import { createPlaylistManager } from "../playlist.js";

// -- Fakes -----------------------------------------------------------------

function makeAudioSpy() {
  const calls = [];
  let nextEnded = null;
  return {
    calls,
    playMusic(packet) {
      calls.push(["playMusic", packet.name]);
      nextEnded = packet.onEnded || null;
    },
    stopMusic() {
      calls.push(["stopMusic"]);
    },
    playSound(packet) {
      calls.push(["playSound", packet.name]);
    },
    /** Pretend the current music track finished. */
    finishTrack() {
      if (nextEnded) nextEnded();
    },
    names() {
      return calls.filter((call) => call[0] !== "stopMusic").map((call) => call[1]);
    },
  };
}

/** An element that reports a fixed duration as soon as metadata is asked for. */
function makeDurationElement(duration) {
  const listeners = {};
  const element = {
    src: "",
    duration,
    listeners,
    addEventListener(type, fn) {
      listeners[type] = fn;
    },
    load() {
      if (listeners.loadedmetadata) listeners.loadedmetadata();
    },
  };
  return element;
}

function makeManager(overrides = {}) {
  const audio = makeAudioSpy();
  const durations = overrides.durations || {};
  const created = [];
  const manager = createPlaylistManager({
    audio,
    createAudioElement: () => {
      const element = makeDurationElement(durations.track1 ?? 0);
      created.push(element);
      return element;
    },
    soundBaseUrl: "./sounds",
    random: overrides.random || (() => 0.5),
  });
  return { manager, audio, created };
}

// -- Tests -----------------------------------------------------------------

test("a playlist with auto_start plays its first track immediately", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({ playlist_id: "lobby", tracks: ["one.ogg", "two.ogg"] });

  assert.deepEqual(audio.names(), ["one.ogg"]);
  assert.equal(manager.isPlaying("lobby"), true);
});

test("auto_start false registers the playlist without playing", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({
    playlist_id: "lobby",
    tracks: ["one.ogg"],
    auto_start: false,
  });

  assert.deepEqual(audio.names(), []);
  assert.equal(manager.isPlaying("lobby"), false);
  assert.deepEqual(manager.getPlaylistIds(), ["lobby"]);
});

test("tracks advance in order until the playlist ends", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({ playlist_id: "lobby", tracks: ["one.ogg", "two.ogg"] });

  audio.finishTrack();
  assert.deepEqual(audio.names(), ["one.ogg", "two.ogg"]);

  audio.finishTrack();
  // The single repeat is used up and auto_remove drops the playlist.
  assert.deepEqual(audio.names(), ["one.ogg", "two.ogg"]);
  assert.deepEqual(manager.getPlaylistIds(), []);
});

test("auto_remove false keeps an exhausted playlist around", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({
    playlist_id: "lobby",
    tracks: ["one.ogg"],
    auto_remove: false,
  });

  audio.finishTrack();

  assert.deepEqual(manager.getPlaylistIds(), ["lobby"]);
  assert.equal(manager.isPlaying("lobby"), false);
});

test("repeats of 2 plays every track twice", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({
    playlist_id: "lobby",
    tracks: ["one.ogg", "two.ogg"],
    repeats: 2,
  });

  audio.finishTrack(); // -> two
  audio.finishTrack(); // -> one (second pass)
  assert.deepEqual(audio.names(), ["one.ogg", "two.ogg", "one.ogg"]);

  audio.finishTrack(); // -> two (second pass)
  audio.finishTrack(); // exhausted
  assert.deepEqual(audio.names(), ["one.ogg", "two.ogg", "one.ogg", "two.ogg"]);
  assert.deepEqual(manager.getPlaylistIds(), []);
});

test("repeats of 0 plays forever and is never auto-removed", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({
    playlist_id: "ambient",
    tracks: ["one.ogg", "two.ogg"],
    repeats: 0,
  });

  for (let index = 0; index < 12; index += 1) {
    audio.finishTrack();
  }

  assert.deepEqual(manager.getPlaylistIds(), ["ambient"]);
  assert.equal(manager.isPlaying("ambient"), true);
  assert.equal(audio.names().length, 13);
});

test("a negative or missing repeats still plays one pass", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({ playlist_id: "lobby", tracks: ["one.ogg"], repeats: -3 });

  audio.finishTrack();

  assert.deepEqual(audio.names(), ["one.ogg"]);
  assert.deepEqual(manager.getPlaylistIds(), []);
});

test("a sound playlist plays through the effects path", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({
    playlist_id: "chimes",
    tracks: ["ding.ogg"],
    audio_type: "sound",
  });

  assert.deepEqual(audio.calls, [["playSound", "ding.ogg"]]);
});

test("shuffle uses the injected random source", () => {
  // random() === 0 makes Fisher-Yates always swap with index 0, which turns
  // [a, b, c] into [b, c, a].
  const { manager, audio } = makeManager({ random: () => 0 });
  manager.addPlaylist({
    playlist_id: "lobby",
    tracks: ["a.ogg", "b.ogg", "c.ogg"],
    shuffle_tracks: true,
  });

  assert.deepEqual(audio.names(), ["b.ogg"]);
  audio.finishTrack();
  assert.deepEqual(audio.names(), ["b.ogg", "c.ogg"]);
  audio.finishTrack();
  assert.deepEqual(audio.names(), ["b.ogg", "c.ogg", "a.ogg"]);
});

test("adding a playlist with an existing id stops the old one first", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({ playlist_id: "lobby", tracks: ["old.ogg"] });
  audio.calls.length = 0;

  manager.addPlaylist({ playlist_id: "lobby", tracks: ["new.ogg"] });

  assert.deepEqual(audio.calls[0], ["stopMusic"]);
  assert.deepEqual(audio.names(), ["new.ogg"]);
  assert.deepEqual(manager.getPlaylistIds(), ["lobby"]);
});

test("start_playlist resumes a registered playlist", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({
    playlist_id: "lobby",
    tracks: ["one.ogg", "two.ogg"],
    auto_start: false,
  });

  assert.equal(manager.startPlaylist("lobby"), true);
  assert.deepEqual(audio.names(), ["one.ogg"]);
});

test("start_playlist on an unknown or empty playlist is a no-op", () => {
  const { manager } = makeManager();
  assert.equal(manager.startPlaylist("nope"), false);

  manager.addPlaylist({ playlist_id: "empty", tracks: [], auto_start: false });
  assert.equal(manager.startPlaylist("empty"), false);
});

test("remove_playlist stops playback and forgets the playlist", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({ playlist_id: "lobby", tracks: ["one.ogg"] });
  audio.calls.length = 0;

  assert.equal(manager.removePlaylist("lobby"), true);
  assert.deepEqual(audio.calls, [["stopMusic"]]);
  assert.deepEqual(manager.getPlaylistIds(), []);
  assert.equal(manager.removePlaylist("lobby"), false);
});

test("removeAllPlaylists clears everything", () => {
  const { manager } = makeManager();
  manager.addPlaylist({ playlist_id: "a", tracks: ["one.ogg"] });
  manager.addPlaylist({ playlist_id: "b", tracks: ["two.ogg"] });

  manager.removeAllPlaylists();

  assert.deepEqual(manager.getPlaylistIds(), []);
});

test("a single-track playlist restarts cleanly instead of resuming", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({
    playlist_id: "loop",
    tracks: ["only.ogg"],
    repeats: 0,
  });

  audio.finishTrack();

  // stopMusic must run before the next playMusic, otherwise the engine would
  // see the same track name and resume a finished element.
  const names = audio.calls.map((call) => call[0]);
  const stopIndex = names.lastIndexOf("stopMusic");
  const playIndex = names.lastIndexOf("playMusic");
  assert.ok(stopIndex < playIndex, "expected stopMusic before the next playMusic");
});

test("an empty track list never starts", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({ playlist_id: "empty", tracks: [] });

  assert.deepEqual(audio.calls, []);
  assert.equal(manager.isPlaying("empty"), false);
});

test("non-string tracks are discarded", () => {
  const { manager, audio } = makeManager();
  manager.addPlaylist({ playlist_id: "lobby", tracks: ["ok.ogg", null, 5, ""] });

  assert.deepEqual(audio.names(), ["ok.ogg"]);
});

test("a playlist with no id is rejected", () => {
  const { manager } = makeManager();
  assert.equal(manager.addPlaylist({ tracks: ["one.ogg"] }), null);
  assert.deepEqual(manager.getPlaylistIds(), []);
});

test("duration reports total, elapsed and remaining once measured", async () => {
  const durations = {};
  const audio = makeAudioSpy();
  const manager = createPlaylistManager({
    audio,
    createAudioElement: () => makeDurationElement(10),
    soundBaseUrl: "./sounds",
  });

  manager.addPlaylist({
    playlist_id: "lobby",
    tracks: ["one.ogg", "two.ogg"],
    repeats: 2,
  });

  const result = await manager.getPlaylistDuration("lobby", "total");
  assert.equal(result.total, 40, "two tracks of 10s, twice");
  assert.equal(result.complete, true);
  assert.equal(result.elapsed, 0, "nothing has finished yet");

  // Finishing the first track moves to the second, so ten seconds have elapsed.
  audio.finishTrack();
  const elapsed = await manager.getPlaylistDuration("lobby", "elapsed");
  assert.equal(elapsed.elapsed, 10);
  assert.equal(elapsed.remaining, 30);
});

test("duration of an unknown playlist is null", async () => {
  const { manager } = makeManager();
  assert.equal(await manager.getPlaylistDuration("nope", "total"), null);
});

test("duration reports incomplete when track lengths are unknown", async () => {
  const { manager } = makeManager({ durations: {} });
  manager.addPlaylist({ playlist_id: "lobby", tracks: ["mystery.ogg"] });

  const result = await manager.getPlaylistDuration("lobby", "total");
  assert.equal(result.complete, false, "an unmeasurable track must not look like 0s");
  assert.equal(result.total, 0);
});