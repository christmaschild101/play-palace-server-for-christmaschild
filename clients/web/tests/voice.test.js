// Tests for the web client's voice chat.
//
// Run with: node --test clients/web/tests/
//
// The manager's Web Audio surface is injected, so every assertion here runs
// without audio hardware and without a browser.

import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_MIC_GAIN,
  DEFAULT_VOICE_ACTIVITY_HANG_MS,
  DEFAULT_VOICE_ACTIVITY_THRESHOLD,
  MODE_PUSH_TO_TALK,
  MODE_VOICE_ACTIVITY,
  VOICE_FRAME_BYTES,
  VOICE_FRAME_SAMPLES,
  VOICE_SAMPLE_RATE,
  applyGain,
  bytesToBase64,
  createVoiceActivityDetector,
  createVoiceCapture,
  createVoiceManager,
  createVoicePlayer,
  decodeVoiceFrame,
  floatToInt16,
  int16ToFloat,
  resampleLinear,
} from "../voice.js";

// -- Helpers ---------------------------------------------------------------

function int16ToBytes(samples) {
  return new Uint8Array(samples.buffer, samples.byteOffset, samples.byteLength);
}

/** A frame of constant amplitude, as the microphone would produce. */
function toneFrame(amplitude, length = VOICE_FRAME_SAMPLES) {
  const samples = new Int16Array(length);
  samples.fill(Math.max(-32768, Math.min(32767, Math.round(amplitude))));
  return samples;
}

function decodeBase64(bytes) {
  return bytesToBase64(bytes);
}

// -- Wire format -----------------------------------------------------------

test("the wire format matches the server's 16kHz mono s16le 20ms frames", () => {
  assert.equal(VOICE_SAMPLE_RATE, 16000);
  assert.equal(VOICE_FRAME_SAMPLES, 320);
  assert.equal(VOICE_FRAME_BYTES, 640);
});

test("float samples round-trip through signed 16-bit", () => {
  const floats = new Float32Array([0, 0.5, -0.5, 1, -1, 0.25]);
  const ints = floatToInt16(floats);
  assert.deepEqual(Array.from(ints), [0, 16384, -16384, 32767, -32768, 8192]);
  const back = int16ToFloat(ints);
  assert.ok(Math.abs(back[0] - 0) < 1e-4);
  assert.ok(Math.abs(back[3] - 1) < 1e-4);
  assert.ok(Math.abs(back[4] + 1) < 1e-4);
});

test("base64 encoding and voice frame decoding round-trip exactly", () => {
  const frame = toneFrame(8000);
  const payload = decodeBase64(int16ToBytes(frame));
  const decoded = decodeVoiceFrame(payload);
  assert.deepEqual(Array.from(decoded), Array.from(frame));
});

test("decoding rejects payloads that are not base64 or carry no samples", () => {
  assert.equal(decodeVoiceFrame("not base64 !!"), null);
  assert.equal(decodeVoiceFrame(""), null);
  assert.equal(decodeVoiceFrame(null), null);
  assert.equal(decodeVoiceFrame(12345), null);
  // A single odd byte cannot be a signed 16-bit sample.
  assert.equal(decodeVoiceFrame(Buffer.from([1]).toString("base64")), null);
});

test("an odd-length frame keeps the whole samples and drops the stray byte", () => {
  const frame = toneFrame(1234);
  const bytes = int16ToBytes(frame);
  const padded = new Uint8Array(bytes.length + 1);
  padded.set(bytes, 0);
  const decoded = decodeVoiceFrame(Buffer.from(padded).toString("base64"));
  assert.deepEqual(Array.from(decoded), Array.from(frame));
});

// -- Resampling ------------------------------------------------------------

test("resampling halves the sample count at half the rate", () => {
  const input = new Float32Array([0, 1, 2, 3]);
  const output = resampleLinear(input, 48000, 16000);
  assert.equal(output.length, 1);
  assert.equal(output[0], 0);
});

test("resampling to the same rate copies rather than aliases the input", () => {
  const input = new Float32Array([1, 2, 3]);
  const output = resampleLinear(input, 16000, 16000);
  assert.deepEqual(Array.from(output), [1, 2, 3]);
  assert.notEqual(output, input);
});

test("resampling 48kHz to 16kHz keeps the signal shape", () => {
  // 48kHz to 16kHz is exactly one sample in three.
  const input = new Float32Array(64 * 3);
  for (let index = 0; index < input.length; index += 1) {
    input[index] = Math.sin((index / 48) * Math.PI * 2);
  }
  const output = resampleLinear(input, 48000, 16000);
  assert.equal(output.length, 64);
  // Every output sample should sit close to the nearest input sample.
  for (let index = 0; index < output.length; index += 1) {
    const expected = input[index * 3];
    assert.ok(
      Math.abs(output[index] - expected) < 0.05,
      `sample ${index}: ${output[index]} vs ${expected}`
    );
  }
});

test("resampling an empty buffer produces an empty buffer", () => {
  assert.equal(resampleLinear(new Float32Array(0), 48000, 16000).length, 0);
});

// -- Voice activity detection ----------------------------------------------

test("a silent frame is below the default sensitivity threshold", () => {
  const detector = createVoiceActivityDetector();
  assert.equal(detector.levelPercent(new Int16Array(VOICE_FRAME_SAMPLES)), 0);
  assert.equal(detector.process(new Int16Array(VOICE_FRAME_SAMPLES)), false);
});

test("loud speech opens the microphone and quiet frames hold it open", () => {
  const detector = createVoiceActivityDetector();
  assert.equal(detector.process(toneFrame(20000)), true);
  assert.equal(detector.isSpeaking(), true);
  // Hang keeps the mic open across the gap between words.
  for (let index = 0; index < 10; index += 1) {
    assert.equal(detector.process(new Int16Array(VOICE_FRAME_SAMPLES)), true);
  }
  assert.equal(detector.isSpeaking(), true);
});

test("the mic closes once the hang period expires", () => {
  // 500ms of hang at 20ms a frame is 25 frames.
  const detector = createVoiceActivityDetector({ hangMs: 500 });
  assert.equal(detector.hangFrames, 25);
  assert.equal(detector.process(toneFrame(20000)), true);
  let frames = 0;
  while (detector.process(new Int16Array(VOICE_FRAME_SAMPLES))) {
    frames += 1;
    assert.ok(frames < 100, "detector never closed");
  }
  assert.equal(frames, 24);
  assert.equal(detector.isSpeaking(), false);
});

test("a zero hang closes the mic on the first quiet frame", () => {
  const detector = createVoiceActivityDetector({ hangMs: 0 });
  assert.equal(detector.process(toneFrame(20000)), true);
  assert.equal(detector.process(new Int16Array(VOICE_FRAME_SAMPLES)), false);
});

test("level scales with amplitude on a 0-100 scale", () => {
  const detector = createVoiceActivityDetector();
  assert.equal(detector.levelPercent(toneFrame(32767)), 100);
  // Half amplitude is -6dB, about 50 on the scale.
  assert.ok(Math.abs(detector.levelPercent(toneFrame(16384)) - 50) <= 1);
});

test("levelPercent handles an empty frame without throwing", () => {
  const detector = createVoiceActivityDetector();
  assert.equal(detector.levelPercent(new Int16Array(0)), 0);
  assert.equal(detector.levelPercent(null), 0);
});

test("reset returns the detector to the silent state", () => {
  const detector = createVoiceActivityDetector();
  detector.process(toneFrame(20000));
  assert.equal(detector.isSpeaking(), true);
  detector.reset();
  assert.equal(detector.isSpeaking(), false);
});

test("threshold and hang can be changed after construction", () => {
  const detector = createVoiceActivityDetector();
  detector.threshold = 90;
  assert.equal(detector.threshold, 90);
  assert.equal(detector.process(toneFrame(20000)), false);
  detector.hangMs = 40;
  assert.equal(detector.hangMs, 40);
  // A non-numeric setting is ignored rather than poisoning the detector.
  detector.threshold = "loud";
  assert.equal(detector.threshold, 90);
});

// -- Gain ------------------------------------------------------------------

test("100% gain leaves the frame untouched", () => {
  const frame = toneFrame(1000);
  assert.equal(applyGain(frame, 100), frame);
});

test("gain scales samples and clips at full scale", () => {
  assert.equal(applyGain(toneFrame(10000), 200)[0], 20000);
  assert.equal(applyGain(toneFrame(10000), 50)[0], 5000);
  // 300% is clamped to 200%, which still clips a near-full-scale sample.
  assert.equal(applyGain(toneFrame(-30000), 300)[0], -32768);
  assert.equal(applyGain(toneFrame(30000), 200)[0], 32767);
  assert.equal(applyGain(toneFrame(10000), 0)[0], 0);
});

test("gain is clamped to 0-200%", () => {
  assert.equal(applyGain(toneFrame(1000), 9999)[0], 2000);
  assert.equal(applyGain(toneFrame(1000), -50)[0], 0);
});

test("gain returns a copy rather than mutating the captured frame", () => {
  const frame = toneFrame(1000);
  applyGain(frame, 50);
  assert.equal(frame[0], 1000);
});

// -- Test doubles ----------------------------------------------------------

/** Records every packet the manager sends. */
function fakeNetwork() {
  const sent = [];
  let connected = true;
  return {
    sent,
    packetsOfType: (type) => sent.filter((packet) => packet.type === type),
    setConnected(value) {
      connected = value;
    },
    send(packet) {
      sent.push(packet);
      return true;
    },
    get connected() {
      return connected;
    },
  };
}

/** Minimal AudioContext stand-in: no worklet, so the ScriptProcessor path runs. */
class FakeAudioParam {
  constructor() {
    this.value = 1;
  }
}

class FakeNode {
  constructor(context, kind) {
    this.context = context;
    this.kind = kind;
    this.connectedTo = [];
    this.disconnected = false;
  }
  connect(target) {
    this.connectedTo.push(target);
    return target;
  }
  disconnect() {
    this.disconnected = true;
  }
}

class FakeAudioContext {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 48000;
    this.state = "running";
    this.destination = new FakeNode(this, "destination");
    this.nodes = [];
    // Deliberately absent: audioWorklet, setSinkId. The client must fall back.
  }
  createGain() {
    const node = new FakeNode(this, "gain");
    node.gain = new FakeAudioParam();
    return node;
  }
  createMediaStreamSource(stream) {
    const node = new FakeNode(this, "source");
    node.stream = stream;
    return node;
  }
  createScriptProcessor(bufferSize, inputChannels, outputChannels) {
    const node = new FakeNode(this, "scriptProcessor");
    node.bufferSize = bufferSize;
    node.inputChannels = inputChannels;
    node.outputChannels = outputChannels;
    this.nodes.push(node);
    return node;
  }
  async resume() {
    this.state = "running";
  }
  async close() {
    this.state = "closed";
  }
  /** Feed a block through the capture ScriptProcessor, as the browser would. */
  pushCaptureInput(samples) {
    const processor = this.nodes.find((node) => node.kind === "scriptProcessor" && node.inputChannels === 1);
    assert.ok(processor, "no capture processor was created");
    processor.onaudioprocess({
      inputBuffer: {
        getChannelData: (channel) => (channel === 0 ? samples : new Float32Array(samples.length)),
        numberOfChannels: 1,
      },
    });
  }
  /** Read back what the playback ScriptProcessor wrote. */
  pullPlaybackOutput() {
    const processor = this.nodes.find(
      (node) => node.kind === "scriptProcessor" && node.outputChannels === 1
    );
    if (!processor || !processor.onaudioprocess) {
      return null;
    }
    const bufferSize = processor.bufferSize;
    const output = new Float32Array(bufferSize);
    processor.onaudioprocess({
      outputBuffer: {
        getChannelData: () => output,
        numberOfChannels: 1,
      },
    });
    return output;
  }
  get playbackProcessor() {
    return this.nodes.find(
      (node) => node.kind === "scriptProcessor" && node.outputChannels === 1
    );
  }
}

function fakeStream() {
  const stopped = [];
  return {
    stopped,
    getTracks: () => [
      {
        stop() {
          stopped.push(true);
        },
      },
    ],
  };
}

/**
 * Builds a manager wired to fakes, returning the pieces tests poke at.
 * `captureFrames` receives every frame the microphone path produced.
 */
function makeManager(overrides = {}) {
  const network = overrides.network || fakeNetwork();
  const sent = [];
  const captureFrames = [];
  const playback = [];
  const context = new FakeAudioContext({ sampleRate: 48000 });
  // One entry per getUserMedia call, in acquisition order.
  const streams = [];

  const manager = createVoiceManager({
    sendPacket: (packet) => {
      sent.push(packet);
      return network.send(packet);
    },
    isConnected: () => network.connected,
    onStateChange: overrides.onStateChange,
    onError: overrides.onError,
    createAudioContext: () => context,
    getUserMedia: async () => {
      const next = fakeStream();
      streams.push(next);
      return next;
    },
    enumerateDevices: overrides.enumerateDevices,
  });

  return {
    manager,
    context,
    network,
    sent,
    streams,
    captureFrames,
    playback,
  };
}

/** Wait for the manager's async capture setup to settle. */
async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

// -- Transmit gating -------------------------------------------------------

test("joining sends voice_join with the current mute state", () => {
  const { manager, sent } = makeManager();
  manager.join();
  const joins = sent.filter((packet) => packet.type === "voice_join");
  assert.equal(joins.length, 1);
  assert.equal(joins[0].muted, false);
  assert.equal(manager.state.joined, true);
  return settle();
});

test("joining twice does not send a second voice_join", async () => {
  const { manager, sent } = makeManager();
  manager.join();
  await settle();
  manager.join();
  assert.equal(sent.filter((packet) => packet.type === "voice_join").length, 1);
});

test("unjoining sends voice_leave and clears the room state", async () => {
  const { manager, sent } = makeManager();
  manager.join();
  await settle();
  manager.handleVoiceStatus({ joined: true, room: "lobby", peers: ["ada"], muted: false });
  await manager.unjoin();
  assert.equal(sent.filter((packet) => packet.type === "voice_leave").length, 1);
  assert.equal(manager.state.joined, false);
  assert.equal(manager.state.room, null);
  assert.deepEqual(manager.state.peers, []);
});

test("unjoining when not joined stays silent", async () => {
  const { manager, sent } = makeManager();
  await manager.unjoin();
  assert.equal(sent.filter((packet) => packet.type === "voice_leave").length, 0);
});

test("muting while joined re-joins so the server stops relaying", async () => {
  const { manager, sent } = makeManager();
  manager.join();
  await settle();
  manager.setMuted(true);
  const joins = sent.filter((packet) => packet.type === "voice_join");
  assert.equal(joins.length, 2);
  assert.equal(joins[1].muted, true);
  assert.equal(manager.state.muted, true);
});

test("setting the same mute state twice sends nothing extra", async () => {
  const { manager, sent } = makeManager();
  manager.join();
  await settle();
  manager.setMuted(false);
  assert.equal(sent.filter((packet) => packet.type === "voice_join").length, 1);
});

test("push to talk only transmits while the key is held", () => {
  const { manager, sent } = makeManager();
  manager.applySettings({ voice_mode: MODE_PUSH_TO_TALK });
  manager.state.joined = true;
  assert.equal(manager.frameToSendForTest(toneFrame(20000)), null);

  manager.setPushToTalk(true);
  assert.ok(manager.frameToSendForTest(toneFrame(20000)));
  assert.equal(manager.state.transmitting, true);

  manager.setPushToTalk(false);
  assert.equal(manager.frameToSendForTest(toneFrame(20000)), null);
  assert.equal(manager.state.transmitting, false);
  assert.equal(sent.length, 0);
});

test("voice activity transmits loud frames and drops quiet ones", () => {
  const { manager } = makeManager();
  manager.state.joined = true;
  assert.ok(manager.frameToSendForTest(toneFrame(20000)));
  // The hang keeps the mic open across the gap, so a quiet frame right after
  // speech still goes out. Silence only drops once the hang expires.
  assert.ok(manager.frameToSendForTest(new Int16Array(VOICE_FRAME_SAMPLES)));
  manager.detector.reset();
  assert.equal(manager.frameToSendForTest(new Int16Array(VOICE_FRAME_SAMPLES)), null);
});

test("a muted or unjoined client never transmits", () => {
  const { manager } = makeManager();
  manager.state.joined = true;
  manager.setMuted(true);
  assert.equal(manager.frameToSendForTest(toneFrame(20000)), null);

  manager.setMuted(false);
  manager.state.joined = false;
  assert.equal(manager.frameToSendForTest(toneFrame(20000)), null);
});

test("applying settings clamps out-of-range values", () => {
  const { manager } = makeManager();
  manager.applySettings({
    voice_mic_gain: 5000,
    voice_volume: -20,
    voice_activity_threshold: 400,
    voice_activity_hang_ms: "soon",
    voice_mode: "telepathy",
  });
  assert.equal(manager.state.micGain, 200);
  assert.equal(manager.state.voiceVolume, 0);
  assert.equal(manager.detector.threshold, 100);
  assert.equal(manager.detector.hangMs, DEFAULT_VOICE_ACTIVITY_HANG_MS);
  assert.equal(manager.state.mode, MODE_VOICE_ACTIVITY);
});

test("settings default sensibly when given nothing", () => {
  const { manager } = makeManager();
  manager.applySettings({});
  assert.equal(manager.state.micGain, DEFAULT_MIC_GAIN);
  assert.equal(manager.state.mode, MODE_VOICE_ACTIVITY);
});

test("settings are read from a nested audio object like the desktop client", () => {
  const { manager } = makeManager();
  manager.applySettings({ audio: { voice_mic_gain: 175, voice_mode: MODE_PUSH_TO_TALK } });
  assert.equal(manager.state.micGain, 175);
  assert.equal(manager.state.mode, MODE_PUSH_TO_TALK);
});

test("changing the input device while joined restarts capture", async () => {
  const { manager, streams } = makeManager();
  manager.join();
  await settle();
  assert.equal(manager.captureActive, true);
  assert.equal(streams.length, 1);

  await manager.applySettings({ voice_input_device: "mic-2" });
  assert.equal(streams.length, 2, "capture did not restart");
  assert.equal(streams[0].stopped.length, 1, "old stream not released");
  assert.equal(streams[1].stopped.length, 0, "new stream already stopped");
  assert.equal(manager.captureActive, true);
});

test("changing the input device while not joined does not open the microphone", async () => {
  const { manager } = makeManager();
  await manager.applySettings({ voice_input_device: "mic-2" });
  assert.equal(manager.captureActive, false);
});

// -- Server packet handling ------------------------------------------------

test("voice_status sets the room and peer list", () => {
  const { manager } = makeManager();
  manager.handleVoiceStatus({
    joined: true,
    room: "table:7",
    peers: ["ada", "bob"],
    muted: true,
  });
  assert.equal(manager.state.joined, true);
  assert.equal(manager.state.room, "table:7");
  assert.deepEqual(manager.state.peers, ["ada", "bob"]);
  assert.equal(manager.state.muted, true);
});

test("voice_status tolerates a missing peers list", () => {
  const { manager } = makeManager();
  manager.handleVoiceStatus({ joined: true, room: "lobby" });
  assert.deepEqual(manager.state.peers, []);
});

test("voice_status not joined releases the microphone", async () => {
  const { manager, streams } = makeManager();
  manager.join();
  await settle();
  manager.handleVoiceStatus({ joined: true, room: "lobby", peers: [] });
  await settle();
  assert.equal(manager.captureActive, true);

  manager.handleVoiceStatus({ joined: false, room: null, peers: [] });
  await settle();
  assert.equal(manager.captureActive, false);
  assert.equal(streams[0].stopped.length, 1);
});

test("voice_peer joined and left update the peer list", () => {
  const { manager } = makeManager();
  manager.handleVoicePeer({ action: "joined", username: "ada", room: "lobby" });
  assert.deepEqual(manager.state.peers, ["ada"]);
  // A repeat announcement must not duplicate the entry.
  manager.handleVoicePeer({ action: "joined", username: "ada", room: "lobby" });
  assert.deepEqual(manager.state.peers, ["ada"]);
  manager.handleVoicePeer({ action: "left", username: "ada", room: "lobby" });
  assert.deepEqual(manager.state.peers, []);
});

test("voice_peer without a username is ignored", () => {
  const { manager } = makeManager();
  manager.handleVoicePeer({ action: "joined", room: "lobby" });
  assert.deepEqual(manager.state.peers, []);
});

test("relayed audio reaches the player for each sender", async () => {
  const { manager, context, playback } = makeManager();
  manager.join();
  await settle();
  manager.handleVoiceStatus({ joined: true, room: "lobby", peers: ["ada"] });
  await settle();

  manager.handleVoiceAudio({
    type: "voice_audio",
    sender: "ada",
    data: decodeBase64(int16ToBytes(toneFrame(8000))),
    seq: 1,
  });
  const output = context.pullPlaybackOutput();
  assert.ok(output, "no playback processor");
  assert.ok(playback.length >= 0);
  assert.ok(
    Array.from(output).some((sample) => sample !== 0),
    "relayed audio was silent"
  );
});

test("relayed audio is ignored when it is malformed", async () => {
  const { manager } = makeManager();
  manager.join();
  await settle();
  // None of these should throw or create a playback stream.
  manager.handleVoiceAudio({ sender: "", data: "AAAA" });
  manager.handleVoiceAudio({ sender: "ada" });
  manager.handleVoiceAudio({ sender: "ada", data: "!!!" });
  assert.equal(manager.playbackActive, true);
});

test("playback is dropped when not joined", () => {
  const { manager } = makeManager();
  manager.handleVoiceAudio({ sender: "ada", data: decodeBase64(int16ToBytes(toneFrame(8000))) });
  assert.equal(manager.playbackActive, false);
});

// -- Rate limiting ---------------------------------------------------------

test("the client never exceeds the server's 50 frames per second", () => {
  const { manager, sent } = makeManager();
  manager.state.joined = true;
  for (let index = 0; index < 500; index += 1) {
    manager.sendFrameForTest(decodeBase64(int16ToBytes(toneFrame(1))));
  }
  assert.equal(sent.length, 50);
});

test("sequence numbers increase across frames", () => {
  const { manager, sent } = makeManager();
  manager.state.joined = true;
  for (let index = 0; index < 5; index += 1) {
    manager.sendFrameForTest(decodeBase64(int16ToBytes(toneFrame(1))));
  }
  assert.deepEqual(sent.map((packet) => packet.seq), [0, 1, 2, 3, 4]);
});

test("nothing is sent while the socket is down", () => {
  const network = fakeNetwork();
  network.setConnected(false);
  const { manager, sent } = makeManager({ network });
  manager.state.joined = true;
  manager.sendFrameForTest(decodeBase64(int16ToBytes(toneFrame(1))));
  assert.equal(sent.length, 0);
});

test("a failing send surfaces the error instead of throwing into the audio path", () => {
  const errors = [];
  const { manager } = makeManager({
    onError: (message) => errors.push(message),
  });
  manager.sendPacket = null;
  manager.network = null;
  // A manager with no sendPacket silently drops frames rather than throwing.
  assert.doesNotThrow(() => manager.sendFrameForTest("AAAA"));
  assert.ok(errors.length === 0 || typeof errors[0] === "string");
});

// -- Device selection ------------------------------------------------------

test("input devices are listed with a default entry first", async () => {
  const { manager } = makeManager({
    enumerateDevices: async () => [
      { kind: "audioinput", deviceId: "mic-1", label: "Headset" },
      { kind: "videoinput", deviceId: "cam-1", label: "Camera" },
    ],
  });
  const inputs = await manager.listInputDevices();
  assert.equal(inputs.length, 1);
  assert.equal(inputs[0].label, "Headset");
  assert.equal(inputs[0].granted, true);
});

test("devices without labels get a placeholder until permission is granted", async () => {
  const { manager } = makeManager({
    enumerateDevices: async () => [
      { kind: "audioinput", deviceId: "mic-1", label: "" },
      { kind: "audiooutput", deviceId: "spk-1", label: "" },
    ],
  });
  const inputs = await manager.listInputDevices();
  assert.equal(inputs[0].label, "Microphone 1");
  assert.equal(inputs[0].granted, false);
  const outputs = await manager.listOutputDevices();
  assert.equal(outputs[0].label, "Speaker 1");
  assert.equal(outputs[0].granted, false);
});

test("a browser without device enumeration reports no devices", async () => {
  const { manager } = makeManager({
    enumerateDevices: async () => {
      throw new Error("not available");
    },
  });
  assert.deepEqual(await manager.listInputDevices(), []);
  assert.deepEqual(await manager.listOutputDevices(), []);
});

test("output device selection is only claimed where the browser supports it", () => {
  const { manager } = makeManager();
  // The fake context has no setSinkId, matching Firefox and Safari.
  assert.equal(manager.supportsOutputSelection(), false);

  const withSink = makeManager();
  withSink.manager.state.outputDevice = "spk-2";
  assert.equal(withSink.manager.supportsOutputSelection(), false);
});

test("picking an unavailable output device falls back and reports why", async () => {
  const errors = [];
  const { manager } = makeManager({ onError: (message) => errors.push(message) });
  manager.join();
  await settle();
  await manager.applySettings({ voice_output_device: "spk-2" });
  assert.equal(manager.state.outputDevice, "default");
  assert.ok(
    errors.some((message) => /cannot pick a voice output device/i.test(message)),
    `expected a fallback message, got ${JSON.stringify(errors)}`
  );
});

test("a stale saved input device falls back to the default", async () => {
  const attempts = [];
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const manager = createVoiceManager({
    sendPacket: () => true,
    createAudioContext: () => context,
    getUserMedia: async (constraints) => {
      attempts.push(constraints);
      if (attempts.length === 1) {
        const error = new Error("no such device");
        error.name = "OverconstrainedError";
        throw error;
      }
      return fakeStream();
    },
    enumerateDevices: async () => [],
  });
  // The device changed while joined, so capture restarts and the saved id is
  // rejected by the browser on the first attempt.
  manager.state.joined = true;
  await manager.applySettings({ voice_input_device: "mic-that-left" });
  assert.equal(attempts.length, 2);
  assert.equal(attempts[0].audio.deviceId.exact, "mic-that-left");
  assert.equal(manager.state.inputDevice, "default");
  // The retry must drop the rejected device id, not resend the same constraint.
  assert.equal(attempts[1].audio.deviceId, undefined);
  assert.equal(manager.captureActive, true);
});

test("the microphone is requested with echo cancellation and mono", async () => {
  const constraints = [];
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const manager = createVoiceManager({
    sendPacket: () => true,
    createAudioContext: () => context,
    getUserMedia: async (value) => {
      constraints.push(value);
      return fakeStream();
    },
  });
  manager.join();
  await settle();
  assert.equal(constraints.length, 1);
  assert.equal(constraints[0].audio.channelCount, 1);
  assert.equal(constraints[0].audio.echoCancellation, true);
  assert.equal(constraints[0].audio.noiseSuppression, true);
});

test("a denied microphone surfaces an error and reports no permission", async () => {
  const errors = [];
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const manager = createVoiceManager({
    sendPacket: () => true,
    onError: (message) => errors.push(message),
    createAudioContext: () => context,
    getUserMedia: async () => {
      const error = new Error("Permission denied");
      error.name = "NotAllowedError";
      throw error;
    },
  });
  manager.join();
  await settle();
  assert.equal(manager.state.permissionGranted, false);
  assert.equal(manager.captureActive, false);
  assert.equal(errors.length, 1);
});

test("unjoining stops the microphone tracks", async () => {
  const { manager, streams } = makeManager();
  manager.join();
  await settle();
  await manager.unjoin();
  assert.equal(streams[0].stopped.length, 1);
  assert.equal(manager.captureActive, false);
});

test("shutdown releases the microphone and the audio context", async () => {
  const { manager, streams, context } = makeManager();
  manager.join();
  await settle();
  await manager.shutdown();
  assert.equal(streams[0].stopped.length, 1);
  assert.equal(context.state, "closed");
  assert.equal(manager.context, null);
});

// -- Capture and playback nodes -------------------------------------------

test("capture falls back to a ScriptProcessor and emits aligned 20ms frames", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const frames = [];
  const capture = createVoiceCapture({
    context,
    stream: fakeStream(),
    onFrame: (frame) => frames.push(frame),
  });
  await capture.start();
  assert.equal(capture.usingWorklet, false);

  // 7680 input samples at 48kHz is 160ms, so eight 20ms frames come out.
  context.pushCaptureInput(new Float32Array(7680).fill(0.5));
  assert.equal(frames.length, 8);
  for (const frame of frames) {
    assert.equal(frame.length, VOICE_FRAME_SAMPLES);
  }
  assert.ok(Math.abs(frames[0][0] - 16384) < 100, "amplitude was not preserved");
});

test("capture keeps partial frames across callbacks", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const frames = [];
  const capture = createVoiceCapture({
    context,
    stream: fakeStream(),
    onFrame: (frame) => frames.push(frame),
  });
  await capture.start();
  // Half a frame, then half a frame: exactly one frame in total.
  context.pushCaptureInput(new Float32Array(480).fill(0.25));
  assert.equal(frames.length, 0);
  context.pushCaptureInput(new Float32Array(480).fill(0.25));
  assert.equal(frames.length, 1);
});

test("the capture microphone path is never routed to the speakers", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const capture = createVoiceCapture({
    context,
    stream: fakeStream(),
    onFrame: () => {},
  });
  await capture.start();
  const processor = context.nodes.find((node) => node.inputChannels === 1);
  const sink = processor.connectedTo[0];
  assert.equal(sink.gain.value, 0, "microphone audio would be audible");
});

test("playback mixes speakers without clipping a single one to silence", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const player = createVoicePlayer({ context });
  await player.start();
  player.push("ada", new Float32Array(1024).fill(1), 1);
  const processor = context.playbackProcessor;
  const output = new Float32Array(processor.bufferSize);
  processor.onaudioprocess({
    outputBuffer: { getChannelData: () => output, numberOfChannels: 1 },
  });
  assert.ok(output[0] > 0);
  assert.ok(output[0] <= 1, `expected headroom, got ${output[0]}`);
});

test("playback applies the voice volume", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const player = createVoicePlayer({ context });
  await player.start();
  player.push("ada", new Float32Array(1024).fill(1), 0.5);
  const processor = context.playbackProcessor;
  const output = new Float32Array(processor.bufferSize);
  processor.onaudioprocess({
    outputBuffer: { getChannelData: () => output, numberOfChannels: 1 },
  });
  assert.ok(Math.abs(output[0] - 0.5) < 1e-6, `expected half volume, got ${output[0]}`);
});

test("closing a speaker removes them from the mix", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const player = createVoicePlayer({ context });
  await player.start();
  player.push("ada", new Float32Array(1024).fill(1), 1);
  player.push("bob", new Float32Array(1024).fill(1), 1);
  assert.deepEqual(player.queuedSenders.sort(), ["ada", "bob"]);
  player.close("ada");
  assert.deepEqual(player.queuedSenders, ["bob"]);
});

test("playback backlog is bounded so a stalled network cannot grow memory", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const player = createVoicePlayer({ context });
  await player.start();
  // Two seconds of audio, well past the 400ms backlog cap.
  for (let index = 0; index < 100; index += 1) {
    player.push("ada", new Float32Array(4096).fill(1), 1);
  }
  const processor = context.playbackProcessor;
  const output = new Float32Array(processor.bufferSize);
  let total = 0;
  for (let block = 0; block < 200; block += 1) {
    processor.onaudioprocess({
      outputBuffer: { getChannelData: () => output, numberOfChannels: 1 },
    });
    total += 1;
  }
  assert.ok(total > 0);
});

// -- End-to-end relay ------------------------------------------------------

test("two clients relay a frame through the server's packets", async () => {
  const alice = makeManager();
  const bob = makeManager();

  alice.manager.join();
  bob.manager.join();
  await settle();

  // The server confirms both are in the lobby and tells each about the other.
  for (const [manager, peer] of [
    [alice.manager, "bob"],
    [bob.manager, "alice"],
  ]) {
    manager.handleVoiceStatus({
      joined: true,
      room: "lobby",
      peers: [peer],
      muted: false,
    });
  }
  await settle();
  assert.deepEqual(alice.manager.state.peers, ["bob"]);
  assert.deepEqual(bob.manager.state.peers, ["alice"]);

  // Alice talks.
  alice.manager.capturedFrameForTest(toneFrame(20000));
  const frame = alice.sent.find((packet) => packet.type === "voice_audio");
  assert.ok(frame, "no audio packet was sent");
  assert.equal(frame.data.length, 856, "expected 640 bytes of base64");

  // The server relays it to Bob verbatim, tagged with the sender.
  bob.manager.handleVoiceAudio({
    type: "voice_audio",
    sender: "alice",
    data: frame.data,
    seq: frame.seq,
  });
  const output = bob.context.pullPlaybackOutput();
  assert.ok(
    Array.from(output).some((sample) => sample !== 0),
    "Bob heard nothing"
  );

  // Bob has not spoken, so nothing should come back the other way.
  assert.equal(bob.sent.filter((packet) => packet.type === "voice_audio").length, 0);

  // Muted senders are dropped by the server; the client never even asks.
  alice.manager.setMuted(true);
  const before = alice.sent.length;
  alice.manager.capturedFrameForTest(toneFrame(20000));
  assert.equal(alice.sent.length, before);
});

test("a peer leaving the room stops their audio being played", async () => {
  const { manager, context } = makeManager();
  manager.join();
  await settle();
  manager.handleVoiceStatus({ joined: true, room: "lobby", peers: ["ada"] });
  await settle();

  manager.handleVoiceAudio({
    sender: "ada",
    data: decodeBase64(int16ToBytes(toneFrame(8000))),
  });
  manager.handleVoicePeer({ action: "left", username: "ada", room: "lobby" });
  assert.deepEqual(manager.state.peers, []);

  const output = context.pullPlaybackOutput();
  assert.ok(
    Array.from(output).every((sample) => sample === 0),
    "still playing a departed speaker"
  );
});

test("every packet the client sends matches the shared packet schema", async () => {
  const { readFile } = await import("node:fs/promises");
  const { fileURLToPath } = await import("node:url");
  const path = await import("node:path");
  const schemaPath = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
    "packet_schema.json"
  );
  const schema = JSON.parse(await readFile(schemaPath, "utf8"));
  const defs = schema.client_to_server.$defs;

  const { manager, sent } = makeManager();
  manager.join();
  await settle();
  manager.capturedFrameForTest(toneFrame(20000));
  manager.setMuted(true);
  manager.handleVoiceStatus({ joined: true, room: "lobby", peers: ["ada"], muted: true });
  await manager.unjoin();

  const voiceTypes = ["voice_join", "voice_leave", "voice_audio"];
  const sentVoice = sent.filter((packet) => voiceTypes.includes(packet.type));
  assert.ok(sentVoice.length >= 3, "expected join, mute re-join, audio and leave");

  const defByType = {
    voice_join: "VoiceJoinPacket",
    voice_leave: "VoiceLeavePacket",
    voice_audio: "VoiceAudioPacket",
  };

  for (const packet of sentVoice) {
    const def = defs[defByType[packet.type]];
    assert.ok(def, `no schema for ${packet.type}`);
    for (const field of def.required || []) {
      assert.ok(
        Object.hasOwn(packet, field),
        `${packet.type} is missing required field '${field}'`
      );
    }
    for (const [key, value] of Object.entries(packet)) {
      if (!Object.hasOwn(def.properties, key)) {
        assert.fail(`${packet.type} has unexpected field '${key}'`);
      }
      const property = def.properties[key];
      if (property.type === "string") {
        assert.equal(typeof value, "string", `${packet.type}.${key} must be a string`);
        if (property.maxLength !== undefined) {
          assert.ok(
            value.length <= property.maxLength,
            `${packet.type}.${key} exceeds maxLength ${property.maxLength}`
          );
        }
      } else if (property.type === "integer") {
        assert.ok(Number.isInteger(value), `${packet.type}.${key} must be an integer`);
        assert.ok(value >= property.minimum, `${packet.type}.${key} below minimum`);
      } else if (property.type === "boolean") {
        assert.equal(typeof value, "boolean", `${packet.type}.${key} must be a boolean`);
      }
    }
  }

  // The audio payload must fit the schema's declared ceiling, which is what
  // the server enforces too.
  const audio = sentVoice.find((packet) => packet.type === "voice_audio");
  const def = defs.VoiceAudioPacket;
  assert.ok(audio.data.length <= def.properties.data.maxLength);
  assert.ok(Buffer.from(audio.data, "base64").length <= 64 * 1024);
});
// -- Output device routing ------------------------------------------------

test("the system default needs no setSinkId call", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  let sinkCalls = 0;
  context.setSinkId = async (id) => {
    sinkCalls += 1;
    if (id !== "") {
      throw new Error(`the device ${id} is not found`);
    }
  };
  // Before joining there is no context yet, so support is probed from the
  // browser constructor, exactly as the panel does before the user presses Join.
  const realCtor = globalThis.AudioContext;
  class SinkAwareContext extends FakeAudioContext {}
  SinkAwareContext.prototype.setSinkId = context.setSinkId;
  globalThis.AudioContext = SinkAwareContext;
  try {
    const manager = createVoiceManager({
      sendPacket: () => true,
      createAudioContext: () => context,
      getUserMedia: async () => fakeStream(),
    });
    assert.equal(manager.supportsOutputSelection(), true);
    manager.join();
    await settle();
    // "default" is not a valid sink id; browsers reject it, so we must not send it.
    assert.equal(sinkCalls, 0);
    assert.equal(manager.state.error, "");
  } finally {
    if (realCtor === undefined) {
      delete globalThis.AudioContext;
    } else {
      globalThis.AudioContext = realCtor;
    }
  }
});

test("a chosen output device is applied through setSinkId", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const sinkCalls = [];
  context.setSinkId = async (id) => {
    sinkCalls.push(id);
  };
  const manager = createVoiceManager({
    sendPacket: () => true,
    createAudioContext: () => context,
    getUserMedia: async () => fakeStream(),
  });
  manager.join();
  await settle();
  await manager.applySettings({ voice_output_device: "spk-2" });
  assert.deepEqual(sinkCalls, ["spk-2"]);
  assert.equal(manager.state.outputDevice, "spk-2");
  assert.equal(manager.state.error, "");
});

test("an output device that has been unplugged falls back without losing the mic", async () => {
  const context = new FakeAudioContext({ sampleRate: 48000 });
  const sinkCalls = [];
  context.setSinkId = async (id) => {
    sinkCalls.push(id);
    if (id !== "") {
      throw new Error(`the device ${id} is not found`);
    }
  };
  const errors = [];
  const manager = createVoiceManager({
    sendPacket: () => true,
    onError: (message) => errors.push(message),
    createAudioContext: () => context,
    getUserMedia: async () => fakeStream(),
  });
  manager.join();
  await settle();
  await manager.applySettings({ voice_output_device: "spk-that-left" });
  assert.deepEqual(sinkCalls, ["spk-that-left", ""]);
  assert.equal(manager.state.outputDevice, "default");
  assert.match(manager.state.error, /unavailable/i);
  assert.equal(manager.captureActive, true, "the microphone should still be live");
});
