"""Pipeline behavior: noiseless floor, seeded reproducibility, failure
accounting at low SNR, RS correction at high SNR."""

import numpy as np
import pytest

from comms.config import LinkConfig
from comms.pipeline import LinkSimulator


def _strip_nondeterministic(d):
    """Latency and wall-clock throughput vary run to run by nature."""
    return {k: v for k, v in d.items()
            if not k.startswith("latency_") and k != "goodput_processing_bps"}


@pytest.mark.parametrize("mode", ["uncoded", "rs255_223"])
@pytest.mark.parametrize("mod", ["bpsk", "qpsk"])
def test_noiseless_perfect_delivery(mode, mod):
    cfg = LinkConfig(mode=mode, modulation=mod, frames=5)
    sim = LinkSimulator(cfg)
    m, _ = sim.run_point(None, 5, np.random.default_rng(11))
    d = m.as_dict()
    assert d["frames_ok"] == 5 and d["frames_failed"] == 0
    assert d["ber_raw"] == 0.0
    assert d["ber_frame_effective"] == 0.0
    assert d["per"] == 0.0 and d["pdr"] == 1.0
    assert m.check_invariants() == []


def test_seeded_reproducibility():
    cfg = LinkConfig(mode="rs255_223", frames=15)
    sim = LinkSimulator(cfg)
    m1, _ = sim.run_point(4.0, 15, np.random.default_rng(1234))
    m2, _ = sim.run_point(4.0, 15, np.random.default_rng(1234))
    assert _strip_nondeterministic(m1.as_dict()) == \
        _strip_nondeterministic(m2.as_dict())


def test_different_seed_different_realization():
    cfg = LinkConfig(mode="uncoded", frames=5)
    sim = LinkSimulator(cfg)
    _, a = sim.run_point(4.0, 5, np.random.default_rng(1),
                         collect_artifacts=True)
    _, b = sim.run_point(4.0, 5, np.random.default_rng(2),
                         collect_artifacts=True)
    assert not np.array_equal(a["tx_bits"], b["tx_bits"])


def test_low_snr_failures_stay_in_denominator():
    cfg = LinkConfig(mode="rs255_223", frames=10)
    sim = LinkSimulator(cfg)
    # RS(255,223) alone sits ~6 dB below the uncoded point (parity
    # overhead); at 0 dB Eb/N0 the codewords are far beyond t=16.
    m, _ = sim.run_point(0.0, 10, np.random.default_rng(21))
    d = m.as_dict()
    assert d["frames_sent"] == 10
    assert d["frames_ok"] + d["frames_failed"] == 10
    assert d["frames_failed"] > 0
    assert d["fail_rs_uncorrectable"] == d["frames_failed"]
    # every undecodable frame contributes its full frame size as an
    # unmeasurable upper bound - failures never vanish from the numbers
    assert d["frame_bits_unmeasurable"] == d["frames_failed"] * 76 * 8
    assert d["ber_frame_effective"] == pytest.approx(1.0)
    assert m.check_invariants() == []


def test_high_snr_rs_corrects():
    cfg = LinkConfig(mode="rs255_223", frames=20)
    sim = LinkSimulator(cfg)
    m, _ = sim.run_point(14.0, 20, np.random.default_rng(31))
    d = m.as_dict()
    assert d["frames_ok"] == 20 and d["frames_failed"] == 0
    assert d["per"] == 0.0 and d["pdr"] == 1.0
    assert m.check_invariants() == []


def test_raw_ber_present_even_when_frames_fail():
    cfg = LinkConfig(mode="rs255_223", frames=10)
    sim = LinkSimulator(cfg)
    m, _ = sim.run_point(2.0, 10, np.random.default_rng(41))
    d = m.as_dict()
    assert d["frames_failed"] == 10          # beyond t at this point
    assert d["ber_raw"] > 0.0                # ...but raw BER still measured
    assert d["bits_sent"] == 10 * 2040       # 255 B codeword -> 2040 bits


def test_artifact_shapes():
    cfg = LinkConfig(mode="uncoded", modulation="qpsk", frames=2)
    sim = LinkSimulator(cfg)
    _, art = sim.run_point(6.0, 2, np.random.default_rng(51),
                           collect_artifacts=True)
    assert art["tx_bits"].size == 608
    assert art["rx_bits"].size == 608
    assert art["tx_symbols"].size == 304      # 608 bits -> 304 QPSK symbols
    assert art["rx_symbols"].size == 304
    assert art["tx_wave"].size == 304 * 8     # sps=8 rect pulse
    assert art["ebn0_db"] == 6.0
