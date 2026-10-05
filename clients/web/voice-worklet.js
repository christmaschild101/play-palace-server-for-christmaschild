// AudioWorklet processors backing the PlayPalace web voice chat.
//
// Both processors convert between the wire format (16kHz mono signed 16-bit
// little-endian PCM) and the AudioContext's own sample rate, so the rest of the
// client never has to care what rate the hardware is running at. The server
// relay is fixed at 16kHz; see server/core/voice.py and
// server/network/packet_models.py.

const TARGET_SAMPLE_RATE = 16000;
const FRAME_SAMPLES = (TARGET_SAMPLE_RATE * 20) / 1000; // 20ms -> 320 samples
const INT16_MAX = 32767;
const INT16_MIN = -32768;

// Two seconds of slack absorbs jitter without letting a stalled network turn
// into unbounded memory growth.
const CAPTURE_BUFFER_SAMPLES = 4096;
const PLAYBACK_BUFFER_SAMPLES = TARGET_SAMPLE_RATE * 2;

function floatToInt16(value) {
  const scaled = value < 0 ? value * 0x8000 : value * 0x7fff;
  if (scaled > INT16_MAX) {
    return INT16_MAX;
  }
  if (scaled < INT16_MIN) {
    return INT16_MIN;
  }
  return scaled;
}

/**
 * Downmix an input block to mono. Browsers hand us one channel per configured
 * channel count, and we always request mono, so this is a pass-through in the
 * normal case.
 */
function mixToMono(frames) {
  if (frames.length === 0) {
    return null;
  }
  if (frames.length === 1) {
    return frames[0];
  }
  const length = frames[0].length;
  const mixed = new Float32Array(length);
  for (let channel = 0; channel < frames.length; channel += 1) {
    const samples = frames[channel];
    for (let index = 0; index < length; index += 1) {
      mixed[index] += samples[index] / frames.length;
    }
  }
  return mixed;
}

class VoiceCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._input = new Float32Array(CAPTURE_BUFFER_SAMPLES);
    this._filled = 0;
    this._readPos = 0;
    this._step = sampleRate / TARGET_SAMPLE_RATE;
    this._output = new Float32Array(FRAME_SAMPLES);
    this._outputFilled = 0;
    this._stopped = false;

    this.port.onmessage = (event) => {
      if (event.data && event.data.type === "stop") {
        this._stopped = true;
      }
    };
  }

  _append(samples) {
    if (samples.length > this._input.length) {
      // A block larger than the whole buffer: keep only its tail, since that
      // is the audio closest to now.
      this._input.set(samples.subarray(samples.length - this._input.length), 0);
      this._filled = this._input.length;
      this._readPos = 0;
      return;
    }
    if (this._filled + samples.length > this._input.length) {
      // Make room by dropping the oldest audio; a full buffer means the main
      // thread stalled. Dropping read audio first keeps the stream aligned.
      const room = this._input.length - samples.length;
      const drop = Math.max(room - this._filled, Math.floor(this._readPos));
      const remove = Math.min(drop, this._filled);
      if (remove > 0) {
        this._input.copyWithin(0, remove, this._filled);
        this._filled -= remove;
        this._readPos = Math.max(0, Math.min(this._readPos - remove, this._filled - 1));
      } else {
        this._filled = 0;
        this._readPos = 0;
      }
    }
    this._input.set(samples, this._filled);
    this._filled += samples.length;
  }

  _compact() {
    if (this._readPos < 1) {
      return;
    }
    // The read position can overshoot the buffer by up to one resample step,
    // so clamp before using it as a copyWithin offset.
    const whole = Math.min(Math.floor(this._readPos), this._filled);
    if (whole <= 0) {
      this._filled = 0;
      this._readPos = 0;
      return;
    }
    this._input.copyWithin(0, whole, this._filled);
    this._filled -= whole;
    this._readPos = Math.max(0, this._readPos - whole);
  }

  _emitFrame() {
    const frame = new Int16Array(FRAME_SAMPLES);
    for (let index = 0; index < FRAME_SAMPLES; index += 1) {
      frame[index] = floatToInt16(this._output[index]);
    }
    this._outputFilled = 0;
    // Transfer the buffer: the worklet allocates a fresh one each frame.
    this.port.postMessage({ type: "frame", buffer: frame.buffer }, [frame.buffer]);
  }

  _drain() {
    while (true) {
      const nextIndex = Math.floor(this._readPos);
      if (nextIndex + 1 >= this._filled) {
        break;
      }
      const fraction = this._readPos - nextIndex;
      const current = this._input[nextIndex];
      const next = this._input[nextIndex + 1];
      this._output[this._outputFilled] = current + (next - current) * fraction;
      this._outputFilled += 1;
      this._readPos += this._step;
      if (this._outputFilled >= FRAME_SAMPLES) {
        this._emitFrame();
      }
    }
    this._compact();
  }

  process(inputs) {
    if (this._stopped) {
      return false;
    }
    const mono = mixToMono(inputs[0] || []);
    if (mono) {
      this._append(mono);
      this._drain();
    }
    // Voice is a one-way tap: never feed the microphone back to the speakers.
    return true;
  }
}

class VoicePlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._streams = new Map();

    this.port.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === "close") {
        this._streams.delete(message.sender);
        return;
      }
      if (message.type !== "frame") {
        return;
      }
      const sender = String(message.sender ?? "");
      if (!sender) {
        return;
      }
      const samples = new Float32Array(message.buffer);
      const stream = this._streamFor(sender);
      if (message.volume !== undefined) {
        stream.volume = Number(message.volume) || 0;
      }
      stream.write(samples);
    };
  }

  _streamFor(sender) {
    let stream = this._streams.get(sender);
    if (!stream) {
      stream = {
        buffer: new Float32Array(PLAYBACK_BUFFER_SAMPLES),
        filled: 0,
        readPos: 0,
        // Input arrives at 16kHz; consume it slower or faster to reach
        // whatever rate the hardware is running at.
        step: TARGET_SAMPLE_RATE / sampleRate,
        volume: 1,
        write(samples) {
          if (samples.length > this.buffer.length) {
            // A single frame longer than the whole ring: keep its tail.
            const tail = samples.subarray(samples.length - this.buffer.length);
            this.buffer.set(tail, 0);
            this.filled = this.buffer.length;
            this.readPos = 0;
            return;
          }
          // Drop consumed audio first, then as much unconsumed audio as is
          // needed, so a stalled network cannot grow this without bound and the
          // write below is guaranteed to fit.
          if (this.filled + samples.length > this.buffer.length) {
            const dropConsumed = Math.floor(this.readPos);
            const stillNeeded =
              this.filled - dropConsumed + samples.length - this.buffer.length;
            const drop = Math.min(dropConsumed, Math.max(0, stillNeeded));
            if (drop > 0) {
              this.buffer.copyWithin(0, drop, this.filled);
              this.filled -= drop;
              this.readPos -= drop;
            }
            if (this.filled + samples.length > this.buffer.length) {
              // Everything queued is unread audio older than the new frame;
              // discard it so the newest speech is what plays.
              this.filled = 0;
              this.readPos = 0;
            }
          }
          this.buffer.set(samples, this.filled);
          this.filled += samples.length;
        },
      };
      this._streams.set(sender, stream);
    }
    return stream;
  }

  _nextSample(stream) {
    const nextIndex = Math.floor(stream.readPos) + 1;
    if (nextIndex >= stream.filled) {
      return 0;
    }
    const base = Math.floor(stream.readPos);
    const fraction = stream.readPos - base;
    const current = stream.buffer[base];
    const next = stream.buffer[nextIndex];
    stream.readPos += stream.step;
    return current + (next - current) * fraction;
  }

  _release(stream) {
    const keepFrom = Math.floor(stream.readPos);
    if (keepFrom <= 0) {
      return;
    }
    stream.buffer.copyWithin(0, keepFrom, stream.filled);
    stream.filled -= keepFrom;
    stream.readPos -= keepFrom;
  }

  process(_inputs, outputs) {
    const output = outputs[0];
    if (!output || output.length === 0) {
      return true;
    }
    for (const channel of output) {
      channel.fill(0);
    }
    if (this._streams.size === 0) {
      return true;
    }

    // Shared headroom so several speakers cannot sum into hard clipping. A linear
    // split guarantees the mix never exceeds full scale no matter how many
    // people are talking.
    const headroom = 1 / Math.max(1, this._streams.size);
    const length = output[0].length;

    for (const [sender, stream] of this._streams) {
      const gain = stream.volume * headroom;
      for (let index = 0; index < length; index += 1) {
        const sample = this._nextSample(stream);
        if (sample === 0) {
          continue;
        }
        for (const channel of output) {
          channel[index] += sample * gain;
        }
      }
      this._release(stream);
      // Interpolation always needs one lookahead sample, so a single trailing
      // sample can never be consumed. Treat it as drained, or the speaker's
      // stream would live for the rest of the session.
      if (stream.filled <= 1) {
        this._streams.delete(sender);
      }
    }
    return true;
  }
}

registerProcessor("playpalace-voice-capture", VoiceCaptureProcessor);
registerProcessor("playpalace-voice-player", VoicePlayerProcessor);