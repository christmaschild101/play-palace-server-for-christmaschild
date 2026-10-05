// Voice chat controls for the web client.
//
// Mirrors the desktop client's voice panel: a join toggle, device pickers,
// mic gain, voice-activity sensitivity, transmit mode, mute, and a status line
// so the state is discoverable without sight of the microphone indicator.

import {
  DEFAULT_MIC_GAIN,
  DEFAULT_VOICE_ACTIVITY_HANG_MS,
  DEFAULT_VOICE_ACTIVITY_THRESHOLD,
  DEFAULT_VOICE_VOLUME,
  DEFAULT_INPUT_DEVICE,
  DEFAULT_OUTPUT_DEVICE,
  MODE_PUSH_TO_TALK,
  MODE_VOICE_ACTIVITY,
} from "../voice.js";

const MODE_VOICE_ACTIVITY_LABEL = "Voice activation";
const MODE_PUSH_TO_TALK_LABEL = "Push to talk";

export function createVoicePanel({
  elements,
  voiceManager,
  a11y,
  onSettingsChange,
  initialSettings = null,
}) {
  let deviceOptionsLoaded = false;

  function settings() {
    return {
      voice_input_device: elements.voiceInputDevice?.value || DEFAULT_INPUT_DEVICE,
      voice_output_device: elements.voiceOutputDevice?.value || DEFAULT_OUTPUT_DEVICE,
      voice_volume: Number(elements.voiceVolume?.value ?? DEFAULT_VOICE_VOLUME),
      voice_mic_gain: Number(elements.voiceGain?.value ?? DEFAULT_MIC_GAIN),
      voice_activity_threshold: Number(
        elements.voiceActivity?.value ?? DEFAULT_VOICE_ACTIVITY_THRESHOLD
      ),
      voice_activity_hang_ms: Number(
        elements.voiceActivityHang?.value ?? DEFAULT_VOICE_ACTIVITY_HANG_MS
      ),
      voice_mode: elements.voiceMode?.value === MODE_PUSH_TO_TALK ? MODE_PUSH_TO_TALK : MODE_VOICE_ACTIVITY,
    };
  }

  async function commit({ announce = false } = {}) {
    const next = settings();
    await voiceManager.applySettings(next);
    onSettingsChange?.(next);
    applyModeToUi();
    if (announce) {
      a11y?.announce(describeSettings(next), { assertive: true });
    }
  }

  function describeSettings(next) {
    const mode = next.voice_mode === MODE_PUSH_TO_TALK ? MODE_PUSH_TO_TALK_LABEL : MODE_VOICE_ACTIVITY_LABEL;
    return `Microphone ${next.voice_mic_gain}% gain, ${mode}, sensitivity ${next.voice_activity_threshold}.`;
  }

  function applyModeToUi() {
    const pushToTalk = elements.voiceMode?.value === MODE_PUSH_TO_TALK;
    if (elements.voiceTalkButton) {
      elements.voiceTalkButton.hidden = !pushToTalk;
    }
    if (elements.voiceActivityHang) {
      elements.voiceActivityHang.disabled = pushToTalk;
    }
  }

  function describeState(state) {
    if (state.error) {
      return `Voice chat error: ${state.error}`;
    }
    if (!state.joined) {
      return "Not in voice chat.";
    }
    const peers = state.peers;
    const who =
      peers.length === 0
        ? "no one else yet"
        : peers.length === 1
          ? `with ${peers[0]}`
          : `with ${peers.join(", ")}`;
    const talking = state.transmitting ? ", talking" : "";
    const muted = state.muted ? ", muted" : "";
    const room = state.room ? ` in ${state.room}` : "";
    return `In voice chat${room} ${who}${talking}${muted}.`;
  }

  function refresh(state = voiceManager.state) {
    if (elements.voiceJoinButton) {
      const label = state.joined ? "Leave voice" : "Join voice";
      elements.voiceJoinButton.textContent = label;
      elements.voiceJoinButton.setAttribute("aria-pressed", state.joined ? "true" : "false");
    }
    if (elements.voiceMute) {
      elements.voiceMute.checked = state.muted;
    }
    if (elements.voiceTalkButton) {
      elements.voiceTalkButton.classList.toggle("active", state.pushToTalkActive);
      elements.voiceTalkButton.setAttribute(
        "aria-pressed",
        state.pushToTalkActive ? "true" : "false"
      );
    }
    if (elements.voiceGainValue) {
      elements.voiceGainValue.textContent = `${voiceManager.state.micGain}%`;
    }
    if (elements.voiceActivityHangValue) {
      elements.voiceActivityHangValue.textContent = `${voiceManager.detector.hangMs}ms`;
    }
    if (elements.voiceVolumeValue) {
      elements.voiceVolumeValue.textContent = `${voiceManager.state.voiceVolume}%`;
    }
    if (elements.voiceStatus) {
      const text = describeState(state);
      elements.voiceStatus.textContent = text;
      elements.voiceStatus.classList.toggle("error", Boolean(state.error));
    }
    if (elements.voiceTalkButton) {
      elements.voiceTalkButton.disabled = !state.joined;
    }
  }

  function fillDeviceSelect(select, devices, selectedId, defaultLabel) {
    if (!select) {
      return;
    }
    const previous = selectedId || select.value;
    const options = [{ deviceId: DEFAULT_INPUT_DEVICE, label: defaultLabel }, ...devices];
    select.replaceChildren(
      ...options.map((device) => {
        const option = document.createElement("option");
        option.value = device.deviceId;
        option.textContent = device.label;
        return option;
      })
    );
    const wanted = options.some((device) => device.deviceId === previous)
      ? previous
      : DEFAULT_INPUT_DEVICE;
    select.value = wanted;
  }

  async function refreshDevices() {
    const [inputs, outputs] = await Promise.all([
      voiceManager.listInputDevices(),
      voiceManager.listOutputDevices(),
    ]);
    fillDeviceSelect(elements.voiceInputDevice, inputs, voiceManager.state.inputDevice, "Default microphone");
    fillDeviceSelect(elements.voiceOutputDevice, outputs, voiceManager.state.outputDevice, "Default speaker");
    deviceOptionsLoaded = true;

    // Labels only appear after permission is granted, so re-enumerate once the
    // microphone is actually open.
    const unlabeled = inputs.some((device) => !device.granted);
    if (elements.voiceDeviceNote) {
      if (!labelsAvailable(inputs) || !labelsAvailable(outputs)) {
        elements.voiceDeviceNote.hidden = false;
        elements.voiceDeviceNote.textContent =
          "Device names appear after the microphone permission is granted.";
      } else {
        elements.voiceDeviceNote.hidden = true;
      }
    }
    if (unlabeled && voiceManager.state.joined) {
      scheduleDeviceRefresh();
    }
  }

  function labelsAvailable(devices) {
    return !devices.some((device) => !device.granted);
  }

  let deviceRefreshTimer = null;
  function scheduleDeviceRefresh(delayMs = 1500) {
    if (deviceRefreshTimer !== null) {
      return;
    }
    deviceRefreshTimer = setTimeout(() => {
      deviceRefreshTimer = null;
      voiceManager.listInputDevices().then((devices) => {
        if (labelsAvailable(devices)) {
          refreshDevices();
        } else {
          scheduleDeviceRefresh();
        }
      });
    }, delayMs);
  }

  function onJoinToggle() {
    if (voiceManager.state.joined) {
      voiceManager.unjoin();
      a11y?.announce("Leaving voice chat.", { assertive: true });
      return;
    }
    // join() must run inside the click handler so the browser treats it as a
    // user gesture and allows the microphone prompt.
    voiceManager.join();
    refreshDevices();
    a11y?.announce("Joining voice chat.", { assertive: true });
  }

  function bindHoldButton(button, onHold, onRelease) {
    if (!button) {
      return;
    }
    const start = (event) => {
      event.preventDefault();
      onHold();
    };
    const end = (event) => {
      event.preventDefault();
      onRelease();
    };
    button.addEventListener("pointerdown", start);
    button.addEventListener("pointerup", end);
    button.addEventListener("pointercancel", end);
    button.addEventListener("pointerleave", (event) => {
      // Only release on leave when the pointer was actually captured.
      if (event.buttons !== 0) {
        onRelease();
      }
    });
    // Keyboard equivalent: Enter/Space on a focused button.
    button.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        event.stopPropagation();
        onHold();
      }
    });
    button.addEventListener("keyup", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        event.stopPropagation();
        onRelease();
      }
    });
    button.addEventListener("blur", () => onRelease());
  }

  elements.voiceJoinButton?.addEventListener("click", onJoinToggle);

  // Losing focus (alt-tab, another tab, a native dialog) can swallow the
  // pointerup or keyup that would otherwise close the mic.
  if (typeof window !== "undefined") {
    window.addEventListener("blur", () => voiceManager.setPushToTalk(false));
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible") {
        voiceManager.setPushToTalk(false);
      }
    });
  }

  bindHoldButton(
    elements.voiceTalkButton,
    () => {
      if (!voiceManager.state.joined) {
        return;
      }
      voiceManager.setPushToTalk(true);
    },
    () => voiceManager.setPushToTalk(false)
  );

  elements.voiceMute?.addEventListener("change", (event) => {
    voiceManager.setMuted(event.target.checked);
    a11y?.announce(
      event.target.checked ? "Microphone muted." : "Microphone unmuted.",
      { assertive: true }
    );
  });

  elements.voiceGain?.addEventListener("input", (event) => {
    const value = Number(event.target.value);
    voiceManager.state.micGain = value;
    if (elements.voiceGainValue) {
      elements.voiceGainValue.textContent = `${value}%`;
    }
  });
  elements.voiceGain?.addEventListener("change", () => commit({ announce: true }));

  elements.voiceActivity?.addEventListener("input", (event) => {
    const value = Number(event.target.value);
    voiceManager.detector.threshold = value;
    if (elements.voiceActivityValue) {
      elements.voiceActivityValue.textContent = String(value);
    }
  });
  elements.voiceActivity?.addEventListener("change", () => commit({ announce: true }));

  elements.voiceActivityHang?.addEventListener("input", (event) => {
    if (elements.voiceActivityHangValue) {
      elements.voiceActivityHangValue.textContent = `${event.target.value}ms`;
    }
  });
  elements.voiceActivityHang?.addEventListener("change", () => commit({ announce: true }));

  elements.voiceVolume?.addEventListener("change", () => commit({ announce: true }));

  elements.voiceMode?.addEventListener("change", () => {
    applyModeToUi();
    commit({ announce: true });
  });

  elements.voiceInputDevice?.addEventListener("change", () => commit());
  elements.voiceOutputDevice?.addEventListener("change", () => commit());

  // Hot-plugging headsets changes the device list under us.
  if (typeof navigator !== "undefined" && navigator.mediaDevices) {
    navigator.mediaDevices.addEventListener?.("devicechange", () => {
      if (deviceOptionsLoaded) {
        refreshDevices();
      }
    });
  }

  // Declared before use below; a function declaration so the saved-settings
  // restore at the end of setup can call it.
  function applySettingsToUi(next) {
    // Only touch a control when a value was supplied, so a partial or empty
    // saved blob cannot blank the sliders.
    const setValue = (el, value) => {
      if (el && value !== undefined && value !== null && value !== "") {
        el.value = String(value);
      }
    };
    setValue(elements.voiceGain, next.voice_mic_gain);
    setValue(elements.voiceActivity, next.voice_activity_threshold);
    setValue(elements.voiceActivityHang, next.voice_activity_hang_ms);
    setValue(elements.voiceVolume, next.voice_volume);
    setValue(elements.voiceMode, next.voice_mode);
    setValue(elements.voiceInputDevice, next.voice_input_device);
    setValue(elements.voiceOutputDevice, next.voice_output_device);
    if (next.voice_activity_threshold !== undefined && elements.voiceActivityValue) {
      elements.voiceActivityValue.textContent = String(next.voice_activity_threshold);
    }
    if (next.voice_activity_hang_ms !== undefined && elements.voiceActivityHangValue) {
      elements.voiceActivityHangValue.textContent = `${next.voice_activity_hang_ms}ms`;
    }
    refresh();
  }

  // Saved settings must land in the controls, not just in the manager: the
  // next slider move reads the DOM, so leaving it at defaults would discard
  // the user's saved gain and sensitivity.
  if (initialSettings) {
    applySettingsToUi(initialSettings);
  }
  applyModeToUi();
  refresh();
  refreshDevices();

  return {
    refresh,
    refreshDevices,
    settings,
    applySettingsToUi,
  };
}
