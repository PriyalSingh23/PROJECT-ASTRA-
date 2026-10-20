"""Tests for the Motorola sound-card (voice) transport.

The two properties worth protecting here are:

1. **The safety gate holds.** With ``MOTOROLA_RADIO_APPROVED`` unset nothing is
   transmitted and the result says so.
2. **PTT is never left held.** A radio with PTT stuck down is a stuck
   transmitter — both a licence breach and a jamming hazard. Every failure path
   must de-key.

Neither needs hardware: the software loopback and a recording fake GPIO cover
both, so these run on a laptop and in CI.
"""
import numpy as np
import pytest

import integration.motorola.hardware_bridge as hb
from integration.motorola.hardware_bridge import (
    MotorolaHardwareBridge,
    SoundCardBackend,
)


class FakeGpio:
    """Minimal RPi.GPIO stand-in that records the PTT line's history."""

    BCM = 0
    OUT = 1
    LOW = 0
    HIGH = 1

    def __init__(self):
        self.history = []

    def setmode(self, *_a):
        pass

    def setup(self, *_a, **_k):
        pass

    def output(self, _pin, value):
        self.history.append(value)


def _loopback_bridge():
    return hb.MotorolaHardwareBridge(backend="soundcard", sound=hb.SoundCardBackend(self_loopback=True))


# ---------------------------------------------------------------------------
# Backend selection and probing
# ---------------------------------------------------------------------------
def test_auto_selects_the_soundcard_path():
    # A UDP connect() cannot prove MOTOTRBO Network Interface Service is
    # listening, so "auto" must not pick it and report success into the void.
    bridge = hb.MotorolaHardwareBridge(backend="auto")
    assert bridge.select_backend() == "soundcard"


@pytest.mark.parametrize("name", ["mnis_udp", "gpio_ptt", "soundcard"])
def test_explicit_backend_is_honoured(name):
    assert hb.MotorolaHardwareBridge(backend=name).select_backend() == name


def test_mnis_probe_does_not_claim_reachability():
    probe = hb.MnisUdpBackend(host="127.0.0.1", port=4001).probe()
    assert probe["socket_ready"] is True
    # Honest: a UDP socket that is ready is not the same as a service listening.
    assert probe["reachable"] is False
    assert "does not prove a listener" in probe["note"]


def test_probe_reports_the_soundcard_modem_parameters():
    probe = hb.MotorolaHardwareBridge(backend="soundcard").probe()
    sc = probe["soundcard"]
    assert probe["selected_backend"] == "soundcard"
    assert probe["dmr_max_payload_bytes"] == 280
    assert probe["approved"] is False
    assert sc["modem"]["symbol_rate"] == 1200.0
    assert sc["modem"]["carrier_hz"] == 1700.0
    assert sc["modem"]["occupied_bandwidth_hz"] == 1800.0
    assert isinstance(sc["gpio_available"], bool)


# ---------------------------------------------------------------------------
# Safety gate
# ---------------------------------------------------------------------------
def test_unapproved_transmit_is_a_dry_run(monkeypatch):
    monkeypatch.delenv("MOTOROLA_RADIO_APPROVED", raising=False)
    res = hb.MotorolaHardwareBridge(backend="mnis_udp").transmit("bravo", b"do not transmit")
    assert res["dry_run"] is True
    assert res["success"] is True
    assert "DRY-RUN" in res["details"]


def test_loopback_declares_itself_as_no_rf():
    sound = hb.SoundCardBackend(self_loopback=True)
    res = sound.send(b"loopback-only", dry_run=True)
    assert res.success is True
    assert res.dry_run is True
    assert "no RF emitted" in res.details


def test_receive_before_any_transmit_is_reported_not_crashed():
    sound = hb.SoundCardBackend(self_loopback=True)
    payload, meta = sound.receive(1.0)
    assert payload is None
    assert meta["ok"] is False
    assert meta["error_code"] == "LOOPBACK_EMPTY"


# ---------------------------------------------------------------------------
# PTT discipline — the safety-critical property
# ---------------------------------------------------------------------------
def test_ptt_is_keyed_then_released_on_success(monkeypatch):
    gpio = FakeGpio()
    monkeypatch.setattr(hb, "_load_gpio", lambda pin: gpio)
    sound = hb.SoundCardBackend(gpio_pin=17)
    monkeypatch.setattr(sound, "_play", lambda audio: "stub")

    res = sound.play_audio(np.zeros(4800, dtype=np.float32), dry_run=False)

    assert res.success is True
    assert gpio.history[0] == gpio.HIGH, "PTT must be keyed before audio starts"
    assert gpio.history[-1] == gpio.LOW, "PTT must be released after audio ends"


def test_ptt_is_released_when_playback_raises(monkeypatch):
    gpio = FakeGpio()
    monkeypatch.setattr(hb, "_load_gpio", lambda pin: gpio)
    sound = hb.SoundCardBackend(gpio_pin=17)

    def _boom(_audio):
        raise RuntimeError("sound card vanished mid-burst")

    monkeypatch.setattr(sound, "_play", _boom)
    res = sound.play_audio(np.zeros(4800, dtype=np.float32), dry_run=False)

    assert res.success is False
    assert res.error_code == "AUDIO_TX_ERROR"
    assert gpio.history[0] == gpio.HIGH
    assert gpio.history[-1] == gpio.LOW, "a stuck transmitter is never acceptable"


def test_transmit_without_gpio_and_without_dry_run_fails_loudly(monkeypatch):
    monkeypatch.setattr(hb, "_load_gpio", lambda pin: False)
    sound = hb.SoundCardBackend(gpio_pin=17)
    res = sound.play_audio(np.zeros(4800, dtype=np.float32), dry_run=False)
    assert res.success is False
    assert res.error_code == "GPIO_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Full chain: transmit -> TMS frame -> audio -> demodulate -> parse
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("message", [
    "SITREP GRID 31U-DQ-8842-1190 STATUS NOMINAL OVER",
    "REQUEST RESUPPLY AT LZ BRAVO 0400Z OVER",
    "A",
    "x" * 200,
])
def test_transmit_voice_round_trips_through_tms(message):
    bridge = _loopback_bridge()

    tx = bridge.transmit_voice("bravo", message.encode())
    assert tx["success"] is True
    assert tx["transport"] == "soundcard_voice"
    assert tx["air_time_s"] > 0

    rx = bridge.receive_voice(2.0)
    assert rx["ok"] is True
    assert rx["tms_crc_ok"] is True
    assert rx["payload"] == message
    assert rx["payload_is_utf8"] is True
    assert rx["sync_score"] > 0.95


def test_transmit_voice_preserves_binary_payloads():
    bridge = _loopback_bridge()
    binary = bytes(range(64))

    bridge.transmit_voice("bravo", binary)
    rx = bridge.receive_voice(2.0)

    assert rx["ok"] is True
    assert rx["tms_crc_ok"] is True
    assert rx["payload_hex"] == binary.hex()
    assert rx["payload_bytes"] == len(binary)


def test_transmit_voice_rejects_an_oversize_payload():
    bridge = _loopback_bridge()
    res = bridge.transmit_voice("bravo", b"x" * 400)
    assert res["success"] is False
    assert res["error_code"] == "PAYLOAD_TOO_LARGE"


def test_bridge_exposes_a_channel_self_test():
    bridge = _loopback_bridge()
    report = bridge.self_test(n_frames=4, snr_db=18.0, cfo_hz=5.0, clock_error_ppm=20.0)
    assert report["pass"] is True
    assert report["per"] == 0.0
    assert report["ber"] == 0.0
    assert report["backend"] == "soundcard"
    # The in-band figure must be the honest one, not the wideband number.
    assert report["snr_inband_db"] > report["snr_db"]


def test_bridge_probe_exposes_the_modem_plan():
    bridge = _loopback_bridge()
    sc = bridge.probe()["soundcard"]
    assert sc["modem"]["occupied_bandwidth_hz"] == 1800.0
    assert sc["modem"]["symbol_rate"] == 1200.0
    assert sc["modem"]["carrier_hz"] == 1700.0
