"""Bit packing utilities.

Convention: **MSB-first** within every byte.
``bytes_to_bits(b"\\x80") -> [1, 0, 0, 0, 0, 0, 0, 0]``.

All values are ``numpy.uint8`` arrays containing only 0/1 so the same
arrays can be fed to modulators, compared for BER, or stored in plots.
"""

from __future__ import annotations

import numpy as np


def bytes_to_bits(data) -> np.ndarray:
    """Pack bytes into an MSB-first uint8 0/1 array (length 8*len(data))."""
    arr = np.frombuffer(bytes(data), dtype=np.uint8)
    if arr.size == 0:
        return np.zeros(0, dtype=np.uint8)
    shifts = np.arange(7, -1, -1, dtype=np.int64)          # MSB first
    return ((arr[:, None] >> shifts[None, :]) & 1).reshape(-1).astype(np.uint8)


def bits_to_bytes(bits) -> bytes:
    """Unpack an MSB-first 0/1 array back into bytes.

    Raises ValueError for non-binary values or a length that is not a
    multiple of 8 (a malformed frame must fail loudly, never be padded
    silently).
    """
    b = np.asarray(bits)
    if b.ndim != 1:
        b = b.reshape(-1)
    if b.size % 8 != 0:
        raise ValueError(f"bit count {b.size} is not a multiple of 8")
    if b.size and not np.all((b == 0) | (b == 1)):
        raise ValueError("bit array must contain only 0/1 values")
    if b.size == 0:
        return b""
    shifts = np.arange(7, -1, -1, dtype=np.int64)
    packed = (b.astype(np.int64).reshape(-1, 8) << shifts[None, :]).sum(axis=1)
    return packed.astype(np.uint8).tobytes()


def pad_to_multiple(bits: np.ndarray, multiple: int) -> tuple[np.ndarray, int]:
    """Zero-pad a bit array to the next multiple of ``multiple``.

    Returns ``(padded_bits, n_pad)``. The receiver strips the padding by
    keeping the first ``len(bits) - n_pad`` bits; because the transmit
    side derives ``n_pad`` from the frame length (known from the link
    profile), padding never has to be carried in-band.
    """
    if multiple <= 0:
        raise ValueError("multiple must be positive")
    b = np.asarray(bits, dtype=np.uint8).reshape(-1)
    n_pad = (-b.size) % multiple
    if n_pad:
        b = np.concatenate([b, np.zeros(n_pad, dtype=np.uint8)])
    return b, n_pad
