"""Link metrics with strict, non-negotiable denominators.

Rules this class enforces (see also ``comms/__init__`` module docstring):

* Every transmitted frame stays in the PER/PDR denominator - frames that
  failed RS decode, framing validation or payload comparison are counted
  as failures, never dropped from statistics.
* ``ber_raw`` is a true bit-for-bit measurement: demodulated bits are
  compared against the transmitted bit sequence for **every** frame
  (pre-FEC, before any decoder can fail).
* ``ber_frame_effective`` measures post-FEC framing-layer bit errors:
  where the RS layer produced frame bytes the comparison is real (even
  when the CRC later rejects the frame); frames the RS layer could not
  decode contribute all of their bits as errors (documented upper-bound
  accounting - ``frame_bits_unmeasurable`` says how many bits were
  counted that way, so the number is never mistaken for a direct
  measurement).
* ``ber_payload_effective`` counts a frame without verified payload
  delivery as fully erroneous (erasure counting), which for a CRC-gated
  link equals PER by construction; both are reported because they are
  computed from independent counters and an invariant ties them.

All rates are computed in :meth:`as_dict`; a rate whose denominator is
zero comes back as ``None`` (rendered as an empty CSV cell) instead of a
fabricated 0.0.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

FAIL_REASONS = (
    "rs_uncorrectable",    # RS block(s) beyond t / decoder failure
    "rs_structural",       # RS output length wrong (structural defect)
    "frame_parse",         # magic/version/length/CRC-32 rejected the frame
    "payload_mismatch",    # frame parsed but payload differs from what was sent
)


def _rate(numer: int, denom: int) -> Optional[float]:
    return (numer / denom) if denom else None


def _ms(samples) -> tuple[Optional[float], Optional[float]]:
    if not samples:
        return None, None
    arr = np.asarray(samples, dtype=np.float64) * 1000.0
    return float(arr.mean()), float(np.percentile(arr, 95))


class LinkMetrics:
    """Accumulator for one sweep point (one Eb/N0 operating point).

    ``frame_bytes`` is the exact serialized frame size (header +
    payload + CRC) for the configured link profile; it fixes the
    denominator of the frame-level bit comparison.
    """

    def __init__(self, frame_bytes: int):
        if frame_bytes <= 0:
            raise ValueError("frame_bytes must be positive")
        self.frame_bytes = frame_bytes

        self.frames_sent = 0
        self.frames_ok = 0
        self.frames_failed = 0
        self.fail_reasons = {r: 0 for r in FAIL_REASONS}

        self.payload_bits_per_frame: Optional[int] = None
        self.payload_bits_sent = 0
        self.payload_bits_ok = 0
        self.payload_bits_failed = 0

        self.symbols_sent = 0
        self.bits_sent = 0
        self.raw_bit_errors = 0

        self.frame_bit_errors_measured = 0
        self.frame_bits_unmeasurable = 0

        self.rs_blocks = 0
        self.rs_block_failures = 0
        self.rs_corrected_symbols = 0

        self.tx_seconds: list = []
        self.rx_seconds: list = []

    # ---- recorders ---------------------------------------------------
    def frame_sent(self, payload_bits: int):
        self.frames_sent += 1
        self.payload_bits_sent += payload_bits
        if self.payload_bits_per_frame is None:
            self.payload_bits_per_frame = payload_bits

    def frame_delivered(self, payload_bits: int):
        self.frames_ok += 1
        self.payload_bits_ok += payload_bits

    def frame_failed(self, reason: str, payload_bits: int):
        if reason not in self.fail_reasons:
            raise ValueError(f"unknown failure reason {reason!r}")
        self.frames_failed += 1
        self.payload_bits_failed += payload_bits
        self.fail_reasons[reason] += 1

    def raw_bits(self, n_bits: int, n_errors: int):
        """Pre-FEC comparison over the full transmitted bit sequence."""
        if not (0 <= n_errors <= n_bits):
            raise ValueError(f"bit errors {n_errors} outside 0..{n_bits}")
        self.bits_sent += n_bits
        self.raw_bit_errors += n_errors

    def symbols(self, n_symbols: int):
        self.symbols_sent += n_symbols

    def frame_bits(self, n_errors: int, n_unmeasurable_bits: int = 0):
        """Post-FEC framing-layer bit comparison (or its upper bound)."""
        if n_errors < 0 or n_unmeasurable_bits < 0:
            raise ValueError("bit counts must be non-negative")
        self.frame_bit_errors_measured += n_errors
        self.frame_bits_unmeasurable += n_unmeasurable_bits

    def rs(self, n_blocks: int, n_failed_blocks: int, corrected: int = 0):
        """Record one frame's RS outcome (per-codeword accounting).

        ``rs_fer`` is therefore a true per-codeword frame-error rate:
        failed codewords are counted as such, not inferred from frames.
        """
        if n_blocks < 0 or not (0 <= n_failed_blocks <= n_blocks):
            raise ValueError(f"invalid RS accounting: {n_failed_blocks}/{n_blocks}")
        if corrected < 0:
            raise ValueError("corrected must be non-negative")
        self.rs_blocks += n_blocks
        self.rs_block_failures += n_failed_blocks
        self.rs_corrected_symbols += corrected

    def latency(self, kind: str, seconds: float):
        if seconds < 0:
            raise ValueError("latency must be non-negative")
        (self.tx_seconds if kind == "tx" else self.rx_seconds).append(seconds)

    # ---- derived statistics -----------------------------------------
    @property
    def frame_bits_total(self) -> int:
        """Denominator of the frame-level BER: every frame bit sent."""
        return self.frames_sent * self.frame_bytes * 8

    def check_invariants(self) -> list:
        """Return a list of violated accounting invariants (empty = sound)."""
        problems = []
        if self.frames_sent != self.frames_ok + self.frames_failed:
            problems.append(
                f"frames_sent {self.frames_sent} != ok {self.frames_ok} "
                f"+ failed {self.frames_failed}")
        if sum(self.fail_reasons.values()) != self.frames_failed:
            problems.append(
                f"failure reasons sum {sum(self.fail_reasons.values())} "
                f"!= frames_failed {self.frames_failed}")
        if self.payload_bits_sent != self.payload_bits_ok + self.payload_bits_failed:
            problems.append(
                f"payload bits sent {self.payload_bits_sent} != ok "
                f"{self.payload_bits_ok} + failed {self.payload_bits_failed}")
        if (self.payload_bits_per_frame is not None
                and self.payload_bits_sent
                != self.frames_sent * self.payload_bits_per_frame):
            problems.append(
                f"payload bits sent {self.payload_bits_sent} != frames_sent "
                f"{self.frames_sent} * per-frame {self.payload_bits_per_frame}")
        if self.raw_bit_errors > self.bits_sent:
            problems.append("raw_bit_errors exceed bits_sent")
        if self.frame_bit_errors_measured + self.frame_bits_unmeasurable \
                > self.frame_bits_total:
            problems.append(
                "frame-level bit errors exceed bits transmitted at frame layer")
        if self.rs_block_failures > self.rs_blocks:
            problems.append("rs_block_failures exceed rs_blocks")
        return problems

    def as_dict(self) -> dict:
        """Flat, CSV-ready statistics (stable key set for every point)."""
        frame_err_total = (self.frame_bit_errors_measured
                           + self.frame_bits_unmeasurable)

        tx_mean, tx_p95 = _ms(self.tx_seconds)
        rx_mean, rx_p95 = _ms(self.rx_seconds)
        proc_total = sum(self.tx_seconds) + sum(self.rx_seconds)

        out = {
            "frames_sent": self.frames_sent,
            "frames_ok": self.frames_ok,
            "frames_failed": self.frames_failed,
            "per": _rate(self.frames_failed, self.frames_sent),
            "pdr": _rate(self.frames_ok, self.frames_sent),

            "payload_bits_sent": self.payload_bits_sent,
            "payload_bits_ok": self.payload_bits_ok,
            "payload_bits_failed": self.payload_bits_failed,
            "ber_payload_effective": _rate(self.payload_bits_failed,
                                           self.payload_bits_sent),

            "symbols_sent": self.symbols_sent,
            "bits_sent": self.bits_sent,
            "raw_bit_errors": self.raw_bit_errors,
            "ber_raw": _rate(self.raw_bit_errors, self.bits_sent),

            "frame_bit_errors_measured": self.frame_bit_errors_measured,
            "frame_bits_unmeasurable": self.frame_bits_unmeasurable,
            "ber_frame_effective": _rate(frame_err_total, self.frame_bits_total),

            "rs_blocks": self.rs_blocks,
            "rs_block_failures": self.rs_block_failures,
            "rs_fer": _rate(self.rs_block_failures, self.rs_blocks),
            "rs_corrected_symbols": self.rs_corrected_symbols,

            "goodput_efficiency": _rate(int(self.payload_bits_ok),
                                        int(self.bits_sent)),
            "goodput_processing_bps": (
                self.payload_bits_ok / proc_total if proc_total > 0 else None),

            "latency_tx_mean_ms": tx_mean,
            "latency_tx_p95_ms": tx_p95,
            "latency_rx_mean_ms": rx_mean,
            "latency_rx_p95_ms": rx_p95,
        }
        for reason in FAIL_REASONS:
            out[f"fail_{reason}"] = self.fail_reasons[reason]
        return out
