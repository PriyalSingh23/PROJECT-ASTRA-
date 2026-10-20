"""FEC layer for the ASTRA platform.

Gate 1 ships RS(255,223) (``comms.fec.rs``). Gate 2 adds LDPC and the
interleavers, and the concatenated coding chain lives here.
"""

from .rs import (  # noqa: F401
    NCODE,
    NDATA,
    NERR,
    NPARITY,
    RSResult,
    ReedSolomon255_223,
    inject_symbol_errors,
)
