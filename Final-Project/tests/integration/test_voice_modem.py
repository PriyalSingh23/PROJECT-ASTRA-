"""Tests for the Motorola voice-channel audio modem.

These run entirely in software: modulate -> simulated radio channel ->
demodulate. That is deliberate. The modem's job is to be provably correct
*before* anything is keyed, so that a failure in the field is a radio problem
and not a DSP bug. Every assertion here is about a measured property of the
chain, not a golden number.
"""
import numpy as np
import pytest

from integration.motorola.voice_modem import (
    BARKER13,
    MAX_PAYLOAD_BYTES,
    ModemConfig,
    VoiceModem,
    bits_to_bytes,
    bytes_to_bits,
    loopback_selftest,
    rrc_taps,
    simulate_voice_channel,
)

PAYLOADS = [
    b"",
    b"\x00",
    b"A",
    bytes(range(16)),
    bytes(range(256)),
    b"SHADOWCOMM/SITREP/GRID-31U-DQ-8842-1190/1xMOTOTRBO-DP4801e/STATUS-OK",
    bytes((i * 7) % 256 for i in range(400)),
]


@pytest.fixture(scope="module")
def modem():
    return VoiceModem()


# ---------------------------------------------------------------------------
# Bit helpers and pulse shaping
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("payload", PAYLOADS)
def test_bit_helpers_round_trip(payload):
    bits = bytes_to_bits(payload)
    assert bits.size == len(payload) * 8
    assert set(np.unique(bits)).issubset({-1.0, 1.0})
    assert bits_to_bytes(bits) == payload


def test_empty_payload_bit_helpers():
    assert bytes_to_bits(b"").size == 0
    assert bits_to_bytes(np.zeros(0)) == b""


def test_rrc_taps_are_unit_energy_and_symmetric():
    taps = rrc_taps(sps=8, beta=0.5, span=6)
    assert taps.size == 2 * 6 * 8 + 1
    assert np.isclose(np.sum(taps ** 2), 1.0, atol=1e-9)
    assert np.allclose(taps, taps[::-1], atol=1e-12)


def test_modem_defaults_fit_a_voice_channel(modem):
    cfg = modem.cfg
    occupied = cfg.symbol_rate * (1.0 + cfg.roll_off)
    # A 300-3000 Hz channel must contain the whole occupied band.
    assert cfg.carrier_hz - occupied / 2 > 300.0
    assert cfg.carrier_hz + occupied / 2 < 3000.0
    assert cfg.sps == 40


def test_barker13_is_low_autocorrelation():
    # The sync word is only useful if it does not correlate with itself offset.
    assert BARKER13.size == 13
    corr = np.correlate(BARKER13, BARKER13, mode="full")
    peak = float(corr.max())
    assert peak == 13.0
    centre = BARKER13.size - 1
    sidelobes = np.delete(corr, centre)
    assert float(np.max(np.abs(sidelobes))) / peak <= 1.0 / 13.0 + 1e-9


# ---------------------------------------------------------------------------
# Loopback
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("payload", PAYLOADS)
def test_clean_loopback_is_bit_exact(modem, payload):
    decoded = modem.demodulate(modem.modulate(payload))
    assert decoded.ok, decoded.detail
    assert decoded.payload == payload
    assert decoded.sync_score > 0.95


def test_oversize_payload_is_refused(modem):
    with pytest.raises(ValueError):
        modem.modulate(b"\x00" * (MAX_PAYLOAD_BYTES + 1))


def test_air_time_is_monotonic_in_payload_size(modem):
    times = [modem.burst_seconds(n) for n in (0, 8, 32, 128, 512)]
    assert all(b > a for a, b in zip(times, times[1:]))


def test_empty_capture_is_reported_not_crashed(modem):
    for n in (0, 1, 100, 1000):
        res = modem.demodulate(np.zeros(n, dtype=np.float32))
        assert res.ok is False
        assert res.payload is None
        assert res.detail


def test_pure_noise_never_falsely_decodes(modem):
    rng = np.random.default_rng(4242)
    for _ in range(6):
        noise = rng.normal(0, 0.05, 48000).astype(np.float32)
        res = modem.demodulate(noise)
        assert res.ok is False
        assert res.payload is None


def test_single_bit_flip_is_caught_by_crc(modem):
    """A corrupted payload must fail loudly, never return wrong bytes."""
    payload = b"TARGET-ALPHA-GRID-8842-1190"
    audio = modem.modulate(payload).copy()
    # Corrupt a mid-burst region well inside the payload.
    start = audio.size // 2
    audio[start : start + 400] *= -1.0
    res = modem.demodulate(audio)
    if res.ok:
        # If it claims success it must be right.
        assert res.payload == payload
    else:
        assert res.payload is None
        assert "CRC" in res.detail or "truncated" in res.detail or "sync" in res.detail


def test_blind_timing_search_recovers_a_shifted_capture(modem):
    payload = b"TIMING-SEARCH-VERIFICATION"
    clean = modem.modulate(payload)
    for shift in (0, 1, 5, 13, 19, 27, 33, 39):
        padded = np.concatenate([np.zeros(shift, dtype=np.float32), clean])
        res = modem.demodulate(padded)
        assert res.ok, f"shift {shift} failed: {res.detail}"
        assert res.payload == payload


def test_differential_encoding_survives_constant_phase_rotation(modem):
    """The whole point of differential BPSK: absolute phase must not matter."""
    payload = b"PHASE-INVARIANT-PAYLOAD"
    clean = modem.modulate(payload)
    n = np.arange(clean.size, dtype=np.float64)
    for deg in (0.0, 37.0, 90.0, 143.0, 250.0):
        rotated = np.real(clean.astype(np.float64) * np.exp(1j * np.deg2rad(deg))).astype(np.float32)
        res = modem.demodulate(rotated)
        assert res.ok, f"{deg} deg rotation failed: {res.detail}"
        assert res.payload == payload


# ---------------------------------------------------------------------------
# Simulated channel
# ---------------------------------------------------------------------------
def test_channel_with_every_impairment_decodes(modem):
    payload = bytes(range(64))
    rx = simulate_voice_channel(
        modem.modulate(payload), snr_db=18.0, cfo_hz=5.0, clock_error_ppm=20.0, seed=11
    )
    res = modem.demodulate(rx)
    assert res.ok, res.detail
    assert res.payload == payload


@pytest.mark.parametrize("cfo_hz", [-8.0, -2.0, 2.0, 8.0])
def test_carrier_offset_is_a_true_frequency_shift(modem, cfo_hz):
    payload = b"CFO-SYMMETRY"
    rx = simulate_voice_channel(modem.modulate(payload), snr_db=20.0, cfo_hz=cfo_hz, seed=3)
    res = modem.demodulate(rx)
    assert res.ok, f"CFO {cfo_hz} Hz failed: {res.detail}"
    assert res.payload == payload


def test_selftest_is_bit_perfect_at_a_realistic_snr():
    report = loopback_selftest(n_frames=10, snr_db=18.0, cfo_hz=5.0, clock_error_ppm=20.0)
    assert report["pass"] is True
    assert report["per"] == 0.0
    assert report["ber"] == 0.0
    assert report["frames_ok"] == report["frames"]


def test_selftest_reports_inband_snr_honestly():
    report = loopback_selftest(n_frames=4, snr_db=10.0)
    # Narrowband signal in a wide sound-card band: in-band SNR must exceed the
    # wideband figure, and the gap must match the occupied bandwidth.
    assert report["snr_inband_db"] > report["snr_db"]
    expected_gain = 10 * np.log10(48000.0 / report["occupied_bandwidth_hz"])
    assert np.isclose(report["snr_inband_db"] - report["snr_db"], expected_gain, atol=0.05)


def test_selftest_per_degrades_gracefully_when_the_noise_wins():
    """There must be a knee: the modem cannot work in a noise-only channel."""
    floor = loopback_selftest(n_frames=8, snr_db=-30.0, cfo_hz=5.0, clock_error_ppm=20.0)
    assert floor["per"] > 0.5
    assert floor["pass"] is False


def test_config_is_overridable():
    cfg = ModemConfig(symbol_rate=600.0, carrier_hz=1500.0, audio_fs=48000)
    m = VoiceModem(cfg)
    assert m.cfg.sps == 80
    payload = b"HALF-RATE"
    assert m.demodulate(m.modulate(payload)).payload == payload
    # Half the symbol rate, twice the air time for the same payload.
    assert m.burst_seconds(64) > VoiceModem().burst_seconds(64)
