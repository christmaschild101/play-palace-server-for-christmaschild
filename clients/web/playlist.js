// Audio playlists for the web client.
//
// This mirrors the desktop client's playlist support in
// clients/desktop/sound_manager.py: the server sends add_playlist /
// start_playlist / remove_playlist / get_playlist_duration packets, and the
// client does the actual sequencing locally. Nothing here talks to the server.
//
// Semantics kept identical to the desktop client so a server feature behaves
// the same for browser and desktop players:
//   * `repeats` of 0 means play forever; anything else is clamped to at least 1.
//   * `auto_start` begins playback immediately when tracks exist.
//   * `auto_remove` drops the playlist once its repeats are exhausted, and is
//     ignored for an infinite playlist (which never exhausts anyway).

const DEFAULT_TRACK_DURATION = 0;

/** Shuffle in place using an injectable RNG so tests are deterministic. */
function shuffleInPlace(items, random) {
  for (let index = items.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(random() * (index + 1));
    const held = items[index];
    items[index] = items[swap];
    items[swap] = held;
  }
  return items;
}

export function createPlaylistManager({
  audio,
  createAudioElement,
  soundBaseUrl = "./sounds",
  random = Math.random,
} = {}) {
  const playlists = new Map();
  const durationCache = new Map();

  function trackUrl(name) {
    const base = String(soundBaseUrl || "./sounds").replace(/\/+$/, "");
    return `${base}/${name}`;
  }

  /** Probe one track's duration via a metadata-only element. */
  function probeDuration(name) {
    if (durationCache.has(name)) {
      return Promise.resolve(durationCache.get(name));
    }
    if (typeof createAudioElement !== "function") {
      return Promise.resolve(DEFAULT_TRACK_DURATION);
    }

    let element;
    try {
      element = createAudioElement();
      element.preload = "metadata";
    } catch {
      return Promise.resolve(DEFAULT_TRACK_DURATION);
    }

    return new Promise((resolve) => {
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        const duration = Number.isFinite(value) && value > 0 ? value : DEFAULT_TRACK_DURATION;
        durationCache.set(name, duration);
        resolve(duration);
      };

      element.addEventListener("loadedmetadata", () => finish(element.duration));
      element.addEventListener("error", () => finish(DEFAULT_TRACK_DURATION));
      try {
        element.src = trackUrl(name);
        if (typeof element.load === "function") {
          element.load();
        }
      } catch {
        finish(DEFAULT_TRACK_DURATION);
      }
    });
  }

  function playTrack(playlist, name) {
    if (playlist.audioType === "music") {
      // Stop first so a repeated single-track playlist does not hit the
      // engine's "already playing this track" short-circuit and resume a
      // finished element instead of starting over.
      audio.stopMusic();
      audio.playMusic({
        name,
        looping: false,
        onEnded: () => playNextTrack(playlist),
      });
      return;
    }
    audio.playSound({ name });
  }

  function playNextTrack(playlist) {
    if (!playlist.isActive || playlist.tracks.length === 0) {
      return;
    }

    if (playlist.trackIndex >= playlist.tracks.length) {
      playlist.trackIndex = 0;
      playlist.currentRepeat += 1;

      // repeats === 0 is infinite, so it never runs out.
      if (playlist.repeats !== 0 && playlist.currentRepeat > playlist.repeats) {
        playlist.isActive = false;
        if (playlist.autoRemove && playlist.playlistId) {
          removePlaylist(playlist.playlistId);
        }
        return;
      }
    }

    const name = playlist.tracks[playlist.trackIndex];
    playlist.trackIndex += 1;
    playTrack(playlist, name);
  }

  function addPlaylist(packet = {}) {
    const playlistId = String(packet.playlist_id ?? "");
    if (!playlistId) {
      return null;
    }

    const tracks = Array.isArray(packet.tracks)
      ? packet.tracks.filter((track) => typeof track === "string" && track)
      : [];

    // Replacing an existing id must stop what is currently playing, exactly
    // as the desktop client's add_playlist does.
    removePlaylist(playlistId);

    const playlist = {
      playlistId,
      originalTracks: tracks.slice(),
      tracks: tracks.slice(),
      audioType: packet.audio_type === "sound" ? "sound" : "music",
      shuffle: Boolean(packet.shuffle_tracks),
      // 0 means forever; anything else is at least one pass.
      repeats: Number(packet.repeats) === 0 ? 0 : Math.max(1, Number(packet.repeats) || 1),
      currentRepeat: 1,
      trackIndex: 0,
      isActive: false,
      autoRemove: packet.auto_remove !== false,
    };

    if (playlist.shuffle) {
      shuffleInPlace(playlist.tracks, random);
    }

    playlists.set(playlistId, playlist);

    if (packet.auto_start !== false && playlist.tracks.length > 0) {
      playlist.isActive = true;
      playNextTrack(playlist);
    }

    return playlist;
  }

  function startPlaylist(playlistId) {
    const playlist = playlists.get(String(playlistId));
    if (!playlist || playlist.tracks.length === 0) {
      return false;
    }
    playlist.isActive = true;
    if (playlist.trackIndex >= playlist.tracks.length) {
      playlist.trackIndex = 0;
    }
    playNextTrack(playlist);
    return true;
  }

  function stopPlaylist(playlistId) {
    const playlist = playlists.get(String(playlistId));
    if (!playlist) {
      return false;
    }
    playlist.isActive = false;
    if (playlist.audioType === "music") {
      audio.stopMusic();
    }
    return true;
  }

  function removePlaylist(playlistId) {
    const playlist = playlists.get(String(playlistId));
    if (!playlist) {
      return false;
    }
    playlist.isActive = false;
    if (playlist.audioType === "music") {
      audio.stopMusic();
    }
    playlists.delete(playlist.playlistId);
    return true;
  }

  function removeAllPlaylists() {
    for (const playlistId of Array.from(playlists.keys())) {
      removePlaylist(playlistId);
    }
  }

  /**
   * Report how long a playlist lasts.
   *
   * Durations come from the browser's own metadata, so they can be unknown
   * (0) until a track has been probed. `complete` reports whether every
   * track's length is known, so callers can tell "three seconds" from
   "not measured yet".
   */
  async function getPlaylistDuration(playlistId, durationType = "total") {
    const playlist = playlists.get(String(playlistId));
    if (!playlist) {
      return null;
    }

    const durations = await Promise.all(
      playlist.tracks.map((track) => probeDuration(track)),
    );
    const complete = durations.every((duration) => duration > 0);

    const passDuration = durations.reduce((sum, duration) => sum + duration, 0);
    // An infinite playlist has no end, so only report the current pass.
    const total = playlist.repeats === 0 ? passDuration : passDuration * playlist.repeats;

    let elapsed = 0;
    for (let index = 0; index < playlist.trackIndex - 1; index += 1) {
      elapsed += durations[index] || 0;
    }
    elapsed += (playlist.currentRepeat - 1) * passDuration;

    if (durationType === "elapsed") {
      return { total, elapsed, remaining: total - elapsed, complete, passes: playlist.repeats };
    }
    if (durationType === "remaining") {
      return { total, elapsed, remaining: total - elapsed, complete, passes: playlist.repeats };
    }
    return { total, elapsed, remaining: total - elapsed, complete, passes: playlist.repeats };
  }

  return {
    addPlaylist,
    startPlaylist,
    stopPlaylist,
    removePlaylist,
    removeAllPlaylists,
    getPlaylistDuration,
    getPlaylist: (playlistId) => playlists.get(String(playlistId)) || null,
    getPlaylistIds: () => Array.from(playlists.keys()),
    isPlaying: (playlistId) => Boolean(playlists.get(String(playlistId))?.isActive),
    /** Test seam: drive track advancement without real audio. */
    playNextTrackForTest: (playlistId) => {
      const playlist = playlists.get(String(playlistId));
      if (playlist) playNextTrack(playlist);
    },
  };
}