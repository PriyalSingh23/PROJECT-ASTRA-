"""Motorola-carried LPI carrier: loopback, key rejection, and EW battery.

These tests assert only what was *measured* on this machine. Where a measurement
is a physics or instrument fact rather than a pass/fail target, the test records
the measured value and its interpretation instead of asserting an unreachable
threshold -- see ``test_ew_battery_measured_state`` for the entropy case.

No test here touches ``lpi_v4/run/`` checkpoints or the wideband USRP path, both
of which need hardware or a trained model that this file deliberately avoids.
"""
import numpy as np
import pytest

from integration.motorola.lpi_carrier import (
    LpiCarrier,
    LpiCarrierConfig,
    _hilbert,
    audio_ew_report,
    carrier_selftest,
)

MESSAGE = "MOTOROLA-LPI-LINK-OK"


@pytest.fixture(scope="module")
def carrier():
    return LpiCarrier(LpiCarrierConfig())


def test_loopback_decodes_without_a_channel(carrier):
    """TX -> RX with no channel: the payload must come back exactly."""
    audio = carrier.modulate(MESSAGE.encode("latin-1"), seed=1)
    res = carrier.demodulate(audio)
    assert res.ok, res.detail
    assert res.payload.decode("latin-1") == MESSAGE


def test_raw_ber_is_zero_at_default_spreading(carrier):
    """The keyed despreader must recover the exact coded bits.

    This is the measurement the sub-symbol timing refinement exists to protect:
    before it, pilot 0 locked a half-symbol early and left a 1.3 % raw BER.
    """
    msg = MESSAGE.encode("latin-1")
    audio = carrier.modulate(msg, seed=1)
    cfg = carrier.cfg
    tx = carrier.frame_bits(msg).reshape(-1)
    n_frames = int(np.ceil(tx.size / cfg.n_bits))
    tx = np.concatenate([tx, np.zeros(n_frames * cfg.n_bits - tx.size, dtype=np.uint8)])
    frames, _ = carrier._sync_and_sample(np.asarray(audio, dtype=np.float64))
    assert frames is not None and len(frames) == n_frames
    rx, n = carrier._syms_to_bits(frames)
    assert n == n_frames
    assert float((rx[: tx.size] != tx).mean()) == 0.0


def test_wrong_key_is_rejected(carrier):
    """A receiver without the session key must not recover the payload.

    Two independent protections are checked: the keyed pilot does not correlate,
    and even if it did the payload would not decrypt.
    """
    audio = carrier.modulate(MESSAGE.encode("latin-1"), seed=1)
    other = LpiCarrier(LpiCarrierConfig(key="NOT-THE-SESSION-KEY"))
    res = other.demodulate(audio)
    assert not res.ok
    assert res.payload is None


def test_quad_axis_is_deterministic_in_key_and_frame(carrier):
    """The circularising Q stream must be reproducible, not random.

    The receiver regenerates Q from (key, frame); if it were drawn from a random
    source the symbol would not be circular in the same way at both ends.
    """
    a = carrier._quad_bits(0, carrier.cfg.n_bits)
    b = carrier._quad_bits(0, carrier.cfg.n_bits)
    c = carrier._quad_bits(1, carrier.cfg.n_bits)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    other = LpiCarrier(LpiCarrierConfig(key="DIFFERENT"))
    assert not np.array_equal(a, other._quad_bits(0, carrier.cfg.n_bits))


def test_payload_is_circular_complex(carrier):
    """The transmitted symbol must be circular: this is what fixes C42.

    Measured: the original real-only payload gave |C42| ~ 0.9-1.0 (fail); the
    complex payload gives ~0.09 (pass). Asserted against the metric itself so a
    regression in the Q axis is caught here rather than in the battery.
    """
    from lpi_stats import metric_hos_c42, metric_iq_circularity

    def frames(y, frame=512):
        n = max(1, (len(y) - frame) // frame + 1)
        seg = np.stack([y[i * frame:i * frame + frame] for i in range(n)])[:256]
        return np.stack([seg, np.imag(_hilbert(seg))], axis=1).astype(np.float32)

    bits = carrier.frame_bits(MESSAGE.encode("latin-1"))
    rng = np.random.default_rng(7)
    chips = []
    for i in range(int(np.ceil(bits.size / carrier.cfg.n_bits))):
        v, vq = carrier._frame_chips(bits, i, rng)
        chips.append((v + 1j * vq) / np.sqrt(2.0))
    ch = np.concatenate(chips)
    F = frames(np.real(ch))
    assert abs(metric_hos_c42(F)) < 0.3
    assert metric_iq_circularity(F) < 0.15


def test_selftest_survives_channel_and_reports_honestly():
    """End-to-end through the audio channel, with the honesty flags present."""
    res = carrier_selftest(message=MESSAGE, snr_db=24.0, cfo_hz=10.0,
                           clock_error_ppm=30.0, seed=7)
    assert res["ok"], res
    assert res["per"] == 0.0
    assert res["trials"][0]["decoded"] == MESSAGE
    # The result must state what it measured and what it did not.
    assert "audio_channel_ber_per" in res["measured_here"]
    assert "radio PA / squelch behaviour" in res["needs_hardware"]
    assert res["waveform_source"] == "keyed_spread_plus_dither_at_audio_scale"


def test_ew_battery_measured_state():
    """Record the eight-domain verdict and its physical limitations.

    Asserted:
      * circularity, PAPR, SCF, C42, kurtosis and KS all pass on the emitted
        audio -- six of the eight domains;
      * the two remaining domains are recorded against the bandwidth-matched
        noise-floor control rather than the wideband threshold.

    Not asserted (deliberately): the ``entropy`` and ``wvd`` thresholds.
    Measured here and derived in closed form, both are monotonic functions of how
    much of the analysis band the signal occupies, and both are unreachable for
    any signal that fits a 3 kHz voice channel:

      * entropy ceiling of a B-of-fs signal is log(B/fs * n_fft)/log(n_fft);
        3.3 kHz in 48 kHz gives 0.571, and the 0.95 criterion needs 35.1 kHz of
        occupancy (73 % of the band);
      * wvd_ratio of band-limited noise is 4.94 at 3.3 kHz, 3.11 at 9.6 kHz, and
        only crosses the 3.7 threshold above ~8 kHz occupancy.

    So the test pins the measured values and checks the burst against a
    band-limited noise floor of its *own* bandwidth -- the physically meaningful
    reference for a narrowband channel. Asserting the wideband thresholds here
    would only be satisfiable by faking the measurement.
    """
    res = carrier_selftest(message=MESSAGE, seed=7)
    ew = res["ew"]["signal"]
    assert ew["pass"]["circ"] and ew["pass"]["papr"]
    assert ew["pass"]["scf"] and ew["pass"]["c42"]
    assert ew["pass"]["kurt"], f"kurtosis {ew['kurt']:.3f} outside 3.0 +/- 0.15"
    assert ew["pass"]["ks"], f"KS p {ew['ks_p']:.4f} below the 0.05 criterion"
    assert ew["n_pass"] >= 6
    # Recorded, not asserted-as-passing:
    assert 0.4 < ew["entropy"] < 0.7             # 3 kHz occupancy in a 24 kHz band
    # The honest reference: the burst must be as noise-like as the noise floor of
    # its own channel. kurtosis and C42 must be at least as good as that control.
    floor = res["ew"]["noise_floor_control"]
    assert abs(ew["kurt"] - 3.0) <= abs(floor["kurt"] - 3.0) + 0.15
    assert abs(ew["c42"]) <= abs(floor["c42"]) + 0.3


def test_normalised_channel_view_is_honest_and_complete():
    """The two channel-limited domains must be reported against their ceiling.

    The raw ``entropy`` and ``wvd`` thresholds are calibrated for a signal that
    fills its own analysis band. Inside a 3 kHz voice channel they are unreachable
    by *any* waveform, so reporting only the raw number would make a correct
    transmission look like a failing one. The normalised view re-expresses them
    against what is actually achievable here -- and it must be complete and
    self-consistent, never a bare pass/fail.
    """
    res = carrier_selftest(message=MESSAGE, seed=7)
    n = res["ew"]["normalised"]
    sig = res["ew"]["signal"]

    # Both raw values must still be present and unchanged -- nothing is hidden.
    assert n["entropy"]["raw"] == round(sig["entropy"], 4)
    assert n["wvd"]["raw"] == round(sig["wvd"], 4)

    # entropy: fraction of the closed-form ceiling log(B/fs * n_fft)/log(n_fft)
    ceil = n["entropy"]["ceiling"]
    assert 0.5 < ceil < 0.6, f"entropy ceiling {ceil:.4f} outside expectation"
    assert abs(n["entropy"]["ratio"] - sig["entropy"] / ceil) < 1e-3
    assert n["entropy"]["pass"], (
        f"entropy only reaches {n['entropy']['ratio']:.3f} of its ceiling -- the "
        f"burst is not as noise-like as this channel allows")

    # wvd: ratio against the shaper-matched noise floor, NOT the brick-wall one.
    assert abs(n["wvd"]["ratio"] - sig["wvd"] / n["wvd"]["floor"]) < 1e-3
    assert n["wvd"]["pass"], (
        f"WVD is {n['wvd']['ratio']:.3f}x its own noise floor")
    assert n["n_pass"] == 2


def test_noise_floor_control_uses_the_same_shaper_as_the_burst():
    """The control must be shaped like the burst, or it is not a fair yardstick.

    Measured: a brick-wall-filtered noise control reports WVD 5.39 while an
    RRC-shaped one of the identical bandwidth reports 6.00 -- and *pure Gaussian
    symbols* pushed through the burst's own shaper score 5.91, the same as the
    burst. Charging the burst against a brick-wall control therefore penalises it
    for using a realisable pulse shape at all. The control must be shaped.
    """
    cfg = LpiCarrierConfig()
    from integration.motorola.lpi_carrier import _bandlimited_noise_floor

    floor = _bandlimited_noise_floor(cfg, 256)
    assert floor.shape == (256, 2, 512)
    # A brick-wall 300-3000 Hz control measures ~5.4; a shaped one measures ~6.0.
    from lpi_stats import metric_wvd_ratio

    assert metric_wvd_ratio(floor) > 5.8, (
        "the noise-floor control looks brick-wall filtered, not shaper-matched")



def test_burst_fits_inside_the_voice_channel():
    """The occupied band must sit inside 300-3000 Hz with margin to spare.

    A Motorola voice channel is 300-3000 Hz. If the burst is wider than that, or
    centred off the channel's own centre (1650 Hz), the radio's filters truncate
    its skirts asymmetrically -- measured as a collapse of the ``bandpass`` view's
    KS p (0.039) relative to the unfiltered signal (0.154).
    """
    cfg = LpiCarrierConfig()
    lo = cfg.carrier_hz - cfg.occupied_hz / 2.0
    hi = cfg.carrier_hz + cfg.occupied_hz / 2.0
    assert lo >= 300.0, f"lower skirt {lo:.0f} Hz falls below the channel"
    assert hi <= 3000.0, f"upper skirt {hi:.0f} Hz exceeds the channel"
    # And the carrier must be at the channel's true centre, not merely inside it.
    assert abs(cfg.carrier_hz - 1650.0) < 1.0


def test_channel_does_not_alter_the_waveform():
    """Filtering to the voice channel must not change the burst's statistics.

    Because the burst exactly fills the channel, the ``bandpass`` view of the
    battery must agree with the raw ``signal`` view. A divergence here means the
    radio's own filtering is eating part of the waveform.
    """
    res = carrier_selftest(message=MESSAGE, seed=7)
    sig = res["ew"]["signal"]
    bp = res["ew"]["bandpass"]
    assert sig["n_pass"] == bp["n_pass"]
    assert abs(sig["kurt"] - bp["kurt"]) < 0.1
    assert abs(sig["c42"] - bp["c42"]) < 0.1



    """The PTT guard and inter-frame gaps must carry masking noise, never silence.

    This is the fix for the KS domain, and the failure it prevents is specific:
    a silent span inside the burst puts a loud/silent step in the audio, and the
    battery's 512-sample analytic frames that straddle that step have strongly
    non-Gaussian shoulders. A controlled experiment that varied *only* the guard
    measured KS p = 0.637 (no guard) against 0.000 (zero guard).

    The test asserts the emitted audio never drops to digital silence, and that
    the guard is statistically continuous with the payload.
    """
    cfg = LpiCarrierConfig()
    car = LpiCarrier(cfg)
    audio = np.asarray(car.modulate(MESSAGE.encode("latin-1"), seed=7),
                       dtype=np.float64)
    frame = 512
    n = audio.size // frame
    segs = np.stack([audio[i * frame:(i + 1) * frame] for i in range(n)])
    rms = np.sqrt((segs ** 2).mean(axis=1))
    # No frame may be silent: the quietest frame must stay within 20 dB of the median.
    assert rms.min() > 0.1 * np.median(rms), (
        f"silent frame detected: min RMS {rms.min():.4f} vs median "
        f"{np.median(rms):.4f} -- a guard region is transmitting silence")


def test_pilot_is_not_constant_modulus():
    """The keyed pilot must be spread, not a bare constant-modulus ZC block.

    A bare ZC sequence has constant modulus, so any analysis frame landing on it
    measures kurtosis ~2.0. Measured on the emitted burst, the ten worst frames
    all sat at the pilot's recurring position with kurt ~2.05, and swapping the
    pilot block for an equal-power Gaussian block moved KS p from 0.069 to 0.219.
    Spreading the ZC through the same keyed codebook removes that outlier while
    preserving both the correlation peak and the keying.
    """
    cfg = LpiCarrierConfig()
    car = LpiCarrier(cfg)
    pilot = car._make_pilot()
    ratio = float(np.abs(pilot).max() / (np.abs(pilot).mean() + 1e-12))
    # A constant-modulus sequence gives exactly 1.0; the spread pilot is not flat.
    assert ratio > 1.5, f"pilot looks constant-modulus (peak/mean {ratio:.2f})"
    # And it must still be deterministic in the key, or the receiver cannot sync.
    assert np.array_equal(pilot, LpiCarrier(cfg)._make_pilot())
    other = LpiCarrier(LpiCarrierConfig(key="SOME-OTHER-KEY"))._make_pilot()
    assert not np.allclose(pilot, other)


def test_awgn_cannot_meet_the_entropy_criterion_at_audio_rate():
    """Prove the entropy domain is instrument-limited at 48 kHz, not waveform-limited.

    If white noise itself cannot score > 0.95 under this analysis geometry, then
    the criterion cannot discriminate a waveform here. This test documents that
    with a measurement so the claim in the module docstring is checkable.
    """
    from lpi_stats import metric_spectral_entropy

    rng = np.random.default_rng(0)
    seg = rng.standard_normal((64, 512))
    F = np.stack([seg, np.imag(_hilbert(seg))], axis=1).astype(np.float32)
    ent = metric_spectral_entropy(F, 512)
    assert ent < 0.95, f"AWGN scored {ent}; the criterion is reachable after all"


def test_decodes_at_any_carrier_offset_not_just_grid_multiples():
    """The receiver must decode at an *arbitrary* curb offset, not a lucky one.

    This pins the fix for a real, measured link-killing defect. The old receiver
    swept a 2 Hz grid and kept the candidate with the best keyed-pilot score --
    but the pilot score is flat in frequency, so the grid usually left a residual
    offset in the baseband. A residual offset rotates phase across each frame
    while the pilot only fixes phase at the frame's *start*: measured loopback
    BER was 0.0000 at 0 Hz and 0.4375 (chance) at 2 Hz, with the pilot still
    locking at 10.0. Non-grid offsets (1, 3, 5, 7, 15 Hz) failed universally.

    The receiver now sweeps coarse to find the burst, then fine (0.25 Hz) to land
    inside the +/-0.2 Hz tolerance the decode budget requires. Each offset below
    is tested with several *message* seeds as well as channel seeds, because the
    old failure was seed-dependent -- a fixed-seed sweep reported 45/45 and was
    simply not measuring the defect.
    """
    from integration.motorola.voice_modem import simulate_voice_channel

    cfg = LpiCarrierConfig()
    msg = MESSAGE.encode("latin-1")
    for cfo in (1.0, 3.0, 7.0, 15.0):
        for k in range(3):
            car = LpiCarrier(cfg)
            audio = np.asarray(car.modulate(msg, seed=500 + k * 13), dtype=float)
            y = simulate_voice_channel(audio, snr_db=25.0, cfo_hz=cfo,
                                       clock_error_ppm=20.0, seed=700 + k * 5)
            res = car.demodulate(y)
            assert res.ok, (
                f"failed at {cfo} Hz offset, message seed {500 + k * 13}: "
                f"{res.detail} (cfo_meta={res.meta.get('cfo_hz')})")
            assert res.payload.decode("latin-1") == MESSAGE


def test_measured_cfo_matches_the_injected_offset():
    """The CFO the receiver reports must be the offset that was actually applied.

    A decode that succeeds while reporting the wrong offset would mean the
    success came from the decode-driven search, not from the carrier recovery --
    and would leave no way to diagnose a real failure. The reported offset is
    therefore asserted against truth to within the 0.2 Hz decode budget.
    """
    from integration.motorola.voice_modem import simulate_voice_channel

    cfg = LpiCarrierConfig()
    msg = MESSAGE.encode("latin-1")
    car = LpiCarrier(cfg)
    audio = np.asarray(car.modulate(msg, seed=42), dtype=float)
    for cfo in (0.0, 1.0, 2.5, 10.0, 30.0):
        y = simulate_voice_channel(audio, snr_db=25.0, cfo_hz=cfo,
                                   clock_error_ppm=0.0, seed=3)
        res = car.demodulate(y)
        assert res.ok, f"no decode at {cfo} Hz: {res.detail}"
        err = abs(res.meta["cfo_hz"] - cfo)
        assert err < 0.2, (
            f"at a true {cfo} Hz offset the receiver reported "
            f"{res.meta['cfo_hz']} Hz (error {err:.3f} Hz)")


def test_link_survives_ten_db_into_the_noise():
    """The link margin must reach negative SNR -- the point of the spreading.

    ``reps=8`` over 1024-chip keyed codes is a strong processing gain, and the
    reason to spend it on a 3 kHz voice channel is so the burst sits *below* the
    channel noise. Measured cliff on this machine is between -10 and -12 dB, so
    -8 dB is asserted as a working link with margin.
    """
    from integration.motorola.voice_modem import simulate_voice_channel

    cfg = LpiCarrierConfig()
    msg = MESSAGE.encode("latin-1")
    for k in range(3):
        car = LpiCarrier(cfg)
        audio = np.asarray(car.modulate(msg, seed=500 + k * 11), dtype=float)
        y = simulate_voice_channel(audio, snr_db=-8.0, cfo_hz=3.0,
                                   clock_error_ppm=20.0, seed=700 + k * 5)
        res = car.demodulate(y)
        assert res.ok, (
            f"no decode at -8 dB SNR, message seed {500 + k * 11}: {res.detail}")
