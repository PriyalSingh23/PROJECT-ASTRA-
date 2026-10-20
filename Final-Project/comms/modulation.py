"""Gray-mapped modulators/demodulators (unit average symbol energy).

Gate 1 ships BPSK and QPSK with **hard** decisions. Soft (LLR) demodulation
arrives with the LDPC layer in Gate 2; the module boundary is already the
right place for it.

Constellations (unit energy):

* BPSK: bit 0 -> +1, bit 1 -> -1.
* QPSK: bit pair (b0, b1) -> ((1-2*b0) + j*(1-2*b1)) / sqrt(2)
  (b0 on the in-phase rail, b1 on the quadrature rail; Gray-coded).

Average symbol energy is exactly 1 for both, which is what lets
``comms.channel`` convert Es/N0 straight into noise variance.
"""

from __future__ import annotations

import numpy as np

from .config import bits_per_symbol

_MODULATIONS = ("bpsk", "qpsk")


def _check_bits(bits) -> np.ndarray:
    b = np.asarray(bits)
    if b.ndim != 1:
        b = b.reshape(-1)
    if b.size and not np.all((b == 0) | (b == 1)):
        raise ValueError("modulator input must be a 0/1 bit array")
    return b.astype(np.uint8, copy=False)


def modulate(bits, modulation: str) -> np.ndarray:
    """Map a 0/1 bit array to unit-energy complex symbols.

    Raises ValueError if the bit count is not a multiple of
    ``bits_per_symbol(modulation)`` - a mis-sized frame must fail loudly
    instead of being silently truncated.
    """
    b = _check_bits(bits)
    k = bits_per_symbol(modulation)
    if b.size % k != 0:
        raise ValueError(f"{b.size} bits is not a multiple of {k} "
                         f"({modulation} needs {k} bit(s) per symbol)")
    if b.size == 0:
        return np.zeros(0, dtype=np.complex128)
    if modulation == "bpsk":
        return (1.0 - 2.0 * b).astype(np.complex128)
    # qpsk
    i = 1.0 - 2.0 * b[0::2]
    q = 1.0 - 2.0 * b[1::2]
    return (i + 1j * q) / np.sqrt(2.0)


def demodulate(symbols, modulation: str) -> np.ndarray:
    """Hard-decision demodulation (bit 0 for the positive half-plane).

    Ties (decision variable exactly 0) resolve deterministically to 0 so
    seeded runs stay bit-for-bit reproducible.
    """
    s = np.asarray(symbols, dtype=np.complex128).reshape(-1)
    if s.size == 0:
        return np.zeros(0, dtype=np.uint8)
    if modulation == "bpsk":
        return (s.real < 0).astype(np.uint8)
    if modulation == "qpsk":
        out = np.empty(2 * s.size, dtype=np.uint8)
        out[0::2] = s.real < 0
        out[1::2] = s.imag < 0
        return out
    raise ValueError(f"unknown modulation {modulation!r} (expected one of {_MODULATIONS})")
