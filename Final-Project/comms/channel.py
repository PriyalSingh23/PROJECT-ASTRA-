"""AWGN channel with explicit Es/N0 noise scaling.

Complex baseband model for unit-energy symbols ``s``::

    r = s + n,   n ~ CN(0, N0),   N0 = E[|n|^2] = 10^(-EsN0_dB/10)
    Re{n}, Im{n} ~ N(0, N0/2) each

``n_info_bits / n_symbols`` conversion from the experiment's Eb/N0 target
happens in :func:`comms.config.ebn0_to_esn0_db` - this module only ever
consumes Es/N0, so channel noise can never accidentally be scaled with an
uncorrected dB figure.
"""

from __future__ import annotations

import math

import numpy as np

from .config import esn0_to_noise_variance


def awgn(symbols, esn0_db: float, rng: np.random.Generator) -> np.ndarray:
    """Add complex AWGN to ``symbols`` at the given Es/N0 (dB).

    ``esn0_db = math.inf`` returns the symbols unchanged (noiseless
    reference run used by the reproducibility/regression tests).
    """
    s = np.asarray(symbols, dtype=np.complex128).reshape(-1)
    if esn0_db == math.inf:
        return s.copy()
    n0 = esn0_to_noise_variance(esn0_db)
    sigma = math.sqrt(n0 / 2.0)
    noise = sigma * (rng.standard_normal(s.size) + 1j * rng.standard_normal(s.size))
    return s + noise


def measured_noise_variance(noise) -> float:
    """E[|n|^2] of a sample of complex noise (verification helper)."""
    n = np.asarray(noise, dtype=np.complex128).reshape(-1)
    if n.size == 0:
        raise ValueError("empty noise sample")
    return float(np.mean(np.abs(n) ** 2))
