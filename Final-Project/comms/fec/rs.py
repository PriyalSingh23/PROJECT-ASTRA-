"""Reed-Solomon RS(255,223) over GF(2^8) - the platform's Gate 1 FEC.

Parameters (identical to the legacy ``app.py`` ``CryptoEngine``, which is
benchmarked against this implementation rather than modified)::

    reedsolo.RSCodec(nsym=32, nsize=255)   fcr=0, prim=0x11d, generator=2
    NDATA   = 223 information bytes per codeword
    NPARITY = 32 parity bytes
    NCODE   = 255 coded bytes per codeword
    NERR    = 16 symbol errors correctable per codeword (t = nsym/2)
    rate    = 223/255 = 0.8745  (+14.35% parity overhead)

Padding scheme
--------------
Input is zero-padded to a multiple of 223 bytes, then emitted as
255-byte codewords. The pad length is **not** carried in-band: framing
knows the exact frame size from the link profile (the frame's own
payload-length field fixes the total), so the receiver trims trailing
bytes after RS decode. Empty input round-trips as empty output (no
codeword is produced for zero bytes).

Detection honesty
-----------------
Uncorrectable blocks (more than 16 symbol errors, or error patterns the
decoder cannot resolve) return ``failed=True`` with **no data** - never
substituted zeros. The decoder does not claim to detect *every* pattern
above t; the CRC-32 in the framing layer is the second, independent
check that catches any residual mis-correction (RS can miscorrect in
rare pathological cases beyond t; CRC then rejects the frame).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from reedsolo import RSCodec, ReedSolomonError

NDATA = 223
NPARITY = 32
NCODE = 255
NERR = NPARITY // 2          # 16 correctable symbol errors per codeword
CODE_RATE = NDATA / NCODE    # 0.8745...


@dataclass(frozen=True)
class RSResult:
    """Outcome of an RS decode.

    ``data`` is None exactly when ``failed`` is True.
    ``reason`` is None on success, else one of
    ``"structural"`` (input length not a multiple of 255),
    ``"uncorrectable"`` (>= t+1 symbol errors / decoder failure),
    ``"short_output"`` (decoded bytes fewer than ``exact_len``).

    ``blocks`` counts the codewords in the input; ``failed_blocks``
    counts the codewords the decoder could not correct (0 on success).
    ``corrected_symbols`` sums symbol corrections over codewords that
    decoded successfully - a codeword that failed contributes none.
    """

    data: Optional[bytes]
    failed: bool
    corrected_symbols: int
    blocks: int
    reason: Optional[str] = None
    failed_blocks: int = 0


class ReedSolomon255_223:
    """RS(255,223) codec with the platform's documented padding scheme."""

    ndata = NDATA
    nparity = NPARITY
    ncode = NCODE
    nerr = NERR

    def __init__(self):
        self.codec = RSCodec(nsym=NPARITY, nsize=NCODE)

    # ---- encode ------------------------------------------------------
    @staticmethod
    def pad_length(n: int) -> int:
        return (-n) % NDATA

    def encode(self, data) -> bytes:
        """Zero-pad ``data`` to a 223-byte multiple and RS-encode blocks.

        Returns the concatenation of 255-byte codewords (length is
        ``ceil(len(data)/223)*255``, or 0 for empty input).
        """
        data = bytes(data)
        pad = self.pad_length(len(data))
        padded = data + b"\x00" * pad
        if not padded:
            return b""
        out = bytearray()
        for i in range(0, len(padded), NDATA):
            out += self.codec.encode(padded[i:i + NDATA])
        return bytes(out)

    # ---- decode ------------------------------------------------------
    def decode(self, data, exact_len: Optional[int] = None) -> RSResult:
        """Decode 255-byte codewords; never fabricates payload bytes.

        ``exact_len`` (optional) trims trailing RS padding and fails the
        decode if fewer bytes than expected came back.
        """
        data = bytes(data)
        if len(data) % NCODE != 0:
            return RSResult(None, True, 0, 0, "structural")
        if exact_len is not None and exact_len < 0:
            raise ValueError("exact_len must be non-negative")
        if len(data) == 0:
            if exact_len in (None, 0):
                return RSResult(b"", False, 0, 0, None)
            return RSResult(None, True, 0, 0, "short_output")

        blocks = len(data) // NCODE
        out = bytearray()
        corrected = 0
        failed_blocks = 0
        for i in range(0, len(data), NCODE):
            try:
                msg, _, errata = self.codec.decode(data[i:i + NCODE])
            except ReedSolomonError:
                # >16 symbol errors or an unresolvable pattern. Every
                # codeword is still attempted so ``failed_blocks`` stays a
                # true per-codeword count, but no partial payload is kept.
                failed_blocks += 1
                continue
            out += bytes(msg)
            if errata:
                corrected += len(errata)
        if failed_blocks:
            return RSResult(None, True, corrected, blocks, "uncorrectable",
                            failed_blocks)
        result = bytes(out)
        if exact_len is not None:
            if len(result) < exact_len:
                return RSResult(None, True, corrected, blocks, "short_output")
            result = result[:exact_len]
        return RSResult(result, False, corrected, blocks, None)


def inject_symbol_errors(data, n_errors: int, rng, block: int = 0) -> bytes:
    """XOR ``n_errors`` distinct symbols of codeword ``block`` (test helper).

    Positions are drawn from ``rng`` (a :class:`numpy.random.Generator`)
    without replacement within the block, so seeded injection is
    reproducible and no symbol is hit twice.
    """
    buf = bytearray(bytes(data))
    if len(buf) % NCODE != 0:
        raise ValueError("input length must be a multiple of 255")
    if len(buf) == 0:
        raise ValueError("empty input")
    if not (0 <= block < len(buf) // NCODE):
        raise ValueError(f"block index {block} out of range")
    if not (0 <= n_errors <= NCODE):
        raise ValueError(f"n_errors must be 0..{NCODE}, got {n_errors}")
    base = block * NCODE
    if n_errors:
        pos = np.atleast_1d(rng.choice(NCODE, size=n_errors, replace=False))
        for p in pos:
            buf[base + int(p)] ^= 0xFF
    return bytes(buf)
