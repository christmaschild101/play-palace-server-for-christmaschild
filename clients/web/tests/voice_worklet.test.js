// Tests for the AudioWorklet processors in voice-worklet.js.
//
// The worklet source is a browser file, so it is evaluated here against stub
// AudioWorklet globals. That keeps the processor logic - resampling, frame
// cutting, and the per-speaker playback ring - covered by the Node suite
// instead of only being exercisable in a browser.

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

const workletUrl = new URL("../voice-worklet.js", import.meta.url);
const source = await readFile(workletUrl, "utf8");

/** Evaluate the worklet source and return its registered processor classes. */
function loadProcessors(sampleRate = 16000) {
  const registered = new Map();
  // The browser routes processor->main messages back to onmessage, so the stub
  // has to do the same or emitted frames never arrive.
  class StubAudioWorkletProcessor {
    constructor() {
      const port = {
        onmessage: null,
        postMessage(data) {
          queueMicrotask(() => port.onmessage?.({ data }));
        },
      };
      this.port = port;
    }
  }
  // The processors reference `registerProcessor` and the AudioWorklet globals.
  const factory = new Function(
    "AudioWorkletProcessor",
    "sampleRate",
    "registerProcessor",
    `${source}\nreturn null;`
  );
  factory(StubAudioWorkletProcessor, sampleRate, (name, ctor) => {
    registered.set(name, ctor);
  });
  return { registered, StubAudioWorkletProcessor };
}

function makeCapture(sampleRate) {
  const { registered, StubAudioWorkletProcessor } = loadProcessors(sampleRate);
  const Capture = registered.get("playpalace-voice-capture");
  assert.ok(Capture, "capture processor was not registered");
  return new Capture();
}

function makePlayer(sampleRate) {
  const { registered } = loadProcessors(sampleRate);
  const Player = registered.get("playpalace-voice-player");
  assert.ok(Player, "player processor was not registered");
  return new Player();
}

// -- Capture --------------------------------------------------------------

test("capture is registered under both names the client asks for", () => {
  const { registered } = loadProcessors();
  assert.ok(registered.has("playpalace-voice-capture"));
  assert.ok(registered.has("playpalace-voice-player"));
});

test("capture emits exact 20ms frames from a 48kHz context", async () => {
  const capture = makeCapture(48000);
  const frames = [];
  capture.port.onmessage = (event) => frames.push(new Int16Array(event.data.buffer));
  // The browser calls process() with 128-sample blocks; 4800 samples at 48kHz
  // is 100ms, so five 20ms frames of 320 samples must come out.
  for (let offset = 0; offset < 4800; offset += 128) {
    capture.process([[new Float32Array(128).fill(0.5)]]);
  }
  await tick();
  assert.equal(frames.length, 5);
  for (const frame of frames) {
    assert.equal(frame.length, 320);
  }
});

test("capture keeps the newest audio when a block exceeds its buffer", async () => {
  const capture = makeCapture(48000);
  const frames = [];
  capture.port.onmessage = (event) => frames.push(new Int16Array(event.data.buffer));
  // Larger than the 4096-sample buffer: only the tail survives, so four
  // frames come out rather than five. Browsers never send a block this big,
  // but the buffer must not overflow if one ever does.
  capture.process([[new Float32Array(4800).fill(0.5)]]);
  await tick();
  assert.equal(frames.length, 4);
  assert.equal(frames[0].length, 320);
});

test("capture preserves amplitude through resampling", async () => {
  const capture = makeCapture(48000);
  const frames = [];
  capture.port.onmessage = (event) => frames.push(new Int16Array(event.data.buffer));
  capture.process([[new Float32Array(4800).fill(0.5)]]);
  await tick();
  // 0.5 is half scale, so about 16384 either side of zero.
  const peak = Math.max(...frames[0].map((s) => Math.abs(s)));
  assert.ok(Math.abs(peak - 16384) < 200, `expected ~16384, got ${peak}`);
});

test("capture keeps frames aligned across uneven callbacks", async () => {
  const capture = makeCapture(48000);
  const frames = [];
  capture.port.onmessage = (event) => frames.push(new Int16Array(event.data.buffer));
  // At 48kHz a 20ms frame needs 960 input samples. Three 160-sample callbacks
  // are only 480 samples, so no frame may be emitted yet.
  for (let i = 0; i < 3; i += 1) {
    capture.process([[new Float32Array(160).fill(0.25)]]);
    await tick();
    assert.equal(frames.length, 0);
  }
  // The next three callbacks complete exactly one frame.
  for (let i = 0; i < 3; i += 1) {
    capture.process([[new Float32Array(160).fill(0.25)]]);
  }
  await tick();
  assert.equal(frames.length, 1);
  assert.equal(frames[0].length, 320);
});

test("capture downmixes multiple input channels to mono", async () => {
  const capture = makeCapture(48000);
  const frames = [];
  capture.port.onmessage = (event) => frames.push(new Int16Array(event.data.buffer));
  // Two identical channels must not double the amplitude.
  capture.process([[new Float32Array(4800).fill(0.5), new Float32Array(4800).fill(0.5)]]);
  await tick();
  const peak = Math.max(...frames[0].map((s) => Math.abs(s)));
  assert.ok(Math.abs(peak - 16384) < 200, `expected ~16384, got ${peak}`);
});

test("capture survives an empty input block", async () => {
  const capture = makeCapture(48000);
  let frames = 0;
  capture.port.onmessage = () => {
    frames += 1;
  };
  capture.process([[]]);
  capture.process([]);
  capture.process([[new Float32Array(480).fill(0.5)]]);
  await tick();
  assert.equal(frames, 0);
});

test("capture stops when told to", async () => {
  const capture = makeCapture(48000);
  capture.port.onmessage({ data: { type: "stop" } });
  assert.equal(capture.process([[new Float32Array(4800).fill(0.5)]]), false);
});

test("capture stays bounded when the main thread never drains", async () => {
  const capture = makeCapture(48000);
  capture.port.onmessage = () => {};
  // Far more audio than the internal buffer can hold.
  for (let i = 0; i < 200; i += 1) {
    capture.process([[new Float32Array(4800).fill(0.5)]]);
  }
  assert.ok(capture._filled <= capture._input.length);
  assert.ok(capture._readPos >= 0);
});

// -- Playback -------------------------------------------------------------

function deliver(player, sender, samples, volume) {
  const copy = samples.slice();
  const event = { data: { type: "frame", sender, buffer: copy.buffer, volume } };
  // The real MessagePort delivers a view over the transferred buffer.
  Object.defineProperty(event.data, "buffer", { value: copy.buffer });
  player.port.onmessage({ data: { type: "frame", sender, buffer: copy.buffer, volume } });
}

/** Port messages are delivered asynchronously; let them land. */
function tick() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function renderOutput(player, length = 128) {
  const out = new Float32Array(length);
  player.process([], [[out]]);
  return out;
}

test("playback emits the samples it was sent", () => {
  const player = makePlayer(16000);
  deliver(player, "ada", new Float32Array(320).fill(0.5), 1);
  const out = renderOutput(player);
  assert.ok(Array.from(out).every((s) => Math.abs(s - 0.5) < 1e-6));
});

test("playback applies the per-speaker volume", () => {
  const player = makePlayer(16000);
  deliver(player, "ada", new Float32Array(320).fill(1), 0.25);
  assert.ok(Math.abs(renderOutput(player)[0] - 0.25) < 1e-6);
});

test("playback resamples 16kHz audio up to the hardware rate", () => {
  const player = makePlayer(48000);
  deliver(player, "ada", new Float32Array(160).fill(0.5), 1);
  // At 48kHz a 16kHz frame covers a third as many output samples.
  const out = renderOutput(player, 128);
  assert.ok(Array.from(out).every((s) => Math.abs(s - 0.5) < 1e-6));
});

test("playback underruns to silence rather than repeating", () => {
  const player = makePlayer(16000);
  deliver(player, "ada", new Float32Array(64).fill(0.5), 1);
  renderOutput(player, 128);
  const out = renderOutput(player, 128);
  assert.ok(Array.from(out).every((s) => s === 0));
});

test("playback mixes several speakers with headroom", () => {
  const player = makePlayer(16000);
  deliver(player, "ada", new Float32Array(320).fill(1), 1);
  deliver(player, "bob", new Float32Array(320).fill(1), 1);
  const out = renderOutput(player);
  // Two speakers must still be audible, but never sum past full scale.
  assert.ok(out[0] > 0.5, `expected two speakers to sum, got ${out[0]}`);
  assert.ok(out[0] <= 1, `mix exceeded full scale with two speakers: ${out[0]}`);
});

test("closing a speaker removes it from the mix", () => {
  const player = makePlayer(16000);
  deliver(player, "ada", new Float32Array(320).fill(1), 1);
  player.port.onmessage({ data: { type: "close", sender: "ada" } });
  assert.ok(Array.from(renderOutput(player)).every((s) => s === 0));
  assert.equal(player._streams.size, 0);
});

test("a frame without a sender is ignored", () => {
  const player = makePlayer(16000);
  const copy = new Float32Array(320).fill(1);
  player.port.onmessage({ data: { type: "frame", sender: "", buffer: copy.buffer } });
  assert.equal(player._streams.size, 0);
});

test("the playback ring never overflows under sustained writes", () => {
  const player = makePlayer(16000);
  // Hammer writes far faster than playback drains, which is what a stalled
  // network looks like. This is the case that used to throw RangeError.
  for (let i = 0; i < 5000; i += 1) {
    deliver(player, "ada", new Float32Array(320).fill(0.5), 1);
    if (i % 3 === 0) {
      renderOutput(player, 128);
    }
  }
  assert.ok(player._streams.get("ada").filled <= player._streams.get("ada").buffer.length);
});

test("a frame larger than the whole ring keeps only its tail", () => {
  const player = makePlayer(16000);
  const oversized = new Float32Array(32000 + 800).fill(0.25);
  deliver(player, "ada", oversized, 1);
  const stream = player._streams.get("ada");
  assert.equal(stream.filled, stream.buffer.length);
  assert.equal(stream.readPos, 0);
  assert.ok(Array.from(renderOutput(player)).every((s) => Math.abs(s - 0.25) < 1e-6));
});

test("the playback ring stays bounded when nothing is ever consumed", () => {
  const player = makePlayer(16000);
  for (let i = 0; i < 1000; i += 1) {
    deliver(player, "ada", new Float32Array(320).fill(0.5), 1);
  }
  const stream = player._streams.get("ada");
  assert.ok(stream.filled <= stream.buffer.length);
  // The newest audio must survive the drop, not be replaced by the oldest.
  assert.ok(Math.abs(renderOutput(player)[0] - 0.5) < 1e-6);
});

test("an exactly-full ring still accepts the next frame", () => {
  const player = makePlayer(16000);
  const stream = player._streamFor("ada");
  stream.buffer = new Float32Array(1000);
  stream.filled = 1000;
  stream.readPos = 0;
  deliver(player, "ada", new Float32Array(320).fill(0.25), 1);
  assert.ok(player._streams.get("ada").filled <= 1000);
  assert.ok(Math.abs(renderOutput(player)[0] - 0.25) < 1e-6);
});

test("the ring drains to nothing and is forgotten", () => {
  const player = makePlayer(16000);
  deliver(player, "ada", new Float32Array(320).fill(0.5), 1);
  for (let i = 0; i < 10; i += 1) {
    renderOutput(player, 128);
  }
  assert.equal(player._streams.size, 0);
});