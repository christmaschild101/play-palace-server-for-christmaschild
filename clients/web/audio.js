function isAbsoluteUrl(path) {
  return /^https?:\/\//i.test(path);
}

function isCrossOriginUrl(url) {
  try {
    const target = new URL(url, window.location.href);
    return target.origin !== window.location.origin;
  } catch {
    return false;
  }
}

function createAudioElement(url) {
  const audio = new Audio();
  if (isCrossOriginUrl(url)) {
    // Required for Web Audio processing of cross-origin media.
    audio.crossOrigin = "anonymous";
  }
  audio.src = url;
  return audio;
}

function toSoundUrl(name, soundBaseUrl) {
  if (!name) {
    return "";
  }
  if (isAbsoluteUrl(name) || name.startsWith("/")) {
    return name;
  }
  const base = String(soundBaseUrl || "./sounds").replace(/\/+$/, "");
  return `${base}/${name}`;
}

export function createAudioEngine(options = {}) {
  const soundBaseUrl = options.soundBaseUrl || "./sounds";
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const context = AudioCtx ? new AudioCtx() : null;

  let effectsGain = null;
  let musicGain = null;
  let ambienceGain = null;
  let currentMusic = null;
  let currentMusicNodes = null;
  let currentMusicName = "";
  let currentMusicLooping = true;
  let pendingMusicPacket = null;
  let currentAmbience = null;
  let currentAmbienceNodes = null;
  let currentAmbienceLoop = null;
  let currentAmbienceLoopNodes = null;
  let currentAmbienceLoopName = "";
  let pendingAmbiencePacket = null;
  const pendingEffectPackets = [];
  const MAX_PENDING_EFFECTS = 24;
  const activeEffects = new Map();
  let muted = false;

  // Decoded PCM is cached so a sound that repeats (typing ticks, chat
  // notifications, dice) plays from memory after the first time instead of
  // building a fresh media element and re-decoding the file on every play.
  // The cache is deliberately bounded: the sounds directory is far larger
  // than a sensible resident set, so the least recently played entries are
  // dropped once the limits below are exceeded.
  const MAX_CACHED_BUFFERS = 24;
  const MAX_CACHED_BYTES = 32 * 1024 * 1024;
  const bufferCache = new Map();
  const bufferPending = new Map();
  let cachedBytes = 0;

  if (context) {
    effectsGain = context.createGain();
    musicGain = context.createGain();
    ambienceGain = context.createGain();

    effectsGain.gain.value = 1.0;
    musicGain.gain.value = 0.2;
    ambienceGain.gain.value = 1.0;

    effectsGain.connect(context.destination);
    musicGain.connect(context.destination);
    ambienceGain.connect(context.destination);
  }

  async function unlock() {
    if (!context) {
      retryPendingPlayback();
      return false;
    }
    if (context.state !== "running") {
      await context.resume();
    }
    retryPendingPlayback();
    return context.state === "running";
  }

  function safePlay(audio, { onRejected } = {}) {
    audio.muted = muted;
    try {
      const maybePromise = audio.play();
      if (maybePromise && typeof maybePromise.catch === "function") {
        maybePromise.catch(() => {
          if (onRejected) {
            onRejected();
          }
        });
      }
    } catch {
      if (onRejected) {
        onRejected();
      }
    }
  }

  function connectElement(audio, gainNode, panValue = 0, url = "") {
    if (!context || !gainNode) {
      return null;
    }

    if (isCrossOriginUrl(url)) {
      // Cross-origin media can be silenced by Web Audio without CORS;
      // let the element play directly as a fallback.
      return null;
    }

    try {
      const source = context.createMediaElementSource(audio);
      if (typeof context.createStereoPanner === "function") {
        const panner = context.createStereoPanner();
        panner.pan.value = Math.max(-1, Math.min(1, panValue));
        source.connect(panner);
        panner.connect(gainNode);
        return { source, panner };
      }
      source.connect(gainNode);
      return { source, panner: null };
    } catch {
      // Fallback to direct element playback if node creation fails.
      return null;
    }
  }function disconnectNodes(nodes) {
    if (!nodes) return;
    try {
      nodes.source.disconnect();
    } catch { /* already disconnected */ }
    if (nodes.panner) {
      try {
        nodes.panner.disconnect();
      } catch { /* already disconnected */ }
    }
  }

  function bufferSize(buffer) {
    return buffer.length * buffer.numberOfChannels * 4;
  }

  function evictBuffers() {
    while (
      bufferCache.size > MAX_CACHED_BUFFERS ||
      cachedBytes > MAX_CACHED_BYTES
    ) {
      const oldest = bufferCache.keys().next();
      if (oldest.done) return;
      const evicted = bufferCache.get(oldest.value);
      bufferCache.delete(oldest.value);
      cachedBytes -= bufferSize(evicted);
    }
  }

  function warmBuffer(url) {
    // Fire-and-forget preload so the next play of this sound is instant.
    if (!context || isCrossOriginUrl(url)) return;
    if (bufferCache.has(url) || bufferPending.has(url)) return;

    const pending = fetch(url)
      .then((response) => (response.ok ? response.arrayBuffer() : null))
      .then((raw) => (raw ? context.decodeAudioData(raw) : null))
      .then((buffer) => {
        if (buffer) {
          bufferCache.set(url, buffer);
          cachedBytes += bufferSize(buffer);
          evictBuffers();
        }
        return buffer;
      })
      .catch(() => null)
      .finally(() => bufferPending.delete(url));

    bufferPending.set(url, pending);
  }

  function playCachedBuffer(url, volume, panValue, playbackRate) {
    // Play decoded PCM directly. Returns false so the caller can fall back to
    // the media-element path on a cache miss or if Web Audio refuses.
    if (!context || !effectsGain) return false;
    if (isCrossOriginUrl(url)) return false;
    const buffer = bufferCache.get(url);
    if (!buffer) return false;

    try {
      const source = context.createBufferSource();
      source.buffer = buffer;
      source.playbackRate.value = Math.max(0.5, Math.min(2, playbackRate));

      const gain = context.createGain();
      gain.gain.value = muted ? 0 : Math.max(0, Math.min(1, volume));

      let panner = null;
      if (typeof context.createStereoPanner === "function") {
        panner = context.createStereoPanner();
        panner.pan.value = Math.max(-1, Math.min(1, panValue));
        source.connect(gain);
        gain.connect(panner);
        panner.connect(effectsGain);
      } else {
        source.connect(gain);
        gain.connect(effectsGain);
      }

      source.addEventListener("ended", () => disconnectNodes({ source, panner }));
      source.start();
      return true;
    } catch {
      return false;
    }
  }

  function playSound(packet) {
    const name = packet.name || packet.sound || "";
    const url = toSoundUrl(name, soundBaseUrl);
    if (!url) {
      return;
    }

    const volume = (packet.volume ?? 100) / 100;
    const pitch = (packet.pitch ?? 100) / 100;
    const pan = (packet.pan ?? 0) / 100;

    warmBuffer(url);
    if (playCachedBuffer(url, volume, pan, pitch)) {
      return;
    }

    const audio = createAudioElement(url);
    audio.muted = muted;
    audio.preload = "auto";
    audio.volume = Math.max(0, Math.min(1, (packet.volume ?? 100) / 100));
    audio.playbackRate = Math.max(0.5, Math.min(2, (packet.pitch ?? 100) / 100));

    try {
      const nodes = connectElement(audio, effectsGain, (packet.pan ?? 0) / 100, url);
      if (!nodes && effectsGain) {
        audio.volume *= effectsGain.gain.value;
      }
      activeEffects.set(audio, nodes);
      const cleanup = () => {
        activeEffects.delete(audio);
        disconnectNodes(nodes);
      };
      audio.addEventListener("ended", cleanup);
      audio.addEventListener("error", cleanup);
      safePlay(audio, {
        onRejected: () => {
          cleanup();
          if (pendingEffectPackets.length >= MAX_PENDING_EFFECTS) {
            pendingEffectPackets.shift();
          }
          pendingEffectPackets.push({
            name,
            volume: packet.volume ?? 100,
            pan: packet.pan ?? 0,
            pitch: packet.pitch ?? 100,
          });
        },
      });
    } catch {
      // Ignore autoplay/stream failures before unlock.
    }
  }

  function playMusic(packet) {
    const name = packet.name || packet.music || "";
    const url = toSoundUrl(name, soundBaseUrl);
    if (!url) {
      return;
    }
    const looping = packet.looping ?? true;
    const onEnded = typeof packet.onEnded === "function" ? packet.onEnded : null;

    // Match desktop behavior: don't restart music if the same track is already active.
    if (currentMusic && currentMusicName === name && currentMusicLooping === looping) {
      if (currentMusic.paused) {
        safePlay(currentMusic, {
          onRejected: () => {
            pendingMusicPacket = { name, looping };
          },
        });
      }
      return;
    }

    stopMusic();

    const audio = createAudioElement(url);
    audio.muted = muted;
    audio.preload = "auto";
    audio.loop = looping;
    audio.volume = 1.0;

    // Playlists chain tracks by listening for the end of the current one.
    if (onEnded) {
      audio.addEventListener("ended", () => onEnded(audio));
    }

    try {
      const nodes = connectElement(audio, musicGain, 0, url);
      if (!nodes && musicGain) {
        audio.volume *= musicGain.gain.value;
      }
      currentMusic = audio;
      currentMusicNodes = nodes;
      currentMusicName = name;
      currentMusicLooping = looping;
      pendingMusicPacket = null;
      safePlay(audio, {
        onRejected: () => {
          pendingMusicPacket = { name, looping };
        },
      });
    } catch {
      currentMusic = audio;
      currentMusicNodes = null;
      currentMusicName = name;
      currentMusicLooping = looping;
      pendingMusicPacket = { name, looping };
    }
  }

  function stopMusic() {
    if (!currentMusic) {
      return;
    }
    try {
      currentMusic.pause();
      currentMusic.currentTime = 0;
    } catch {
      // Ignore stop failures.
    }
    disconnectNodes(currentMusicNodes);
    currentMusic = null;
    currentMusicNodes = null;
    currentMusicName = "";
    currentMusicLooping = true;
    pendingMusicPacket = null;
  }

  function stopAmbience() {
    if (currentAmbience) {
      try {
        currentAmbience.pause();
        currentAmbience.currentTime = 0;
      } catch {
        // Ignore stop failures.
      }
      disconnectNodes(currentAmbienceNodes);
      currentAmbience = null;
      currentAmbienceNodes = null;
    }
    if (currentAmbienceLoop) {
      try {
        currentAmbienceLoop.pause();
        currentAmbienceLoop.currentTime = 0;
      } catch {
        // Ignore stop failures.
      }
      disconnectNodes(currentAmbienceLoopNodes);
      currentAmbienceLoop = null;
      currentAmbienceLoopNodes = null;
    }
    currentAmbienceLoopName = "";
    pendingAmbiencePacket = null;
  }

  function playAmbience(packet) {
    const loopName = packet.loop || "";
    const introName = packet.intro || "";
    if (!loopName) {
      return;
    }
    if (currentAmbienceLoop && currentAmbienceLoopName === loopName) {
      if (currentAmbienceLoop.paused) {
        safePlay(currentAmbienceLoop, {
          onRejected: () => {
            pendingAmbiencePacket = {
              loop: loopName,
              intro: introName,
              outro: packet.outro || "",
            };
          },
        });
      }
      return;
    }

    stopAmbience();

    const loopAudio = createAudioElement(toSoundUrl(loopName, soundBaseUrl));
    loopAudio.muted = muted;
    loopAudio.preload = "auto";
    loopAudio.loop = true;
    loopAudio.volume = 1.0;
    const loopUrl = toSoundUrl(loopName, soundBaseUrl);
    const loopNodes = connectElement(loopAudio, ambienceGain, 0, loopUrl);
    if (!loopNodes && ambienceGain) {
      loopAudio.volume *= ambienceGain.gain.value;
    }

    const startLoop = () => {
      currentAmbienceLoop = loopAudio;
      currentAmbienceLoopNodes = loopNodes;
      currentAmbienceLoopName = loopName;
      pendingAmbiencePacket = null;
      safePlay(loopAudio, {
        onRejected: () => {
          pendingAmbiencePacket = {
            loop: loopName,
            intro: introName,
            outro: packet.outro || "",
          };
        },
      });
    };

    if (introName) {
      const introAudio = createAudioElement(toSoundUrl(introName, soundBaseUrl));
      introAudio.muted = muted;
      introAudio.preload = "auto";
      introAudio.loop = false;
      introAudio.volume = 1.0;
      const introUrl = toSoundUrl(introName, soundBaseUrl);
      const introNodes = connectElement(introAudio, ambienceGain, 0, introUrl);
      if (!introNodes && ambienceGain) {
        introAudio.volume *= ambienceGain.gain.value;
      }
      introAudio.addEventListener("ended", () => {
        disconnectNodes(introNodes);
        currentAmbienceNodes = null;
        startLoop();
      }, { once: true });
      currentAmbience = introAudio;
      currentAmbienceNodes = introNodes;
      safePlay(introAudio, {
        onRejected: () => {
          pendingAmbiencePacket = {
            loop: loopName,
            intro: introName,
            outro: packet.outro || "",
          };
          startLoop();
        },
      });
      return;
    }

    startLoop();
  }

  function retryPendingPlayback() {
    if (pendingMusicPacket) {
      const packet = pendingMusicPacket;
      pendingMusicPacket = null;
      playMusic(packet);
    }
    if (pendingAmbiencePacket) {
      const packet = pendingAmbiencePacket;
      pendingAmbiencePacket = null;
      playAmbience(packet);
    }
    if (pendingEffectPackets.length > 0) {
      const packets = pendingEffectPackets.splice(0, pendingEffectPackets.length);
      for (const packet of packets) {
        playSound(packet);
      }
    }
  }

  function setMusicVolumePercent(percent) {
    const bounded = Math.max(0, Math.min(100, Number(percent)));
    if (musicGain) {
      musicGain.gain.value = bounded / 100;
    } else if (currentMusic) {
      currentMusic.volume = bounded / 100;
    }
    return bounded;
  }

  function setAmbienceVolumePercent(percent) {
    const bounded = Math.max(0, Math.min(100, Number(percent)));
    if (ambienceGain) {
      ambienceGain.gain.value = bounded / 100;
    } else {
      if (currentAmbience) {
        currentAmbience.volume = bounded / 100;
      }
      if (currentAmbienceLoop) {
        currentAmbienceLoop.volume = bounded / 100;
      }
    }
    return bounded;
  }

  function setMuted(nextMuted) {
    muted = Boolean(nextMuted);
    if (currentMusic) {
      currentMusic.muted = muted;
    }
    if (currentAmbience) {
      currentAmbience.muted = muted;
    }
    if (currentAmbienceLoop) {
      currentAmbienceLoop.muted = muted;
    }
    for (const effect of activeEffects.keys()) {
      effect.muted = muted;
    }
  }

  function isMuted() {
    return muted;
  }

  function getMusicVolumePercent() {
    if (musicGain) {
      return Math.round(musicGain.gain.value * 100);
    }
    if (currentMusic) {
      return Math.round(currentMusic.volume * 100);
    }
    return 20;
  }

  function getAmbienceVolumePercent() {
    if (ambienceGain) {
      return Math.round(ambienceGain.gain.value * 100);
    }
    if (currentAmbienceLoop) {
      return Math.round(currentAmbienceLoop.volume * 100);
    }
    return 100;
  }

  function stopAll() {
    stopMusic();
    stopAmbience();
    for (const [audio, nodes] of activeEffects) {
      try {
        audio.pause();
        audio.currentTime = 0;
      } catch {
        // Ignore per-element stop failures.
      }
      disconnectNodes(nodes);
    }
    activeEffects.clear();
  }

  return {
    unlock,
    playSound,
    playMusic,
    playAmbience,
    stopMusic,
    stopAmbience,
    stopAll,
    setMusicVolumePercent,
    setAmbienceVolumePercent,
    getMusicVolumePercent,
    getAmbienceVolumePercent,
    setMuted,
    isMuted,
    retryPendingPlayback,
  };
}
