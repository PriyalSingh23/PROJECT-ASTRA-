"""Motorola bridge integration: the Pi sound-card path carries LPI bursts.

These tests run the *exact* ``SoundCardBackend`` code path the Raspberry Pi uses
(``send`` -> modulate -> PTT -> play -> ``receive`` -> demodulate) in software
loopback, so the wiring between the LPI carrier and the hardware bridge is proven
green before anything is keyed. No RF and no GPIO are touched, and the safety
lockout is asserted separately.

What is NOT tested here, because it needs hardware: the real PTT transient, the
radio's PA and squelch, and the acoustic coupling into the mic.
"""
import numpy as np
import pytest

from integration.motorola.hardware_bridge import (
    DMR_MAX_PAYLOAD_BYTES,
    SoundCardBackend,
)


def test_lpi_mode_loopback_round_trips():
    """LPI mode must carry an arbitrary framed payload end to end."""
    backend = SoundCardBackend(self_loopback=True, lpi_mode=True)
    frame = b"TMS-PDU-LPI-ROUNDTRIP"
    sent = backend.send(frame, dry_run=True)
    assert sent.success, sent.detail
    assert sent.meta.get("lpi") is True
    payload, meta = backend.receive(2.0)
    assert meta["ok"], meta
    assert meta.get("lpi") is True
    assert payload == frame


def test_plain_mode_is_unaffected():
    """The default (non-LPI) modem must behave exactly as before."""
    backend = SoundCardBackend(self_loopback=True)
    assert backend._lpi is None
    frame = b"PLAIN-VOICE-MODEM"
    assert backend.send(frame, dry_run=True).success
    payload, meta = backend.receive(2.0)
    assert meta["ok"], meta
    assert payload == frame
    assert "lpi" not in meta


def test_wrong_mode_receiver_does_not_recover_the_payload():
    """An LPI burst must not decode in a plain-mode receiver.

    This is the intended property: the two modes differ at the physical layer, so
    they are incompatible in the same way two different session keys are. A
    receiver configured for the wrong mode must fail to recover the payload
    rather than silently mangle it.
    """
    lpi = SoundCardBackend(self_loopback=True, lpi_mode=True)
    lpi.send(b"LPI-ONLY-PAYLOAD", dry_run=True)

    # Put the LPI burst where a plain receiver will read it.
    plain = SoundCardBackend(self_loopback=True)
    plain._loopback_audio = lpi._loopback_audio
    payload, meta = plain.receive(2.0)
    assert payload != b"LPI-ONLY-PAYLOAD", (
        "a plain-mode receiver recovered an LPI burst; the physical layers "
        "should not be cross-compatible")


def test_dmr_ceiling_still_enforced():
    """The 280-byte DMR ceiling is the binding payload limit, not the carrier's."""
    backend = SoundCardBackend(self_loopback=True, lpi_mode=True)
    # A payload at the DMR ceiling must still fit the LPI carrier.
    frame = bytes(range(256)) * 1 + b"X" * (DMR_MAX_PAYLOAD_BYTES - 256)
    assert len(frame) == DMR_MAX_PAYLOAD_BYTES
    sent = backend.send(frame, dry_run=True)
    assert sent.success, sent.detail
    payload, meta = backend.receive(2.0)
    assert meta["ok"], meta
    assert payload == frame


def test_lpi_burst_is_not_silent():
    """The transmitted burst must never be digitally silent in any guard region."""
    backend = SoundCardBackend(self_loopback=True, lpi_mode=True)
    backend.send(b"LEVEL-CHECK", dry_run=True)
    audio = np.asarray(backend._loopback_audio, dtype=np.float64)
    assert audio.size > 0
    frame = 512
    n = audio.size // frame
    segs = np.stack([audio[i * frame:(i + 1) * frame] for i in range(n)])
    rms = np.sqrt((segs ** 2).mean(axis=1))
    assert rms.min() > 0.1 * np.median(rms)


def test_radio_safety_lockout_is_default_off():
    """No transmission may be approved unless explicitly enabled by env var."""
    import os

    from integration.motorola.hardware_bridge import MotorolaHardwareBridge

    os.environ.pop("MOTOROLA_RADIO_APPROVED", None)
    bridge = MotorolaHardwareBridge(backend="soundcard", lpi_mode=True)
    assert bridge.approved() is False
    # A dispatch must be a dry run when not approved.
    result = bridge.transmit("endpoint-b", b"SAFETY-CHECK")
    assert result["dry_run"] is True


# ---------------------------------------------------------------------------
# SDR (USRP) transport
#
# The Motorola path and the wideband SDR path were historically separate modules
# with nothing connecting them, so "Motorola carried over the SDR" was not true
# in code. These tests pin the join: the SDR backend must carry the *same* LPI
# burst the sound-card path transmits, with no second waveform, and must never
# claim a device it cannot see.
# ---------------------------------------------------------------------------

def test_sdr_backend_carries_the_same_lpi_waveform():
    """The SDR transport must reuse the Motorola LPI burst verbatim."""
    from integration.motorola.lpi_carrier import LpiCarrier, LpiCarrierConfig
    from integration.motorola.sdr_backend import SdrBackend, audio_to_iq

    carrier = LpiCarrier(LpiCarrierConfig())
    backend = SdrBackend(lpi=carrier,
                         seed_fn=lambda f: 1234)

    frame = b"SDR-CARRY-SAME-WAVEFORM"
    res = backend.send(frame, dry_run=True)
    assert res.success, res.details
    assert res.dry_run is True
    assert res.meta["lpi"] is True
    assert res.meta["transport"] == "sdr_usrp"

    # The IQ must be the analytic upconversion of exactly this burst, so its
    # length is the audio length times the exact 5.12 rate ratio.
    expected = audio_to_iq(carrier.modulate(frame, seed=1234)).size
    assert res.meta["iq_samples"] == expected
    assert res.bytes_on_wire == len(frame), (
        "bytes_on_wire must report frame bytes, not audio samples")


def test_sdr_upsampling_ratio_is_exact_and_single_sideband():
    """48 kHz -> 245.76 kHz must be the exact 512/100 ratio, one sideband."""
    from integration.motorola.lpi_carrier import LpiCarrier, LpiCarrierConfig
    from integration.motorola.sdr_backend import DEFAULT_SDR_RATE, audio_to_iq

    carrier = LpiCarrier(LpiCarrierConfig())
    audio = carrier.modulate(b"BANDWIDTH-CHECK", seed=7)
    iq = audio_to_iq(audio, DEFAULT_SDR_RATE)

    # ``resample_poly`` rounds the output length up, so 81192 * 512/100 =
    # 415703.04 becomes 415704 samples. The rate itself is exact; only the
    # trailing partial sample is padded.
    assert iq.size == int(np.ceil(audio.size * 512 / 100))
    assert np.max(np.abs(iq)) == pytest.approx(1.0, abs=1e-6)

    # The occupied band must survive the conversion at the right width and stay
    # on one side of the LO (an analytic signal, not a mirrored DSB).
    power = np.abs(np.fft.fftshift(np.fft.fft(iq))) ** 2
    freqs = np.fft.fftshift(np.fft.fftfreq(iq.size, 1.0 / DEFAULT_SDR_RATE))
    norm = power / power.max()
    band = freqs[norm > 1e-3]
    lo, hi = float(band.min()), float(band.max())
    assert lo > -500.0, f"energy leaked to the negative side ({lo:.0f} Hz)"
    assert 2400.0 < (hi - lo) < 3000.0, (
        f"occupied width changed to {hi - lo:.0f} Hz")


def test_sdr_probe_never_invents_a_device():
    """probe() must not report availability without enumerating a device."""
    from integration.motorola.sdr_backend import SdrBackend

    probe = SdrBackend().probe()
    assert probe["backend"] == "sdr_usrp"
    if probe["device_found"]:
        assert probe["available"] is True
    else:
        assert probe["available"] is False
        assert "no USRP" in probe["note"]


def test_sdr_is_not_the_automatic_backend():
    """auto must stay on the radio path; SDR radiation is an explicit choice."""
    from integration.motorola.hardware_bridge import MotorolaHardwareBridge

    bridge = MotorolaHardwareBridge(backend="auto", lpi_mode=True)
    assert bridge.select_backend() == "soundcard"

    forced = MotorolaHardwareBridge(backend="sdr_usrp", lpi_mode=True)
    assert forced.select_backend() == "sdr_usrp"
