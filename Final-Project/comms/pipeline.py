"""Deterministic end-to-end link pipeline (Gate 1 baseline).

Chain, per frame::

    payload -> build_frame -> [RS encode] -> bits -> pad -> modulate
            -> AWGN -> demodulate -> strip pad -> [RS decode]
            -> parse_frame -> payload comparison -> metrics

Measurement rules (enforced here, explained in ``comms/metrics.py``):

* Raw (pre-FEC) BER compares every demodulated bit against what was
  actually transmitted (RS-coded bits when FEC is on), padded bits
  included - failures never excluded.
* Post-FEC frame BER compares framing bytes wherever the RS layer
  produced output, *even when the CRC later rejects the frame*; frames
  the RS layer could not decode contribute their whole frame size to a
  separately reported unmeasurable upper bound.
* Payload delivery requires parse + CRC-32 + byte-exact match against
  the known transmitted payload (simulation ground truth). FEC success
  is never treated as authenticity.
* Processing latency is measured with ``time.perf_counter`` around the
  per-frame transmit and receive chains on the local host - it is
  compute time, not over-the-air latency, and is labelled as such.
* Eb/N0 -> Es/N0 conversion uses the *actual* symbol count of each
  frame (coded bits plus symbol padding), so code rate, frame overhead
  and padding land in one exact ratio (:func:`comms.config.ebn0_to_esn0_db`).

``run_point(ebn0_db=None)`` runs a noiseless reference (used by the
regression tests to pin the zero-error floor).
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .bits import bits_to_bytes, bytes_to_bits, pad_to_multiple
from .channel import awgn
from .config import LinkConfig, bits_per_symbol, ebn0_to_esn0_db
from .fec.rs import ReedSolomon255_223
from .framing import FrameError, build_frame, parse_frame
from .metrics import LinkMetrics
from .modulation import demodulate, modulate

SPECTRUM_SPS = 8  # samples/symbol for waveform artifacts (plot view only)


def _byte_hamming(a: bytes, b: bytes) -> int:
    """Bit differences between two equal-length byte strings."""
    if len(a) != len(b):
        raise ValueError(f"length mismatch: {len(a)} vs {len(b)}")
    if not a:
        return 0
    x = np.frombuffer(a, dtype=np.uint8) ^ np.frombuffer(b, dtype=np.uint8)
    return int(np.unpackbits(x).sum())


class LinkSimulator:
    """Executes the transmit/receive chain of one :class:`LinkConfig`.

    The simulator never swallows unexpected exceptions: only *link*
    outcomes (RS failure, frame rejection, payload mismatch) are
    recorded as failures. A bug in the chain surfaces as a crash, not
    as a suspiciously high error rate.
    """

    def __init__(self, config: LinkConfig):
        self.cfg = config
        self.rs = (ReedSolomon255_223()
                   if config.mode == "rs255_223" else None)

    # ---- single-frame chain ------------------------------------------
    def transmit(self, payload: bytes, seq: int) -> dict:
        cfg = self.cfg
        frame = build_frame(payload, seq)
        coded = self.rs.encode(frame) if self.rs else frame
        bits = bytes_to_bits(coded)
        bits, n_pad = pad_to_multiple(bits, bits_per_symbol(cfg.modulation))
        symbols = modulate(bits, cfg.modulation)
        return {"payload": payload, "frame": frame, "coded": coded,
                "bits": bits, "n_pad": n_pad, "symbols": symbols}

    def receive(self, rx_symbols, tx: dict) -> dict:
        """Demodulate and recover one frame; link defects become reasons."""
        cfg = self.cfg
        rx_bits = demodulate(rx_symbols, cfg.modulation)
        raw_errors = int(np.count_nonzero(rx_bits != tx["bits"]))
        coded_rx = bits_to_bytes(rx_bits[: cfg.coded_bits()])
        out = {"raw_errors": raw_errors, "frame_rx": None, "reason": None,
               "frame_errors": None, "rs_blocks": 0, "rs_failed_blocks": 0,
               "rs_corrected": 0}
        if self.rs:
            res = self.rs.decode(coded_rx, exact_len=cfg.frame_bytes)
            out["rs_blocks"] = res.blocks
            out["rs_failed_blocks"] = res.failed_blocks
            out["rs_corrected"] = res.corrected_symbols
            if res.failed:
                out["reason"] = ("rs_structural"
                                 if res.reason in ("structural", "short_output")
                                 else "rs_uncorrectable")
                return out
            frame_rx = res.data
        else:
            frame_rx = coded_rx
        out["frame_rx"] = frame_rx
        out["frame_errors"] = _byte_hamming(frame_rx, tx["frame"])
        try:
            parsed = parse_frame(frame_rx)
        except FrameError:
            out["reason"] = "frame_parse"
            return out
        if parsed.payload != tx["payload"]:
            out["reason"] = "payload_mismatch"
            return out
        return out

    # ---- sweep point --------------------------------------------------
    def run_point(self, ebn0_db: Optional[float],
                  n_frames: Optional[int] = None,
                  rng: Optional[np.random.Generator] = None,
                  collect_artifacts: bool = False):
        """Run ``n_frames`` at one Eb/N0; returns ``(metrics, artifacts)``.

        ``ebn0_db=None`` disables the noise (noiseless reference).
        ``rng`` defaults to the config seed; pass a seeded generator for
        reproducible point-by-point sweeps (see ``comms.experiments``).
        """
        cfg = self.cfg
        n = n_frames or cfg.frames
        if rng is None:
            rng = np.random.default_rng(cfg.seed)
        metrics = LinkMetrics(frame_bytes=cfg.frame_bytes)
        artifacts = {"ebn0_db": ebn0_db}
        for seq in range(n):
            payload = rng.integers(0, 256, size=cfg.payload_bytes,
                                   dtype=np.uint8).tobytes()
            t0 = time.perf_counter()
            tx = self.transmit(payload, seq)
            t_tx = time.perf_counter() - t0

            if ebn0_db is None:
                rx_symbols = tx["symbols"].copy()
            else:
                esn0_db = ebn0_to_esn0_db(ebn0_db, cfg.info_bits,
                                          int(tx["symbols"].size))
                rx_symbols = awgn(tx["symbols"], esn0_db, rng)

            t1 = time.perf_counter()
            rx = self.receive(rx_symbols, tx)
            t_rx = time.perf_counter() - t1

            metrics.frame_sent(cfg.info_bits)
            metrics.symbols(int(tx["symbols"].size))
            metrics.raw_bits(int(tx["bits"].size), rx["raw_errors"])
            metrics.latency("tx", t_tx)
            metrics.latency("rx", t_rx)
            if rx["rs_blocks"]:
                metrics.rs(rx["rs_blocks"], rx["rs_failed_blocks"],
                           rx["rs_corrected"])
            if rx["reason"] is None:
                metrics.frame_delivered(cfg.info_bits)
                if rx["frame_errors"]:
                    # CRC + exact payload match passed, yet the framing
                    # bytes differ - a CRC-32 collision. Recorded as the
                    # real measured value; delivery was already revoked
                    # would it exceed zero, here it cannot.
                    metrics.frame_bits(rx["frame_errors"])
            elif rx["reason"] in ("rs_uncorrectable", "rs_structural"):
                metrics.frame_failed(rx["reason"], cfg.info_bits)
                metrics.frame_bits(0, n_unmeasurable_bits=cfg.frame_bytes * 8)
            else:
                metrics.frame_failed(rx["reason"], cfg.info_bits)
                metrics.frame_bits(int(rx["frame_errors"] or 0))

            if collect_artifacts and seq == 0:
                artifacts["tx_bits"] = tx["bits"].copy()
                artifacts["rx_bits"] = demodulate(rx_symbols,
                                                  cfg.modulation).copy()
                artifacts["tx_symbols"] = tx["symbols"].copy()
                artifacts["rx_symbols"] = np.asarray(rx_symbols).copy()
                artifacts["tx_wave"] = np.repeat(tx["symbols"], SPECTRUM_SPS)
                artifacts["rx_wave"] = np.repeat(rx_symbols, SPECTRUM_SPS)
        return metrics, artifacts
