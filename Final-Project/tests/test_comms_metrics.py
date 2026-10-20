"""Metrics accounting: denominators always include failures, invariants
hold, undetermined rates are None (never fabricated 0.0)."""

import pytest

from comms.metrics import FAIL_REASONS, LinkMetrics


def test_empty_metrics_rates_are_none():
    d = LinkMetrics(frame_bytes=76).as_dict()
    assert d["per"] is None and d["pdr"] is None
    assert d["ber_raw"] is None and d["ber_frame_effective"] is None
    assert d["ber_payload_effective"] is None
    assert d["rs_fer"] is None
    assert d["goodput_efficiency"] is None
    assert d["goodput_processing_bps"] is None
    assert d["latency_tx_mean_ms"] is None


def test_per_pdr_include_failures_in_denominator():
    m = LinkMetrics(frame_bytes=10)
    for _ in range(4):
        m.frame_sent(64)
        m.frame_delivered(64)
    for _ in range(6):
        m.frame_sent(64)
        m.frame_failed("rs_uncorrectable", 64)
    d = m.as_dict()
    assert d["frames_sent"] == 10 and d["frames_ok"] == 4 and d["frames_failed"] == 6
    assert d["per"] == pytest.approx(0.6)         # failures not excluded
    assert d["pdr"] == pytest.approx(0.4)
    assert d["ber_payload_effective"] == pytest.approx(0.6)
    assert d["payload_bits_sent"] == 10 * 64
    assert d["payload_bits_failed"] == 6 * 64


def test_frame_level_ber_counts_unmeasurable_upper_bound():
    m = LinkMetrics(frame_bytes=10)               # 80 bits per frame
    m.frame_sent(64); m.frame_delivered(64); m.frame_bits(3)
    m.frame_sent(64); m.frame_failed("rs_uncorrectable", 64)
    m.frame_bits(0, n_unmeasurable_bits=80)       # whole frame unmeasurable
    d = m.as_dict()
    assert d["frame_bit_errors_measured"] == 3
    assert d["frame_bits_unmeasurable"] == 80
    assert d["ber_frame_effective"] == pytest.approx(83 / 160)
    assert m.check_invariants() == []


def test_invariants_catch_bad_accounting():
    m = LinkMetrics(frame_bytes=10)
    m.frame_sent(64)
    m.frame_delivered(64)
    m.frame_failed("frame_parse", 64)             # 2 sent, 2 terminal states
    problems = m.check_invariants()
    assert problems and "frames_sent" in problems[0]

    m2 = LinkMetrics(frame_bytes=10)
    m2.frame_sent(64); m2.frame_delivered(64); m2.frame_failed("frame_parse", 64)
    # force ok+failed bits ahead of sent bits
    m2.payload_bits_sent = 64
    assert any("payload bits" in p for p in m2.check_invariants())


def test_recorder_validation():
    m = LinkMetrics(frame_bytes=10)
    with pytest.raises(ValueError):
        m.frame_failed("not_a_reason", 64)
    with pytest.raises(ValueError):
        m.raw_bits(10, 11)
    with pytest.raises(ValueError):
        m.latency("tx", -1.0)
    with pytest.raises(ValueError):
        m.rs(2, 3)
    with pytest.raises(ValueError):
        LinkMetrics(frame_bytes=0)


def test_rs_recorder_per_codeword():
    m = LinkMetrics(frame_bytes=10)
    m.rs(3, 1, corrected=5)
    d = m.as_dict()
    assert d["rs_blocks"] == 3 and d["rs_block_failures"] == 1
    assert d["rs_fer"] == pytest.approx(1 / 3)
    assert d["rs_corrected_symbols"] == 5


def test_fail_reason_keys_present_and_stable():
    m = LinkMetrics(frame_bytes=10)
    d1 = m.as_dict()
    m.frame_sent(64)
    d2 = m.as_dict()
    assert set(d1.keys()) == set(d2.keys())
    for reason in FAIL_REASONS:
        assert f"fail_{reason}" in d1


def test_latency_stats():
    import numpy as np
    m = LinkMetrics(frame_bytes=10)
    for s in (0.001, 0.002, 0.003, 0.010):
        m.latency("tx", s)
    d = m.as_dict()
    assert d["latency_tx_mean_ms"] == pytest.approx(4.0)
    assert d["latency_tx_p95_ms"] >= d["latency_tx_mean_ms"] * 0.9
    assert np.isfinite(d["latency_tx_p95_ms"])


def test_goodput_processing_bps():
    m = LinkMetrics(frame_bytes=10)
    for _ in range(5):
        m.frame_sent(64); m.frame_delivered(64)
    m.latency("tx", 0.001); m.latency("rx", 0.001)
    d = m.as_dict()
    assert d["goodput_processing_bps"] == pytest.approx(5 * 64 / 0.002)
