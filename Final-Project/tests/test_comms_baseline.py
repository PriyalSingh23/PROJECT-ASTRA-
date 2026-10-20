"""Gate 1 baseline: bits, framing, modulation, channel, Eb/N0 accounting.

Theory cross-checks use the textbook formulas computed independently in
the test (not via comms.config helpers) so the accounting itself is
what gets validated.
"""

import math

import numpy as np
import pytest
from scipy.special import erfc

from comms.bits import bits_to_bytes, bytes_to_bits, pad_to_multiple
from comms.channel import awgn, measured_noise_variance
from comms.config import (LinkConfig, bits_per_symbol, config_from_preset,
                          ebn0_to_esn0_db, esn0_to_noise_variance)
from comms.framing import FrameError, build_frame, parse_frame
from comms.modulation import demodulate, modulate


# ---- bits ------------------------------------------------------------

def test_bytes_to_bits_msb_first():
    assert bytes_to_bits(b"\x80").tolist() == [1, 0, 0, 0, 0, 0, 0, 0]
    assert bytes_to_bits(b"\x01").tolist() == [0, 0, 0, 0, 0, 0, 0, 1]
    assert bytes_to_bits(b"\xA5").tolist() == [1, 0, 1, 0, 0, 1, 0, 1]


def test_bits_bytes_roundtrip():
    rng = np.random.default_rng(1)
    for n in (0, 1, 7, 64, 255, 1000):
        data = rng.bytes(n)
        assert bits_to_bytes(bytes_to_bits(data)) == data


def test_bits_to_bytes_rejects_malformed():
    with pytest.raises(ValueError):
        bits_to_bytes([1, 0, 1])               # not multiple of 8
    with pytest.raises(ValueError):
        bits_to_bytes([0, 2, 0, 0, 0, 0, 0, 0])  # non-binary


def test_pad_to_multiple():
    b = np.array([1, 1, 1], dtype=np.uint8)
    padded, n_pad = pad_to_multiple(b, 4)
    assert n_pad == 1 and padded.tolist() == [1, 1, 1, 0]
    padded, n_pad = pad_to_multiple(b, 3)
    assert n_pad == 0
    with pytest.raises(ValueError):
        pad_to_multiple(b, 0)


# ---- framing ---------------------------------------------------------

def test_frame_roundtrip():
    frame = build_frame(b"ASTRA", seq=42)
    parsed = parse_frame(frame)
    assert parsed.payload == b"ASTRA"
    assert parsed.seq == 42
    assert parsed.ftype == 0 and parsed.version == 1


def test_frame_empty_payload():
    parsed = parse_frame(build_frame(b"", seq=0))
    assert parsed.payload == b""


def test_frame_corruption_rejected():
    frame = build_frame(b"payload", seq=7)
    corrupt = bytearray(frame)
    corrupt[10] ^= 0xFF                       # flip a payload byte
    with pytest.raises(FrameError, match="CRC"):
        parse_frame(bytes(corrupt))


def test_frame_truncation_rejected():
    frame = build_frame(b"payload", seq=7)
    with pytest.raises(FrameError):
        parse_frame(frame[:-1])
    with pytest.raises(FrameError):
        parse_frame(frame[:6])


def test_frame_bad_magic_version_length_rejected():
    frame = build_frame(b"payload", seq=7)
    bad_magic = bytearray(frame); bad_magic[0] = 0x00
    with pytest.raises(FrameError, match="magic"):
        parse_frame(bytes(bad_magic))
    bad_ver = bytearray(frame); bad_ver[2] = 9
    with pytest.raises(FrameError, match="version"):
        parse_frame(bytes(bad_ver))
    bad_len = bytearray(frame); bad_len[6] = 99
    with pytest.raises(FrameError, match="length"):
        parse_frame(bytes(bad_len))


def test_frame_oversized_payload_rejected():
    with pytest.raises(FrameError):
        build_frame(b"x" * 70000, seq=0)


# ---- modulation ------------------------------------------------------

def test_modulation_roundtrip_and_unit_energy():
    rng = np.random.default_rng(3)
    for mod in ("bpsk", "qpsk"):
        k = bits_per_symbol(mod)
        bits = rng.integers(0, 2, size=k * 500, dtype=np.uint8)
        syms = modulate(bits, mod)
        assert syms.size == bits.size // k
        assert np.mean(np.abs(syms) ** 2) == pytest.approx(1.0, abs=1e-12)
        assert np.array_equal(demodulate(syms, mod), bits)


def test_modulation_rejects_bad_input():
    with pytest.raises(ValueError):
        modulate([1, 0, 1], "qpsk")           # odd count for k=2
    with pytest.raises(ValueError):
        modulate([0, 2], "bpsk")              # non-binary


# ---- channel ---------------------------------------------------------

def test_awgn_noise_variance_matches_esn0():
    rng = np.random.default_rng(5)
    syms = modulate(np.zeros(200000, dtype=np.uint8), "bpsk")
    for esn0_db, expected in ((0.0, 1.0), (10.0, 0.1), (-10.0, 10.0)):
        noise = awgn(syms, esn0_db, rng) - syms
        assert measured_noise_variance(noise) == pytest.approx(expected, rel=0.05)


def test_awgn_infinite_is_noiseless():
    syms = modulate(np.array([0, 1, 1, 0], dtype=np.uint8), "qpsk")
    out = awgn(syms, math.inf, np.random.default_rng(1))
    assert np.array_equal(out, syms)


# ---- Eb/N0 accounting ------------------------------------------------

def test_ebn0_to_esn0_db_exact_ratio():
    # 64-byte payload: frame = 8 hdr + 64 payload + 4 CRC = 76 B = 608 bits
    got = ebn0_to_esn0_db(6.0, 512, 608)
    want = 6.0 + 10.0 * math.log10(512 / 608)
    assert got == pytest.approx(want, abs=1e-12)
    assert got < 6.0                          # overhead reduces Es/N0
    # no overhead -> identical
    assert ebn0_to_esn0_db(3.0, 100, 100) == pytest.approx(3.0)
    with pytest.raises(ValueError):
        ebn0_to_esn0_db(6.0, 0, 100)
    with pytest.raises(ValueError):
        ebn0_to_esn0_db(6.0, 100, 0)
    with pytest.raises(ValueError):
        ebn0_to_esn0_db(math.inf, 100, 100)


def test_esn0_to_noise_variance_values():
    assert esn0_to_noise_variance(0.0) == pytest.approx(1.0)
    assert esn0_to_noise_variance(10.0) == pytest.approx(0.1)
    assert esn0_to_noise_variance(-10.0) == pytest.approx(10.0)


def test_config_geometry_and_presets():
    cfg = config_from_preset("debug")
    assert cfg.frames == 25 and cfg.ebn0_db == (0.0, 4.0, 8.0)
    assert cfg.frame_bytes == 76
    assert cfg.info_bits == 512
    assert cfg.coded_bytes() == 76                    # uncoded
    rs_cfg = config_from_preset("debug", mode="rs255_223")
    assert rs_cfg.coded_bytes() == 255                # 76 B -> 1 codeword
    big = config_from_preset("debug", mode="rs255_223", payload_bytes=500)
    assert big.coded_bytes() == 3 * 255               # 512 B frame -> 3 codewords
    with pytest.raises(ValueError):
        config_from_preset("nope")
    with pytest.raises(ValueError):
        LinkConfig(modulation="16qam")
    with pytest.raises(ValueError):
        LinkConfig(frames=0)
    with pytest.raises(ValueError):
        LinkConfig(ebn0_db=())


# ---- theory cross-check (independent formulas) ------------------------

def _theory_ber(ebn0_db, n_info_bits, n_coded_bits):
    """Q(sqrt(2*Es/N0)) with Es/N0 from first principles, not the library."""
    esn0_lin = (10.0 ** (ebn0_db / 10.0)) * n_info_bits / n_coded_bits
    return 0.5 * erfc(math.sqrt(esn0_lin))


def test_uncoded_bpsk_ber_matches_theory():
    from comms.pipeline import LinkSimulator
    cfg = LinkConfig(mode="uncoded", modulation="bpsk", frames=200)
    sim = LinkSimulator(cfg)
    m, _ = sim.run_point(4.0, 200, np.random.default_rng(101))
    ber = m.as_dict()["ber_raw"]
    theory = _theory_ber(4.0, 512, 608)      # frame = 76 B = 608 bits
    assert ber == pytest.approx(theory, rel=0.20), (ber, theory)


def test_uncoded_qpsk_ber_matches_theory():
    from comms.pipeline import LinkSimulator
    cfg = LinkConfig(mode="uncoded", modulation="qpsk", frames=600)
    sim = LinkSimulator(cfg)
    m, _ = sim.run_point(6.0, 600, np.random.default_rng(202))
    ber = m.as_dict()["ber_raw"]
    theory = _theory_ber(6.0, 512, 608)      # 608 bits -> 304 symbols
    assert ber == pytest.approx(theory, rel=0.25), (ber, theory)
