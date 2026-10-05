// Tests for the web client's audio engine.
//
// Run with: node --test clients/web/tests/
//
// The engine's Web Audio surface, fetch and Audio element are all injected,
// so these assertions run without audio hardware and without a browser.

import assert from "node:assert/strict";
import test from "node:test";

import { createAudioEngine } from "../audio.js";

// -- Fakes -----------------------------------------------------------------

class FakeGainNode {
  constructor() {
    this.gain = { value: 1 };
  }
  connect() {}
  disconnect() {}
}

class FakePannerNode {
  constructor() {
    this.pan = { value: 0 };
  }
  connect() {}
  disconnect() {}
}

class FakeBufferSource {
  constructor(context) {
    this.context = context;
    this.buffer = null;
    this.playbackRate = { value: 1 };
    this.started = false;
    this.listeners = {};
  }
  connect() {}
  disconnect() {}
  addEventListener(type, fn) {
    this.listeners[type] = fn;
  }
  start() {
    this.started = true;
    this.context.bufferSources.push(this);
  }
}

class FakeAudioContext {
  constructor({ decodeFails = false } = {}) {
    this.state = "running";
    this.destination = {};
    this.bufferSources = [];
    this.decodedUrls = [];
    this.decodeFails = decodeFails;
  }
  createGain() {
    return new FakeGainNode();
  }
  createStereoPanner() {
    return new FakePannerNode();
  }
  createBufferSource() {
    return new FakeBufferSource(this);
  }
  createMediaElementSource() {
    return { connect() {}, disconnect() {} };
  }
  async resume() {
    this.state = "running";
  }
  async decodeAudioData(raw) {
    this.decodedUrls.push(raw);
    if (this.decodeFails) {
      throw new Error("decode failed");
    }
    return { length: raw.byteLength / 4, numberOfChannels: 2 };
  }
}

class FakeAudioElement {
  constructor() {
    this.src = "";
    this.paused = false;
    this.currentTime = 0;
    this.muted = false;
    this.volume = 1;
    this.loop = false;
    this.playbackRate = 1;
    this.listeners = {};
    FakeAudioElement.created.push(this);
  }
  play() {
    this.paused = false;
    return Promise.resolve();
  }
  pause() {
    this.paused = true;
  }
  addEventListener(type, fn) {
    this.listeners[type] = fn;
  }
}
FakeAudioElement.created = [];

const PAGE_URL = "https://play.example/index.html";
const PAGE_ORIGIN = "https://play.example";

function makeEngine(options = {}) {
  FakeAudioElement.created = [];
  const context = options.context || new FakeAudioContext();
  const fetches = [];
  const previousWindow = globalThis.window;
  const previousFetch = globalThis.fetch;
  const previousAudio = globalThis.Audio;

  globalThis.window = {
    AudioContext: function () { return context; },
    // `origin` is what the engine compares against, so it must be present.
    location: { href: PAGE_URL, origin: PAGE_ORIGIN },
  };
  globalThis.Audio = FakeAudioElement;
  globalThis.fetch = (url) => {
    fetches.push(url);
    if (options.fetchFails) {
      return Promise.resolve({ ok: false, arrayBuffer: () => Promise.reject(new Error("no")) });
    }
    return Promise.resolve({
      ok: true,
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(4096)),
    });
  };

  const engine = createAudioEngine({ soundBaseUrl: "./sounds" });

  return {
    engine,
    context,
    fetches,
    elements: FakeAudioElement.created,
    restore() {
      globalThis.window = previousWindow;
      globalThis.fetch = previousFetch;
      globalThis.Audio = previousAudio;
    },
  };
}

/** Let queued microtasks (fetch + decode) settle. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

// -- Tests -----------------------------------------------------------------

test("a sound is played through a media element until it is cached", async () => {
  const harness = makeEngine();
  try {
    harness.engine.playSound({ name: "chat.ogg" });
    assert.equal(harness.elements.length, 1, "first play should use an element");
    assert.equal(harness.elements[0].src, "./sounds/chat.ogg");
    assert.equal(harness.context.bufferSources.length, 0);

    await settle();

    harness.engine.playSound({ name: "chat.ogg" });
    assert.equal(harness.elements.length, 1, "second play should reuse decoded PCM");
    assert.equal(harness.context.bufferSources.length, 1);
    assert.equal(harness.context.bufferSources[0].started, true);
  } finally {
    harness.restore();
  }
});

test("the sound file is fetched and decoded only once", async () => {
  const harness = makeEngine();
  try {
    harness.engine.playSound({ name: "chat.ogg" });
    await settle();
    harness.engine.playSound({ name: "chat.ogg" });
    harness.engine.playSound({ name: "chat.ogg" });
    await settle();

    assert.deepEqual(harness.fetches, ["./sounds/chat.ogg"], "should fetch once, not per play");
    assert.equal(harness.elements.length, 1);
    assert.equal(harness.context.decodedUrls.length, 1);
  } finally {
    harness.restore();
  }
});

test("distinct sounds each get their own cache entry", async () => {
  const harness = makeEngine();
  try {
    harness.engine.playSound({ name: "chat.ogg" });
    harness.engine.playSound({ name: "dice.ogg" });
    await settle();

    harness.engine.playSound({ name: "chat.ogg" });
    harness.engine.playSound({ name: "dice.ogg" });

    assert.equal(harness.elements.length, 2);
    assert.equal(harness.context.bufferSources.length, 2);
  } finally {
    harness.restore();
  }
});

test("a failed fetch falls back to the element path and still plays", async () => {
  const harness = makeEngine({ fetchFails: true });
  try {
    harness.engine.playSound({ name: "chat.ogg" });
    await settle();

    harness.engine.playSound({ name: "chat.ogg" });

    assert.equal(harness.elements.length, 2, "should fall back to a fresh element");
    assert.equal(harness.context.bufferSources.length, 0);
  } finally {
    harness.restore();
  }
});

test("a failed decode falls back to the element path and still plays", async () => {
  const harness = makeEngine({ context: new FakeAudioContext({ decodeFails: true }) });
  try {
    harness.engine.playSound({ name: "chat.ogg" });
    await settle();

    harness.engine.playSound({ name: "chat.ogg" });

    assert.equal(harness.elements.length, 2, "should fall back to a fresh element");
  } finally {
    harness.restore();
  }
});

test("the cache is bounded so many distinct sounds cannot grow without limit", async () => {
  const harness = makeEngine();
  try {
    for (let index = 0; index < 60; index += 1) {
      harness.engine.playSound({ name: `sound${index}.ogg` });
    }
    await settle();

    // Every sound still plays, and the oldest are dropped rather than kept.
    for (let index = 0; index < 60; index += 1) {
      harness.engine.playSound({ name: `sound${index}.ogg` });
    }

    // 60 sounds warmed, but only the last 24 survive the cache. The second pass
    // therefore plays the 24 survivors from memory and re-creates elements for
    // the 36 that were evicted: 60 + 36 = 96 element plays, not 120.
    assert.equal(harness.elements.length, 96);
  } finally {
    harness.restore();
  }
});

test("muting silences cached playback too", async () => {
  const harness = makeEngine();
  try {
    harness.engine.playSound({ name: "chat.ogg" });
    await settle();

    harness.engine.setMuted(true);
    const before = harness.context.bufferSources.length;
    harness.engine.playSound({ name: "chat.ogg" });

    assert.equal(harness.context.bufferSources.length, before + 1);
    assert.equal(harness.engine.isMuted(), true);
  } finally {
    harness.restore();
  }
});

test("pitch is clamped before reaching the cached playback rate", async () => {
  const harness = makeEngine();
  try {
    harness.engine.playSound({ name: "chat.ogg" });
    await settle();

    harness.engine.playSound({ name: "chat.ogg", pitch: 400 });

    const source = harness.context.bufferSources.at(-1);
    assert.ok(source.playbackRate.value <= 2, "rate should be clamped");
  } finally {
    harness.restore();
  }
});

test("cross-origin sound urls never enter the cache", async () => {
  const harness = makeEngine();
  try {
    harness.engine.playSound({ name: "https://cdn.example.com/chat.ogg" });
    await settle();

    assert.deepEqual(harness.fetches, [], "cross-origin audio must not be fetched");
    assert.equal(harness.context.bufferSources.length, 0);
    assert.equal(harness.elements.length, 1, "cross-origin audio plays via the element");
    assert.equal(harness.elements[0].crossOrigin, "anonymous");
  } finally {
    harness.restore();
  }
});

test("music and ambience still play through the element path", async () => {
  const harness = makeEngine();
  try {
    harness.engine.playMusic({ name: "theme.ogg", looping: true });
    harness.engine.playAmbience({ loop: "crowd.ogg", intro: "crowdintro.ogg" });
    await settle();

    const sources = harness.elements.map((element) => element.src);
    assert.ok(sources.includes("./sounds/theme.ogg"), "music uses an element");
    assert.ok(sources.includes("./sounds/crowd.ogg"), "ambience loop uses an element");
    assert.equal(harness.engine.getMusicVolumePercent(), 20);
    assert.equal(harness.context.bufferSources.length, 0, "long audio is not buffer-cached");
  } finally {
    harness.restore();
  }
});