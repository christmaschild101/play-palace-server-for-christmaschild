// Voice chat for the PlayPalace web client.
//
// This mirrors clients/desktop/voice_manager.py: the same wire format, the same
// transmit gating (voice activity or push to talk), the same gain clipping, and
// the same packet shapes. The server relay is unchanged, so a browser and a
// desktop client can sit in the same room and hear each other.
//
// Wire format (see server/network/packet_models.py):
//   16kHz mono signed 16-bit little-endian PCM, sliced into 20ms frames of
//   640 bytes, base64-encoded into a `voice_audio` packet. Nothing is stored.
//
// Every Web Audio object is created lazily and only while joined, and all of it
// is reachable through injectable options so the pure logic can be tested in
// Node without audio hardware.

export const VOICE_SAMPLE_RATE = 16000;
export const VOICE_CHANNELS = 1;
export const VOICE_SAMPLE_WIDTH = 2;
export const VOICE_FRAME_MS = 20;
export const VOICE_FRAME_SAMPLES = (VOICE_SAMPLE_RATE * VOICE_FRAME_MS) / 1000;
export const VOICE_FRAME_BYTES = VOICE_FRAME_SAMPLES * VOICE_SAMPLE_WIDTH; // 640

export const MODE_VOICE_ACTIVITY = "voice_activity";
export const MODE_PUSH_TO_TALK = "push_to_talk";

export const DEFAULT_MIC_GAIN = 100; // percent, 0-200
export const DEFAULT_VOICE_ACTIVITY_THRESHOLD = 15; // 0-100 scale
export const DEFAULT_VOICE_ACTIVITY_HANG_MS = 500;
export const DEFAULT_VOICE_VOLUME = 100; // percent, 0-200

// Device ids used when the user has not picked one. "default" is what
// getUserMedia and AudioContext both accept as "whatever the OS says".
export const DEFAULT_INPUT_DEVICE = "default";
export const DEFAULT_OUTPUT_DEVICE = "default";

// The server rate-limits a sender to 50 frames a second; a 20ms frame is
// exactly real time, so this only trims a stall rather than gating normal use.
export const MAX_FRAMES_PER_SECOND = 50;

// Playback is deliberately a little more generous than the send limit so a
// single late frame does not immediately become an audible gap.
export const MAX_PLAYBACK_BACKLOG_MS = 400;

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

/** Convert float samples in [-1, 1] to signed 16-bit, clipping at full scale. */
export function floatToInt16(input) {
  const samples = input instanceof Float32Array ? input : Float32Array.from(input);
  const out = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const value = samples[index];
    const scaled = value < 0 ? value * 0x8000 : value * 0x7fff;
    out[index] = scaled > 32767 ? 32767 : scaled < -32768 ? -32768 : Math.round(scaled);
  }
  return out;
}

/** Convert signed 16-bit samples back to float samples in [-1, 1]. */
export function int16ToFloat(input) {
  const samples = input instanceof Int16Array ? input : Int16Array.from(input);
  const out = new Float32Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    out[index] = samples[index] < 0 ? samples[index] / 0x8000 : samples[index] / 0x7fff;
  }
  return out;
}

/** Resample float samples with linear interpolation. */
export function resampleLinear(input, inputRate, outputRate) {
  if (inputRate === outputRate) {
    return input instanceof Float32Array ? input.slice() : Float32Array.from(input);
  }
  const source = input instanceof Float32Array ? input : Float32Array.from(input);
  if (source.length === 0) {
    return new Float32Array(0);
  }
  const ratio = inputRate / outputRate;
  const length = Math.max(1, Math.floor(source.length / ratio));
  const out = new Float32Array(length);
  for (let index = 0; index < length; index += 1) {
    const position = index * ratio;
    const base = Math.floor(position);
    const fraction = position - base;
    const current = source[base] ?? 0;
    const next = source[base + 1] ?? current;
    out[index] = current + (next - current) * fraction;
  }
  return out;
}

const BASE64_CHUNK = 0x8000;

/** Base64-encode raw bytes, chunked so large buffers do not blow the stack. */
export function bytesToBase64(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += BASE64_CHUNK) {
    const chunk = bytes.subarray(offset, offset + BASE64_CHUNK);
    binary += String.fromCharCode.apply(null, chunk);
  }
  return btoa(binary);
}

/** Base64-decode into a byte view, or null when the payload is not base64. */
export function base64ToBytes(text) {
  if (typeof text !== "string" || text.length === 0) {
    return null;
  }
  try {
    const binary = atob(text);
    const out = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      out[index] = binary.charCodeAt(index);
    }
    return out;
  } catch {
    return null;
  }
}

/** Decode a relayed frame into signed 16-bit samples, or null if malformed. */
export function decodeVoiceFrame(payload) {
  const bytes = base64ToBytes(payload);
  if (!bytes || bytes.length === 0) {
    return null;
  }
  // Copy into an aligned buffer: bytes.length may not be a multiple of 2.
  const usable = bytes.length - (bytes.length % VOICE_SAMPLE_WIDTH);
  if (usable <= 0) {
    return null;
  }
  const samples = new Int16Array(usable / VOICE_SAMPLE_WIDTH);
  const view = new DataView(bytes.buffer, bytes.byteOffset, usable);
  for (let index = 0; index < samples.length; index += 1) {
    samples[index] = view.getInt16(index * VOICE_SAMPLE_WIDTH, true);
  }
  return samples;
}

/**
 * Decides whether a frame of PCM should be transmitted.
 *
 * Uses RMS amplitude against a threshold, then holds the mic open for a hang
 * period so speech is not chopped between words.
 */
export function createVoiceActivityDetector({
  threshold = DEFAULT_VOICE_ACTIVITY_THRESHOLD,
  hangMs = DEFAULT_VOICE_ACTIVITY_HANG_MS,
} = {}) {
  let speaking = false;
  let framesSinceSpeech = 0;
  let hangFrames = hangFramesFor(hangMs);

  function hangFramesFor(ms) {
    return Math.max(1, Math.floor(Number(ms) / VOICE_FRAME_MS));
  }

  return {
    get threshold() {
      return threshold;
    },
    set threshold(value) {
      const numeric = Number(value);
      if (Number.isFinite(numeric)) {
        threshold = numeric;
      }
    },
    get hangMs() {
      return hangFrames * VOICE_FRAME_MS;
    },
    get hangFrames() {
      return hangFrames;
    },
    set hangMs(value) {
      const numeric = Number(value);
      if (Number.isFinite(numeric)) {
        hangFrames = hangFramesFor(numeric);
      }
    },
    reset() {
      speaking = false;
      framesSinceSpeech = 0;
    },
    isSpeaking() {
      return speaking;
    },
    levelPercent(frame) {
      const samples = frame instanceof Int16Array ? frame : Int16Array.from(frame || []);
      if (samples.length === 0) {
        return 0;
      }
      let total = 0;
      for (let index = 0; index < samples.length; index += 1) {
        total += samples[index] * samples[index];
      }
      // RMS of full-scale 16-bit audio is 32768.
      const rms = Math.sqrt(total / samples.length);
      return Math.min(100, Math.round((rms / 32768) * 100));
    },
    process(frame) {
      if (this.levelPercent(frame) >= threshold) {
        speaking = true;
        framesSinceSpeech = 0;
        return true;
      }
      framesSinceSpeech += 1;
      if (framesSinceSpeech >= hangFrames) {
        speaking = false;
      }
      return speaking;
    },
  };
}

/** Scale signed 16-bit samples by a percentage, clipping at full scale. */
export function applyGain(frame, gainPercent) {
  const samples = frame instanceof Int16Array ? frame : Int16Array.from(frame || []);
  const gain = Math.max(0, Math.min(200, Number(gainPercent))) / 100;
  if (gain === 1) {
    return samples;
  }
  const out = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const scaled = Math.round(samples[index] * gain);
    out[index] = scaled > 32767 ? 32767 : scaled < -32768 ? -32768 : scaled;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Capture
// ---------------------------------------------------------------------------

/**
 * Microphone capture.
 *
 * Preferred path is an AudioWorklet, which runs off the main thread and cannot
 * glitch the UI. Browsers without `audioWorklet` (or a blocked worklet module,
 * which happens under a strict CSP) fall back to a ScriptProcessorNode running
 * the same resampling on the main thread.
 */
export function createVoiceCapture({
  context,
  stream,
  workletUrl = new URL("./voice-worklet.js", import.meta.url).href,
  onFrame,
  onError = null,
} = {}) {
  let source = null;
  let node = null;
  let stopped = false;
  let useWorklet = false;
  // Partial samples carried between callbacks so frames stay 20ms aligned.
  let pending = new Float32Array(0);

  function emit(resampled) {
    // ``resampled`` is already at the wire rate, so every sample is one frame
    // sample and the only job here is cutting fixed-length frames.
    pending = concatFloat32(pending, resampled);
    while (pending.length >= VOICE_FRAME_SAMPLES) {
      const slice = pending.subarray(0, VOICE_FRAME_SAMPLES);
      pending = pending.slice(VOICE_FRAME_SAMPLES);
      onFrame(floatToInt16(slice));
    }
  }

  async function start() {
    source = context.createMediaStreamSource(stream);

    if (context.audioWorklet && typeof AudioWorkletNode === "function") {
      try {
        await context.audioWorklet.addModule(workletUrl);
        const workletNode = new AudioWorkletNode(context, "playpalace-voice-capture", {
          numberOfInputs: 1,
          numberOfOutputs: 0,
          channelCount: VOICE_CHANNELS,
        });
        workletNode.port.onmessage = (event) => {
          const message = event.data || {};
          if (message.type !== "frame") {
            return;
          }
          onFrame(new Int16Array(message.buffer));
        };
        source.connect(workletNode);
        node = workletNode;
        useWorklet = true;
        return;
      } catch (error) {
        // Fall through to the ScriptProcessor path.
        if (onError) {
          onError(error);
        }
      }
    }

    const processor = context.createScriptProcessor(1024, VOICE_CHANNELS, 1);
    processor.onaudioprocess = (event) => {
      if (stopped) {
        return;
      }
      emit(resampleLinear(event.inputBuffer.getChannelData(0), context.sampleRate, VOICE_SAMPLE_RATE));
    };
    source.connect(processor);
    // A ScriptProcessor only runs while connected to a destination; route it
    // through a muted gain so the microphone is never played back.
    const sink = context.createGain();
    sink.gain.value = 0;
    processor.connect(sink).connect(context.destination);
    node = processor;
    useWorklet = false;
  }

  function stop() {
    stopped = true;
    if (node && useWorklet) {
      try {
        node.port.postMessage({ type: "stop" });
      } catch {
        // The node may already be gone with its context.
      }
    }
    if (node && typeof node.onaudioprocess === "function") {
      node.onaudioprocess = null;
    }
    try {
      source?.disconnect();
    } catch {
      // Already disconnected.
    }
    try {
      node?.disconnect();
    } catch {
      // Already disconnected.
    }
    node = null;
    source = null;
    pending = new Float32Array(0);
  }

  return {
    start,
    stop,
    get usingWorklet() {
      return useWorklet;
    },
  };
}

function concatFloat32(left, right) {
  if (left.length === 0) {
    return right;
  }
  if (right.length === 0) {
    return left;
  }
  const out = new Float32Array(left.length + right.length);
  out.set(left, 0);
  out.set(right, left.length);
  return out;
}

// ---------------------------------------------------------------------------
// Playback
// ---------------------------------------------------------------------------

/**
 * Plays one relayed audio frame per remote speaker.
 *
 * Like capture, an AudioWorklet is preferred and a ScriptProcessorNode is the
 * fallback. Both keep a per-speaker queue so one lagging speaker cannot stall
 * the others.
 */
export function createVoicePlayer({
  context,
  workletUrl = new URL("./voice-worklet.js", import.meta.url).href,
} = {}) {
  const queues = new Map();
  let node = null;
  let useWorklet = false;
  let masterGain = null;
  let stopped = false;
  const maxQueueSamples = Math.ceil((context.sampleRate * MAX_PLAYBACK_BACKLOG_MS) / 1000);

  function queueFor(sender) {
    let queue = queues.get(sender);
    if (!queue) {
      queue = [];
      queue.samples = 0;
      queues.set(sender, queue);
    }
    return queue;
  }

  function enqueue(sender, samples, volume) {
    const queue = queueFor(sender);
    if (volume !== undefined) {
      queue.volume = Number(volume) || 0;
    }
    queue.push(samples);
    queue.samples += samples.length;
    while (queue.samples > maxQueueSamples && queue.length > 1) {
      queue.samples -= queue.shift().length;
    }
  }

  function drain(sender, length) {
    const queue = queues.get(sender);
    const out = new Float32Array(length);
    if (!queue) {
      return out;
    }
    let written = 0;
    while (written < length && queue.length > 0) {
      const chunk = queue[0];
      const take = Math.min(chunk.length, length - written);
      out.set(chunk.subarray(0, take), written);
      written += take;
      queue.samples -= take;
      if (take === chunk.length) {
        queue.shift();
      } else {
        queue[0] = chunk.slice(take);
      }
    }
    if (queue.length === 0 && queue.samples <= 0) {
      queues.delete(sender);
    }
    return out;
  }

  async function start() {
    masterGain = context.createGain();
    masterGain.gain.value = 1;
    masterGain.connect(context.destination);

    if (context.audioWorklet && typeof AudioWorkletNode === "function") {
      try {
        await context.audioWorklet.addModule(workletUrl);
        const workletNode = new AudioWorkletNode(context, "playpalace-voice-player", {
          numberOfInputs: 0,
          numberOfOutputs: 1,
          outputChannelCount: [VOICE_CHANNELS],
        });
        workletNode.port.onmessage = (event) => {
          const message = event.data || {};
          if (message.type === "close") {
            queues.delete(message.sender);
            return;
          }
          if (message.type === "frame") {
            enqueue(message.sender, new Float32Array(message.buffer));
          }
        };
        workletNode.connect(masterGain);
        node = workletNode;
        useWorklet = true;
        return;
      } catch {
        // Fall through to the ScriptProcessor path.
      }
    }

    const processor = context.createScriptProcessor(1024, 0, VOICE_CHANNELS);
    processor.onaudioprocess = (event) => {
      if (stopped) {
        return;
      }
      const output = event.outputBuffer.getChannelData(0);
      output.fill(0);
      const active = [...queues.keys()];
      if (active.length === 0) {
        return;
      }
      const headroom = 1 / Math.max(1, Math.sqrt(active.length));
      for (const sender of active) {
        const queue = queues.get(sender);
        if (!queue) {
          continue;
        }
        // Volume travels with the queue in this path; the worklet applies it
        // on the audio thread instead.
        const gain = (queue.volume ?? 1) * headroom;
        const samples = drain(sender, output.length);
        for (let index = 0; index < output.length; index += 1) {
          output[index] += samples[index] * gain;
        }
      }
    };
    node = processor;
    // A ScriptProcessor must reach a destination to run; the gain node is where
    // playback volume is applied, so send it straight there.
    node.connect(masterGain);
    useWorklet = false;
  }

  function push(sender, samples, volume = 1) {
    if (stopped) {
      return;
    }
    const sender_ = String(sender);
    if (useWorklet && node) {
      const copy = samples.slice();
      node.port.postMessage(
        { type: "frame", sender: sender_, buffer: copy.buffer, volume },
        [copy.buffer]
      );
      return;
    }
    enqueue(sender_, samples, volume);
  }

  function setVolume(volume) {
    if (!masterGain) {
      return;
    }
    const bounded = Math.max(0, Math.min(200, Number(volume))) / 100;
    masterGain.gain.value = bounded;
  }

  function close(sender) {
    if (sender === undefined) {
      queues.clear();
      return;
    }
    queues.delete(String(sender));
    if (useWorklet && node) {
      try {
        node.port.postMessage({ type: "close", sender: String(sender) });
      } catch {
        // Node already gone.
      }
    }
  }

  function stop() {
    stopped = true;
    if (node && useWorklet) {
      try {
        node.port.postMessage({ type: "stop" });
      } catch {
        // Node already gone.
      }
    }
    if (node && typeof node.onaudioprocess === "function") {
      node.onaudioprocess = null;
    }
    try {
      node?.disconnect();
    } catch {
      // Already disconnected.
    }
    try {
      masterGain?.disconnect();
    } catch {
      // Already disconnected.
    }
    node = null;
    masterGain = null;
    queues.clear();
  }

  return {
    start,
    stop,
    push,
    close,
    setVolume,
    get usingWorklet() {
      return useWorklet;
    },
    get queuedSenders() {
      return [...queues.keys()];
    },
  };
}

// ---------------------------------------------------------------------------
// Manager
// ---------------------------------------------------------------------------

/**
 * Owns microphone capture, transmit gating, and speaker playback.
 *
 * `sendPacket` is expected to be cheap and non-blocking (a websocket send), so
 * frames go out inline from the worklet callback: there is no audio thread here
 * to hand work off to, and inline keeps latency at one frame.
 */
export function createVoiceManager({
  sendPacket,
  isConnected = () => true,
  onStateChange = null,
  onError = null,
  createAudioContext = null,
  getUserMedia = null,
  enumerateDevices = null,
  workletUrl = undefined,
} = {}) {
  const state = {
    joined: false,
    muted: false,
    transmitting: false,
    room: null,
    peers: [],
    mode: MODE_VOICE_ACTIVITY,
    micGain: DEFAULT_MIC_GAIN,
    voiceVolume: DEFAULT_VOICE_VOLUME,
    inputDevice: DEFAULT_INPUT_DEVICE,
    outputDevice: DEFAULT_OUTPUT_DEVICE,
    pushToTalkActive: false,
    // True once the microphone has been granted at least once this session.
    permissionGranted: false,
    error: "",
  };

  const detector = createVoiceActivityDetector();
  const speakers = new Map();

  let context = null;
  let stream = null;
  let capture = null;
  let player = null;
  let sequence = 0;
  let sequenceWindowStartedAt = 0;
  let framesThisSecond = 0;
  let starting = false;

  function notify() {
    if (typeof onStateChange === "function") {
      onStateChange(state);
    }
  }

  function fail(error) {
    state.error = error instanceof Error ? error.message : String(error || "Voice error");
    if (typeof onError === "function") {
      onError(state.error);
    }
    notify();
  }

  // -- Devices -------------------------------------------------------------

  /**
   * Return available microphones.
   *
   * `enumerateDevices` reports empty labels until microphone permission has
   * been granted at least once, so the entries are given a placeholder name
   * until then rather than showing a column of blanks.
   */
  async function listInputDevices() {
    const enumerate = enumerateDevices || defaultEnumerateDevices();
    try {
      const devices = await enumerate();
      return devices
        .filter((device) => device.kind === "audioinput")
        .map((device, index) => ({
          deviceId: device.deviceId || String(index),
          label: device.label || `Microphone ${index + 1}`,
          granted: Boolean(device.label),
        }));
    } catch {
      return [];
    }
  }

  /** Return available speakers. Empty labels mean permission has not been granted. */
  async function listOutputDevices() {
    const enumerate = enumerateDevices || defaultEnumerateDevices();
    try {
      const devices = await enumerate();
      return devices
        .filter((device) => device.kind === "audiooutput")
        .map((device, index) => ({
          deviceId: device.deviceId || String(index),
          label: device.label || `Speaker ${index + 1}`,
          granted: Boolean(device.label),
        }));
    } catch {
      return [];
    }
  }

  /**
   * Output device selection needs `AudioContext.setSinkId`, which is not
   * implemented in every browser. Reporting it beats offering a control that
   * silently does nothing.
   */
  function supportsOutputSelection() {
    // Answerable before joining so the UI can decide up front, and re-checked
    // against the live context afterwards.
    if (context) {
      return typeof context.setSinkId === "function";
    }
    const Ctor = globalThis.AudioContext || globalThis.webkitAudioContext;
    return typeof Ctor?.prototype?.setSinkId === "function";
  }

  async function applyOutputDevice() {
    if (!context) {
      return;
    }
    const isDefault = state.outputDevice === DEFAULT_OUTPUT_DEVICE;
    if (typeof context.setSinkId !== "function") {
      if (!isDefault) {
        state.outputDevice = DEFAULT_OUTPUT_DEVICE;
        fail("This browser cannot pick a voice output device; using the system default.");
      }
      return;
    }
    // The system default needs no call at all. ``setSinkId("default")`` looks
    // like the right argument but is rejected as an unknown device, and
    // ``""`` is the spec's actual "use the default" value.
    if (isDefault) {
      return;
    }
    try {
      await context.setSinkId(state.outputDevice);
      state.error = "";
    } catch (error) {
      // A device that has since been unplugged should not leave the mic dead.
      state.outputDevice = DEFAULT_OUTPUT_DEVICE;
      try {
        await context.setSinkId("");
      } catch {
        fail(error);
        return;
      }
      state.error = "Voice output device unavailable; using the system default.";
      notify();
    }
  }

  // -- Context -------------------------------------------------------------

  function newContext() {
    if (context) {
      return context;
    }
    const factory =
      createAudioContext ||
      (() => {
        const Ctor = window.AudioContext || window.webkitAudioContext;
        return new Ctor({ sampleRate: VOICE_SAMPLE_RATE });
      });
    // The wire format is 16kHz, so ask for it; browsers that cannot honour the
    // request still work because both ends resample.
    try {
      context = factory({ sampleRate: VOICE_SAMPLE_RATE });
    } catch {
      context = factory();
    }
    return context;
  }

  async function acquireStream() {
    const getMedia = getUserMedia || defaultGetUserMedia();

    function buildConstraints() {
      const constraints = {
        audio: {
          channelCount: VOICE_CHANNELS,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      };
      if (state.inputDevice && state.inputDevice !== DEFAULT_INPUT_DEVICE) {
        constraints.audio.deviceId = { exact: state.inputDevice };
      }
      return constraints;
    }

    try {
      stream = await getMedia(buildConstraints());
      state.permissionGranted = true;
      state.error = "";
    } catch (error) {
      // A stale saved device id is common after plugging in different hardware.
      // Drop the id and let the browser pick, rather than losing the mic.
      if (error?.name === "OverconstrainedError" || error?.name === "NotFoundError") {
        state.inputDevice = DEFAULT_INPUT_DEVICE;
        stream = await getMedia(buildConstraints());
        state.permissionGranted = true;
        state.error = "";
      } else {
        state.permissionGranted = error?.name === "NotAllowedError" ? false : state.permissionGranted;
        throw error;
      }
    }
  }

  async function startCapture() {
    if (capture || starting) {
      return;
    }
    starting = true;
    try {
      const audioContext = newContext();
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }
      await applyOutputDevice();
      await acquireStream();
      player = createVoicePlayer({
        context: audioContext,
        ...(workletUrl ? { workletUrl } : {}),
      });
      await player.start();
      player.setVolume(state.voiceVolume);
      capture = createVoiceCapture({
        context: audioContext,
        stream,
        ...(workletUrl ? { workletUrl } : {}),
        onFrame: onCapturedFrame,
        onError: (error) => {
          // A failed worklet already fell back inside createVoiceCapture.
          if (!(error instanceof Error) || !/worklet/i.test(error.message || "")) {
            fail(error);
          }
        },
      });
      await capture.start();
    } catch (error) {
      fail(error);
      await stopCapture();
    } finally {
      starting = false;
    }
  }

  async function stopCapture() {
    const activeCapture = capture;
    const activePlayer = player;
    const activeStream = stream;
    capture = null;
    player = null;
    stream = null;
    try {
      activeCapture?.stop();
    } catch {
      // Ignore teardown failures.
    }
    try {
      activePlayer?.stop();
    } catch {
      // Ignore teardown failures.
    }
    for (const track of activeStream?.getTracks?.() ?? []) {
      try {
        track.stop();
      } catch {
        // The track may already be ended.
      }
    }
    speakers.clear();
    setTransmitting(false);
  }

  function closeSpeakers() {
    if (player) {
      for (const username of speakers.keys()) {
        player.close(username);
      }
    }
    speakers.clear();
  }

  // -- Transmit gating -----------------------------------------------------

  function setTransmitting(value) {
    if (state.transmitting !== value) {
      state.transmitting = value;
      notify();
    }
  }

  /** Return the frame to transmit, or null to drop it. */
  function frameToSend(frame) {
    if (state.muted || !state.joined) {
      setTransmitting(false);
      return null;
    }
    if (state.mode === MODE_PUSH_TO_TALK) {
      if (!state.pushToTalkActive) {
        setTransmitting(false);
        return null;
      }
    } else if (!detector.process(frame)) {
      setTransmitting(false);
      return null;
    }
    setTransmitting(true);
    return applyGain(frame, state.micGain);
  }

  function onCapturedFrame(frame) {
    const outgoing = frameToSend(frame);
    if (!outgoing) {
      return;
    }
    const payload = bytesToBase64(
      new Uint8Array(outgoing.buffer, outgoing.byteOffset, outgoing.byteLength)
    );
    sendFrame(payload);
  }

  function sendFrame(payload) {
    if (!sendPacket || typeof sendPacket !== "function") {
      return;
    }
    if (!isConnected()) {
      return;
    }
    // The server enforces the same ceiling; this just avoids wasting a send.
    const now = Date.now();
    if (now - sequenceWindowStartedAt >= 1000) {
      sequenceWindowStartedAt = now;
      framesThisSecond = 0;
    }
    if (framesThisSecond >= MAX_FRAMES_PER_SECOND) {
      return;
    }
    framesThisSecond += 1;
    try {
      sendPacket({ type: "voice_audio", data: payload, seq: sequence });
      sequence = (sequence + 1) % Number.MAX_SAFE_INTEGER;
    } catch (error) {
      fail(error);
    }
  }

  function refreshTransmitting() {
    if (state.muted || !state.joined) {
      setTransmitting(false);
    } else if (state.mode === MODE_PUSH_TO_TALK) {
      setTransmitting(state.pushToTalkActive);
    }
  }

  // -- Public API ----------------------------------------------------------

  function join() {
    if (state.joined || !sendPacket) {
      return;
    }
    // Ask for the microphone first: browsers only grant getUserMedia from a
    // user gesture, and join() is called from the button's click handler.
    startCapture();
    sendPacket({ type: "voice_join", muted: state.muted });
    // Optimistic, so the button flips immediately; voice_status confirms it.
    state.joined = true;
    notify();
  }

  async function unjoin() {
    if (sendPacket && state.joined) {
      try {
        sendPacket({ type: "voice_leave" });
      } catch {
        // The socket may already be gone; the server drops us on disconnect.
      }
    }
    state.joined = false;
    state.room = null;
    state.peers = [];
    state.muted = false;
    state.pushToTalkActive = false;
    state.error = "";
    detector.reset();
    await stopCapture();
    notify();
  }

  function setMuted(muted) {
    const next = Boolean(muted);
    if (next === state.muted) {
      return;
    }
    state.muted = next;
    if (next) {
      state.transmitting = false;
    } else {
      detector.reset();
    }
    // Re-join with the new mute state so the server stops or starts relaying.
    if (state.joined && sendPacket) {
      sendPacket({ type: "voice_join", muted: next });
    }
    refreshTransmitting();
    notify();
  }

  function setPushToTalk(active) {
    const next = Boolean(active);
    if (next === state.pushToTalkActive) {
      return;
    }
    state.pushToTalkActive = next;
    refreshTransmitting();
    notify();
  }

  /** Apply voice settings, restarting capture only when the device changed. */
  async function applySettings(settings = {}) {
    const audio = settings.audio && typeof settings.audio === "object" ? settings.audio : settings;
    const previousInput = state.inputDevice;
    const previousOutput = state.outputDevice;
    const previousMode = state.mode;

    state.micGain = clampInt(audio.voice_mic_gain, DEFAULT_MIC_GAIN, 0, 200);
    state.voiceVolume = clampInt(audio.voice_volume, DEFAULT_VOICE_VOLUME, 0, 200);
    state.inputDevice = String(audio.voice_input_device || DEFAULT_INPUT_DEVICE);
    state.outputDevice = String(audio.voice_output_device || DEFAULT_OUTPUT_DEVICE);
    const mode = String(audio.voice_mode || MODE_VOICE_ACTIVITY);
    state.mode = mode === MODE_PUSH_TO_TALK ? MODE_PUSH_TO_TALK : MODE_VOICE_ACTIVITY;
    detector.threshold = clampInt(
      audio.voice_activity_threshold,
      DEFAULT_VOICE_ACTIVITY_THRESHOLD,
      0,
      100
    );
    detector.hangMs = clampInt(
      audio.voice_activity_hang_ms,
      DEFAULT_VOICE_ACTIVITY_HANG_MS,
      0,
      10000
    );

    player?.setVolume(state.voiceVolume);

    if (state.joined && previousOutput !== state.outputDevice) {
      await applyOutputDevice();
    }
    if (state.joined && previousInput !== state.inputDevice) {
      await restartCapture();
    }
    if (previousMode !== state.mode || state.mode === MODE_PUSH_TO_TALK) {
      detector.reset();
    }
    refreshTransmitting();
    notify();
  }

  async function restartCapture() {
    await stopCapture();
    if (state.joined) {
      await startCapture();
    }
  }

  function handleVoiceStatus(packet = {}) {
    state.joined = Boolean(packet.joined);
    state.room = packet.room ?? null;
    state.peers = Array.isArray(packet.peers) ? [...packet.peers] : [];
    if (typeof packet.muted === "boolean") {
      state.muted = packet.muted;
    }

    if (state.joined) {
      startCapture();
    } else {
      stopCapture();
      closeSpeakers();
    }

    // Speakers we can no longer hear are dropped.
    for (const username of [...speakers.keys()]) {
      if (!state.peers.includes(username)) {
        speakers.delete(username);
        player?.close(username);
      }
    }
    refreshTransmitting();
    notify();
  }

  function handleVoicePeer(packet = {}) {
    const action = packet.action;
    const username = packet.username;
    if (!username) {
      return;
    }
    if (action === "left") {
      speakers.delete(username);
      player?.close(username);
      state.peers = state.peers.filter((name) => name !== username);
    } else if (!state.peers.includes(username)) {
      state.peers = [...state.peers, username];
    }
    notify();
  }

  function handleVoiceAudio(packet = {}) {
    const sender = packet.sender;
    const data = packet.data;
    if (!sender || typeof data !== "string") {
      return;
    }
    const samples = decodeVoiceFrame(data);
    if (!samples || samples.length === 0) {
      return;
    }
    if (!player) {
      return;
    }
    speakers.set(sender, true);
    player.push(sender, int16ToFloat(samples), state.voiceVolume / 100);
  }

  async function shutdown() {
    await unjoin();
    try {
      if (context && context.state !== "closed") {
        await context.close();
      }
    } catch {
      // Closing twice is harmless.
    }
    context = null;
  }

  return {
    state,
    detector,
    join,
    unjoin,
    shutdown,
    setMuted,
    setPushToTalk,
    applySettings,
    handleVoiceStatus,
    handleVoicePeer,
    handleVoiceAudio,
    listInputDevices,
    listOutputDevices,
    supportsOutputSelection,
    get context() {
      return context;
    },
    get captureActive() {
      return Boolean(capture);
    },
    get playbackActive() {
      return Boolean(player);
    },
    // Seams for tests: exercise the transmit path and the send rate limit
    // without a microphone, so gating is verifiable in Node.
    frameToSendForTest: frameToSend,
    sendFrameForTest: sendFrame,
    capturedFrameForTest: onCapturedFrame,
  };
}

function clampInt(value, fallback, min, max) {
  const numeric = Math.round(Number(value));
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, numeric));
}

function defaultEnumerateDevices() {
  return async () => {
    const devices = navigator?.mediaDevices?.enumerateDevices;
    if (!devices) {
      throw new Error("Device enumeration is not available in this browser.");
    }
    return devices.call(navigator.mediaDevices);
  };
}

function defaultGetUserMedia() {
  return async (constraints) => {
    const getMedia = navigator?.mediaDevices?.getUserMedia;
    if (!getMedia) {
      throw new Error("Microphone capture is not available in this browser.");
    }
    return getMedia.call(navigator.mediaDevices, constraints);
  };
}