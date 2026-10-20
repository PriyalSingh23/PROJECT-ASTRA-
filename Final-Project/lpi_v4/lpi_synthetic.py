#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lpi_synthetic.py -- band-limited modulated "hard negatives" for the warden.
===========================================================================

A warden that has only ever seen AWGN learns "is this noise?", which is the
easy version of the question.  A field warden asks "is this noise *or* a real
signal?", so the detector needs real signals to train against -- the reference
paper's own ablation calls the AWGN-only version a "sim-only detector", and
that is exactly what the shipped v4 checkpoint was gated against.

The real dataset for that job is RadioML 2018.01A.  DeepSig now gates it behind
an email signup form, so this module synthesises the part that matters: a bank
of *band-limited* modulated frames -- RRC-shaped PSK/QAM, constant-envelope
GFSK and CPFSK, PN-spread DSSS, improper PAM4 -- at random SNR, CFO and
timing, in the exact ``(N, 2, T)`` float32 layout ``lpi_datasets.load_hdf5``
produces, so anything that can eat a GOLD/RML capture can eat this.

The pulse shaping is the point.  The older RadioML-style generator in
``lpi_research/datasets/synthetic_generator.py`` writes *unfiltered* symbol
streams, whose spectral images make them trivially separable from anything a
real receiver's DAC would emit -- a warden trained on those learns "does this
have images?", learns it in an epoch, and then tells you nothing about
stealth.  Every frame here is shaped to a fractional bandwidth like a radio's
DAC would emit, so the warden has to learn *modulation structure* instead.

    python lpi_synthetic.py --n 20000 --out data/hardnegatives.hdf5
    python lpi_train.py --synth-real 20000

That HDF5 is also loadable by ``lpi_datasets.load_hdf5`` (``--radioml --data
data/hardnegatives.hdf5``), because the layouts are the same by construction.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Optional, Tuple

import numpy as np

#: The nine shapes a tactical 2.4 GHz link can realistically be carrying.
#: ``awgn`` is *not* in the default set: it is already the warden's real class,
#: and adding it to the "signal" side would teach the detector to classify
#: noise as signal -- the exact opposite of what we want.
MODS: Tuple[str, ...] = ("bpsk", "qpsk", "8psk", "pam4", "16qam", "64qam",
                         "gfsk", "cpm", "dsss")


def rrc_taps(sps: int = 8, beta: float = 0.35, span: int = 8) -> np.ndarray:
    """Root-raised-cosine taps, unit energy, with the two removable
    singularities (t=0 and t=+-1/(4 beta)) handled analytically.

    beta=0.35 is the 3GPP/RRC default and what a field modem's DAC actually
    emits; sps=8 puts the occupied bandwidth at ~fs/8 with the RRC rolloff,
    which is a real signal's spectral shape rather than a full-Nyquist brick.
    """
    n = np.arange(-span * sps, span * sps + 1, dtype=np.float64)
    t = n / float(sps)
    h = np.zeros_like(t)
    with np.errstate(invalid="ignore", divide="ignore"):
        num = np.sin(np.pi * t * (1.0 - beta)) + 4.0 * beta * t * np.cos(np.pi * t * (1.0 + beta))
        den = np.pi * t * (1.0 - (4.0 * beta * t) ** 2)
        h = num / den
    h[np.abs(t) < 1e-12] = 1.0 + beta * (4.0 / np.pi - 1.0)
    i = np.abs(np.abs(t) - 1.0 / (4.0 * beta)) < 1e-9
    h[i] = (beta / np.sqrt(2.0)) * (
        (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * beta))
        + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * beta)))
    return h / np.sqrt(np.sum(h ** 2))


def _gauss_kernel(bt: float = 0.5, span: int = 4) -> np.ndarray:
    """Gaussian frequency pulse for GFSK (BT=0.5, the Bluetooth value)."""
    n = np.arange(-span, span + 1, dtype=np.float64)
    s = np.sqrt(np.log(2.0)) / (2.0 * np.pi * bt)
    k = np.exp(-0.5 * (n / s) ** 2)
    return k / np.sum(k)


_QPSK = np.array([1 + 1j, -1 + 1j, -1 - 1j, 1 - 1j]) / np.sqrt(2.0)
_8PSK = np.exp(1j * 2.0 * np.pi * np.arange(8) / 8.0)
_16QAM = np.array([q + 1j * r for q in (-3, -1, 1, 3) for r in (-3, -1, 1, 3)]) / np.sqrt(10.0)
_64QAM = np.array([q + 1j * r for q in range(-7, 8, 2) for r in range(-7, 8, 2)]) / np.sqrt(42.0)
_PAM4 = np.array([-3.0, -1.0, 1.0, 3.0]) / np.sqrt(10.0)


def _symbols(mod: str, n_sym: int, rng: np.random.Generator) -> np.ndarray:
    """Unit-mean-power complex symbols for one modulation (PAM4 is I-only)."""
    if mod == "bpsk":
        return rng.choice(np.array([-1.0, 1.0]), n_sym).astype(np.complex128)
    if mod == "qpsk":
        return _QPSK[rng.integers(0, 4, n_sym)]
    if mod == "8psk":
        return _8PSK[rng.integers(0, 8, n_sym)]
    if mod == "pam4":
        return _PAM4[rng.integers(0, 4, n_sym)].astype(np.complex128)  # improper: Q = 0
    if mod == "16qam":
        return _16QAM[rng.integers(0, 16, n_sym)]
    if mod == "64qam":
        return _64QAM[rng.integers(0, 64, n_sym)]
    if mod == "dsss":
        # handled by synth_frame: spreading happens at the *chip* level
        raise ValueError("dsss is expanded by synth_frame before symbol mapping")
    raise ValueError(f"unknown modulation {mod!r}")


def synth_frame(mod: str, n: int = 512, snr_db: float = 10.0, rng=None,
                sps: int = 8, fs: float = 1.0) -> np.ndarray:
    """One (2, n) float32 frame of ``mod`` at ``snr_db``, with CFO and phase.

    Steps: symbols -> RRC (or Gaussian for GFSK; DSSS spreads at the chip level
    first) -> random frame start (so the window never lands on a symbol
    boundary) -> unit-power -> CFO/phase -> AWGN -> unit-power again.  That last
    normalisation matches what ``lpi_datasets._norm`` does to a real RadioML
    capture, so a synthetic bank and a real one are scaled the same way before
    the warden sees them.
    """
    rng = np.random.default_rng() if rng is None else rng
    n_sym = int(np.ceil(n / sps)) + 16                      # guard for filter memory

    if mod in ("gfsk", "cpm"):
        bits = rng.choice(np.array([-1.0, 1.0]), n_sym)
        if mod == "gfsk":
            pulse = np.convolve(bits, _gauss_kernel(), mode="same")
        else:
            pulse = bits                                    # CPFSK: rectangular pulse
        # Hold each smoothed symbol over sps samples: symbol rate fs/sps puts the
        # spectrum in a radio-like band (and makes the frame long enough that the
        # zero-pad fallback below never fires -- at 1 sample/symbol the frame
        # came out 80 samples long, got 432 zeros, and read as 8 dB PAPR).
        hold = np.repeat(pulse, sps)
        sig = np.exp(1j * np.cumsum(hold) * (np.pi / 2.0) / sps)   # h = 0.5
    else:
        h = rrc_taps(sps=sps)
        if mod == "dsss":
            # spread at the chip level: sf chips per data symbol, then the chip
            # stream -- not the symbol stream -- is what the DAC pulse-shapes.
            # (Mapping 16x chips into n_sym slots is a broadcast error, and
            # spreading after windowing would not spread anything.)
            sf = 16
            bits = rng.choice(np.array([-1.0, 1.0]), n_sym).astype(np.complex128)
            pn = rng.choice(np.array([-1.0, 1.0]), sf).astype(np.complex128)
            chips = np.kron(bits, pn) / np.sqrt(float(sf))
            tx = np.zeros(len(chips) * sps, dtype=np.complex128)
            tx[::sps] = chips
        else:
            tx = np.zeros(n_sym * sps, dtype=np.complex128)
            tx[::sps] = _symbols(mod, n_sym, rng)
        sig = np.convolve(tx, h)[sps * 4:]                  # drop filter warm-up

    if len(sig) < n:                                        # very short frames
        sig = np.pad(sig, (0, n - len(sig)))
    start = int(rng.integers(0, len(sig) - n + 1))
    sig = sig[start:start + n]                              # random fractional timing

    p = np.mean(np.abs(sig) ** 2)
    if p > 0:
        sig = sig / np.sqrt(p)                              # unit power, pre-noise

    t = np.arange(n, dtype=np.float64) / fs
    cfo = rng.uniform(-fs / 30.0, fs / 30.0)                # +-3.3% of fs
    sig = sig * np.exp(1j * (2.0 * np.pi * cfo * t + rng.uniform(0.0, 2.0 * np.pi)))

    if snr_db < 60.0:                                       # 60 dB = "no noise"
        s2 = 10.0 ** (-snr_db / 10.0)                       # per real dim
        sig = sig + np.sqrt(s2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))

    p = np.mean(np.abs(sig) ** 2)
    if p > 0:
        sig = sig / np.sqrt(p)                              # unit power, post-noise
    return np.stack([sig.real, sig.imag]).astype(np.float32)


def synthesize_bank(n: int, target_len: int = 512, seed: int = 0,
                    snr_range: Tuple[float, float] = (-20.0, 18.0),
                    mods: Optional[Iterable[str]] = None,
                    sps: int = 8) -> np.ndarray:
    """``n`` frames of (2, target_len) float32, balanced across ``mods``, shuffled.

    Balanced (``i % len(mods)``) then shuffled, so a batch never sees one
    modulation in sorted order and a per-batch normalization can't leak class
    identity.  Deterministic under ``seed``.
    """
    rng = np.random.default_rng(seed)
    mods = tuple(mods) if mods else MODS
    out = np.empty((n, 2, target_len), dtype=np.float32)
    for i in range(n):
        out[i] = synth_frame(mods[i % len(mods)], target_len,
                             snr_db=float(rng.uniform(*snr_range)),
                             rng=rng, sps=sps)
    return out[rng.permutation(n)]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Write a band-limited modulated hard-negative bank for the "
                    "LPI warden (RadioML 2018.01A is email-gated; this is not).")
    ap.add_argument("--n", type=int, default=20000,
                    help="frames to generate (default 20000)")
    ap.add_argument("--len", dest="length", type=int, default=512,
                    help="samples per frame (default 512)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--snr-lo", type=float, default=-20.0)
    ap.add_argument("--snr-hi", type=float, default=18.0)
    ap.add_argument("--out", default="data/hardnegatives.hdf5",
                    help="HDF5 path; the dataset key is 'X', GOLD-style")
    args = ap.parse_args()

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    x = synthesize_bank(args.n, args.length, seed=args.seed,
                        snr_range=(args.snr_lo, args.snr_hi))
    print(f"[synth] {x.shape} frames, mods={','.join(MODS)}, "
          f"snr {args.snr_lo:g}..{args.snr_hi:g} dB")

    try:
        import h5py
    except ImportError:
        npy = os.path.splitext(args.out)[0] + ".npy"
        np.save(npy, x)
        print(f"[synth] h5py missing; wrote {npy} instead ({os.path.getsize(npy)/1e6:.1f} MB)")
        return 0

    with h5py.File(args.out, "w") as f:
        f.create_dataset("X", data=x, compression="gzip", compression_opts=4)
    print(f"[synth] wrote {args.out} ({os.path.getsize(args.out)/1e6:.1f} MB) -- "
          f"load with: python lpi_train.py --radioml --data {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
