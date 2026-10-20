"""RS(255,223) benchmark: correctness, error injection, timing, legacy interop.

Usage::

    python3 -m comms.bench_rs --out results/rs255_223_benchmark.json

Produces machine-readable JSON. Every field is measured on this host in
this run; behavior beyond the t=16 correction capability is *observed
and reported* per trial as ``correct`` / ``miscorrected`` / ``failed``
rather than assumed (a soft decoder can miscorrect beyond t - the
framing CRC-32 is the independent safeguard that rejects such output
end-to-end).

The "legacy" section benchmarks the existing ``app.py`` ``CryptoEngine``
in place: its codewords are compared byte-for-byte against this
package's encoder, its round-trip is verified, and its behavior on
corrupted ciphertext is *recorded as observed* (the legacy decrypt path
substitutes zero blocks for uncorrectable codewords instead of failing -
documented here, not silently relied upon). Timing numbers are
single-host Python wall-clock (``perf_counter``) - not hardware claims.
"""

from __future__ import annotations

import argparse
import base64
import json
import platform
import sys
import time
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path

import numpy as np

from .fec.rs import (CODE_RATE, NCODE, NDATA, NERR, NPARITY,
                     ReedSolomon255_223, inject_symbol_errors)

_INJECTION_NS = (1, 4, 8, 16, 17, 20, 32)


def _environment() -> dict:
    vers = {"python": sys.version.split()[0], "platform": platform.platform()}
    for pkg in ("numpy", "reedsolo", "cryptography", "torch"):
        try:
            vers[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            vers[pkg] = None
    return vers


def _time(fn, iters: int) -> float:
    """Mean seconds per call (one warm-up call, then ``iters`` timed)."""
    fn()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    return (time.perf_counter() - t0) / iters


def run_benchmark(trials: int = 25, timing_iterations: int = 200,
                  seed: int = 20261020) -> dict:
    rng = np.random.default_rng(seed)
    rs = ReedSolomon255_223()

    # ---- correctness: round-trip across boundary lengths --------------
    lengths = (0, 1, 222, 223, 224, 999, 4096)
    rt_ok = rt_fail = 0
    for n in lengths:
        data = rng.bytes(n)
        res = rs.decode(rs.encode(data), exact_len=n)
        if not res.failed and res.data == data:
            rt_ok += 1
        else:
            rt_fail += 1

    # ---- error injection: observed decoder behavior beyond t ----------
    injection_rows = []
    for n in _INJECTION_NS:
        correct = miscorrected = failed = corrected_reported = 0
        for _ in range(trials):
            data = rng.bytes(NDATA * 3)
            enc = rs.encode(data)
            block = int(rng.integers(0, 3))
            bad = inject_symbol_errors(enc, n, rng, block=block)
            res = rs.decode(bad, exact_len=len(data))
            if res.failed:
                failed += 1
            elif res.data == data:
                correct += 1
                corrected_reported += res.corrected_symbols
            else:
                miscorrected += 1
        injection_rows.append({
            "symbol_errors_injected": n,
            "trials": trials,
            "correct": correct,
            "miscorrected": miscorrected,
            "failed": failed,
            "corrected_symbols_reported": corrected_reported,
        })

    # ---- malformed inputs ---------------------------------------------
    structural_total = structural_detected = 0
    for n in (100, 254, 256, 511, 300):
        structural_total += 1
        res = rs.decode(rng.bytes(n))
        if res.failed and res.reason == "structural" and res.data is None:
            structural_detected += 1
    big = rng.bytes(NDATA * 3)
    trunc = rs.encode(big)[:700]                     # 3 blocks -> cut mid-stream
    trunc_res = rs.decode(trunc)
    trunc_detected = bool(trunc_res.failed
                          and trunc_res.reason == "structural")
    empty_res = rs.decode(b"")

    # ---- timing --------------------------------------------------------
    small = rng.bytes(76)                            # one baseline frame
    big_payload = rng.bytes(10_000)
    enc_small_c = rs.encode(small)
    enc_big_c = rs.encode(big_payload)
    it_big = max(5, timing_iterations // 10)

    t_enc_small = _time(lambda: rs.encode(small), timing_iterations)
    t_dec_small = _time(lambda: rs.decode(enc_small_c, exact_len=len(small)),
                        timing_iterations)
    t_enc_big = _time(lambda: rs.encode(big_payload), it_big)
    t_dec_big = _time(lambda: rs.decode(enc_big_c, exact_len=len(big_payload)),
                      it_big)

    def _perf(op_s: float, bytes_per_op: float) -> dict:
        return {"seconds_per_op": op_s,
                "ops_per_second": (1.0 / op_s) if op_s > 0 else None,
                "input_bytes_per_op": bytes_per_op,
                "mb_per_second": (bytes_per_op / op_s / 1e6) if op_s > 0 else None}

    # ---- legacy app.py CryptoEngine interop ----------------------------
    legacy = _legacy_section(rng, rs)

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "environment": _environment(),
        "parameters": {
            "nsym": NPARITY, "ndata": NDATA, "nparity": NPARITY,
            "ncode": NCODE, "t_correctable_per_codeword": NERR,
            "code_rate": CODE_RATE,
            "parity_overhead_pct": round(100.0 * NPARITY / NDATA, 4),
            "field": "GF(2^8), fcr=0, prim=0x11d, generator=2 (reedsolo)",
        },
        "correctness": {
            "lengths_tested": list(lengths),
            "roundtrip_ok": rt_ok,
            "roundtrip_failures": rt_fail,
        },
        "injection": {
            "trials": trials,
            "note": ("inject_symbol_errors flips n distinct symbols of one "
                     "codeword; 'miscorrected' = decoder returned data that "
                     "differs from the original (only possible beyond t; the "
                     "framing CRC-32 rejects such frames end-to-end)"),
            "per_n": injection_rows,
        },
        "malformed": {
            "non_multiple_of_255_inputs": structural_total,
            "structural_failures_detected": structural_detected,
            "truncated_stream_detected": trunc_detected,
            "empty_input_failed": bool(empty_res.failed),
            "empty_input_roundtrips_empty": (not empty_res.failed
                                             and empty_res.data == b""),
        },
        "timing": {
            "method": ("time.perf_counter, single process, single host, "
                       "Python/reedsolo - not a hardware claim"),
            "encode_frame_76B": _perf(t_enc_small, len(small)),
            "decode_frame_76B_to255B": _perf(t_dec_small, len(enc_small_c)),
            "encode_10000B": _perf(t_enc_big, len(big_payload)),
            "decode_12675B_to10000B": _perf(t_dec_big, len(enc_big_c)),
        },
        "legacy_app_engine": legacy,
        "notes": [
            "RS provides correction up to t=16 symbols/codeword and reliable "
            "detection beyond via syndrome re-check plus CRC-32; no claim is "
            "made that every pattern above t is detected by RS alone.",
            "The comms RS layer reports failures (data=None) and never "
            "substitutes payload bytes; the legacy app.py decrypt path "
            "substitutes zero blocks - interop section records its observed "
            "behavior.",
            "FEC success is integrity/correction, not authenticity.",
        ],
    }
    return report


def _legacy_section(rng, rs: ReedSolomon255_223) -> dict:
    try:
        from app import CryptoEngine
    except Exception as exc:                            # pragma: no cover
        return {"imported": False, "error": repr(exc)}

    eng = CryptoEngine()
    probe = "ASTRA legacy corruption probe"

    # codeword equivalence: our RS encoder vs the legacy engine's codec
    equiv_trials = 50
    identical = 0
    for _ in range(equiv_trials):
        block = rng.bytes(NDATA)
        if rs.codec.encode(block) == eng.rsc.encode(block):
            identical += 1

    # round-trip through the legacy engine
    rt_texts = ("", "a", "hello world", "x" * 500)
    rt_ok = sum(1 for t in rt_texts if eng.decrypt(eng.encrypt(t)) == t)

    # corruption beyond t=16: legacy decrypt must never return the original
    ct = base64.b64decode(eng.encrypt(probe))
    buf = bytearray(ct)
    for p in rng.choice(NCODE, size=20, replace=False):
        buf[int(p)] ^= 0xFF
    beyond_out = eng.decrypt(base64.b64encode(bytes(buf)).decode())

    # corruption within t=16: legacy engine corrects, decrypt recovers
    buf2 = bytearray(ct)
    for p in rng.choice(NCODE, size=16, replace=False):
        buf2[int(p)] ^= 0xFF
    within_out = eng.decrypt(base64.b64encode(bytes(buf2)).decode())

    # our layer on the same corrupted stream: honest failure
    ours_res = rs.decode(bytes(buf), exact_len=223)

    return {
        "imported": True,
        "codeword_equivalence": {
            "trials": equiv_trials,
            "identical_codewords": identical,
            "note": ("identical_codewords == trials means our encoder emits "
                     "byte-identical RS codewords to app.py's RSCodec"),
        },
        "legacy_roundtrip": {"texts": len(rt_texts), "ok": rt_ok},
        "corruption_within_t": {
            "errors_injected": 16,
            "legacy_returned_original_plaintext": within_out == probe,
        },
        "corruption_beyond_t": {
            "errors_injected": 20,
            "legacy_returned_original_plaintext": beyond_out == probe,
            "legacy_observed_output_preview": str(beyond_out)[:80],
            "our_layer_failed": bool(ours_res.failed),
            "our_layer_reason": ours_res.reason,
            "note": ("legacy decrypt substitutes zero blocks for uncorrectable "
                     "codewords and swallows per-block failures; observed "
                     "output recorded, not assumed"),
        },
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="comms.bench_rs",
        description="RS(255,223) benchmark with machine-readable output.")
    p.add_argument("--out", type=Path, default=None,
                   help="write JSON here (default: stdout)")
    p.add_argument("--trials", type=int, default=25)
    p.add_argument("--iterations", type=int, default=200)
    p.add_argument("--seed", type=int, default=20261020)
    a = p.parse_args(argv)
    report = run_benchmark(trials=a.trials, timing_iterations=a.iterations,
                           seed=a.seed)
    text = json.dumps(report, indent=2)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
        print(f"wrote {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
