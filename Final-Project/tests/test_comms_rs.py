"""RS(255,223) unit tests: correction, failure, structural errors, legacy
interop (app.py CryptoEngine codeword equivalence and safety properties)."""

import base64

import numpy as np
import pytest

from comms.fec.rs import (NCODE, NDATA, NERR, NPARITY, RSResult,
                          ReedSolomon255_223, inject_symbol_errors)


@pytest.fixture(scope="module")
def rs():
    return ReedSolomon255_223()


def test_parameters_documented():
    assert (NDATA, NPARITY, NCODE, NERR) == (223, 32, 255, 16)


def test_roundtrip_lengths(rs):
    rng = np.random.default_rng(1)
    for n in (0, 1, 222, 223, 224, 999, 4096):
        data = rng.bytes(n)
        res = rs.decode(rs.encode(data), exact_len=n)
        assert not res.failed, (n, res.reason)
        assert res.data == data


def test_encode_block_structure(rs):
    rng = np.random.default_rng(2)
    data = rng.bytes(NDATA)
    assert len(rs.encode(data)) == NCODE
    assert len(rs.encode(b"")) == 0
    assert rs.pad_length(0) == 0 and rs.pad_length(1) == NDATA - 1


def test_corrects_up_to_16_symbol_errors(rs):
    rng = np.random.default_rng(3)
    data = rng.bytes(NDATA * 2)
    enc = rs.encode(data)
    for n in (1, 8, NERR):
        bad = inject_symbol_errors(enc, n, rng, block=n % 2)
        res = rs.decode(bad, exact_len=len(data))
        assert not res.failed, (n, res.reason)
        assert res.data == data
        assert res.corrected_symbols == n
        assert res.failed_blocks == 0 and res.blocks == 2


def test_beyond_16_fails_closed(rs):
    rng = np.random.default_rng(4)
    data = rng.bytes(NDATA)
    enc = rs.encode(data)
    outcomes = {"failed": 0, "miscorrected": 0}
    for _ in range(25):
        bad = inject_symbol_errors(enc, NERR + 1, rng, block=0)
        res = rs.decode(bad, exact_len=len(data))
        if res.failed:
            outcomes["failed"] += 1
            assert res.data is None
            assert res.reason == "uncorrectable"
            assert res.failed_blocks == 1
        else:
            # Decoder may legally miscorrect beyond t; the payload it
            # returns must differ from the original (CRC-32 is the
            # end-to-end backstop for that case).
            outcomes["miscorrected"] += 1
            assert res.data != data
    assert outcomes["failed"] + outcomes["miscorrected"] == 25


def test_structural_bad_length(rs):
    rng = np.random.default_rng(5)
    for n in (1, 254, 256, 511):
        res = rs.decode(rng.bytes(n))
        assert res.failed and res.reason == "structural" and res.data is None


def test_short_output(rs):
    rng = np.random.default_rng(6)
    data = rng.bytes(NDATA)
    res = rs.decode(rs.encode(data), exact_len=len(data) + 1)
    assert res.failed and res.reason == "short_output" and res.data is None


def test_empty_input(rs):
    ok = rs.decode(b"")
    assert not ok.failed and ok.data == b""
    short = rs.decode(b"", exact_len=1)
    assert short.failed and short.reason == "short_output"
    with pytest.raises(ValueError):
        rs.decode(b"", exact_len=-1)


def test_rsresult_never_returns_data_with_failure():
    res = RSResult(None, True, 0, 0, "uncorrectable", 1)
    assert res.data is None and res.failed


# ---- legacy app.py CryptoEngine interop -------------------------------

def test_codewords_identical_to_legacy_engine(rs):
    from app import CryptoEngine
    eng = CryptoEngine()
    rng = np.random.default_rng(7)
    for _ in range(10):
        block = rng.bytes(NDATA)
        assert rs.codec.encode(block) == eng.rsc.encode(block)


def test_legacy_roundtrip_preserved():
    from app import CryptoEngine
    eng = CryptoEngine()
    assert eng.decrypt(eng.encrypt("ASTRA roundtrip")) == "ASTRA roundtrip"


def test_legacy_within_t_corruption_recovers():
    from app import CryptoEngine
    eng = CryptoEngine()
    probe = "ASTRA corruption probe"
    ct = base64.b64decode(eng.encrypt(probe))
    rng = np.random.default_rng(8)
    buf = bytearray(ct)
    for p in rng.choice(NCODE, size=NERR, replace=False):
        buf[int(p)] ^= 0xFF
    assert eng.decrypt(base64.b64encode(bytes(buf)).decode()) == probe


def test_legacy_beyond_t_never_silently_returns_plaintext():
    """Safety property: corruption > t must not decrypt to the original."""
    from app import CryptoEngine
    eng = CryptoEngine()
    probe = "ASTRA corruption probe"
    ct = base64.b64decode(eng.encrypt(probe))
    rng = np.random.default_rng(9)
    buf = bytearray(ct)
    for p in rng.choice(NCODE, size=NERR + 4, replace=False):
        buf[int(p)] ^= 0xFF
    out = eng.decrypt(base64.b64encode(bytes(buf)).decode())
    assert out != probe
    # The comms layer reports the same corruption as an honest failure.
    from comms.fec.rs import ReedSolomon255_223
    res = ReedSolomon255_223().decode(bytes(buf), exact_len=NDATA)
    assert res.failed and res.data is None
