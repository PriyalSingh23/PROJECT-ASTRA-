"""Link experiment configuration and Eb/N0 <-> Es/N0 accounting.

Definitions used consistently across the platform
--------------------------------------------------
``Eb/N0``
    Energy per **information (payload) bit** relative to the noise PSD
    ``N0``. Every bit that consumes airtime is overhead and is therefore
    accounted for: frame header, CRC-32, FEC parity and symbol padding.
``Es/N0``
    Energy per transmitted **symbol** relative to ``N0``.
``SNR``
    At symbol level with unit-energy symbols, ``SNR == Es/N0``. On an
    oversampled waveform the same quantity holds only after dividing the
    measured signal/noise powers over ``sps`` samples per symbol; Gate 1
    simulates at symbol level and derives waveform views from the same
    unit-energy symbols, so the two never disagree.

Conversion (linear): ``Es/N0 = (Eb/N0) * n_info_bits / n_symbols``
In dB::

    esn0_db = ebn0_db + 10 * log10(n_info_bits / n_symbols)

``n_info_bits`` counts payload bits only; ``n_symbols`` counts every
symbol actually transmitted (header + payload + CRC + FEC parity +
padding). For an uncoded link with no framing overhead the ratio is 1
and the two quantities coincide; with RS(255,223) + a 12-byte frame
overhead on a 64-byte payload the ratio is well below 1, which is
exactly the "coding-rate + framing overhead" accounting the platform is
required to make explicit rather than hand-wave.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MODULATIONS = ("bpsk", "qpsk")
MODES = ("uncoded", "rs255_223")


def bits_per_symbol(modulation: str) -> int:
    """Coded bits carried by one symbol of ``modulation``."""
    if modulation == "bpsk":
        return 1
    if modulation == "qpsk":
        return 2
    raise ValueError(f"unknown modulation {modulation!r} (expected one of {MODULATIONS})")


def ebn0_to_esn0_db(ebn0_db: float, n_info_bits: int, n_symbols: int) -> float:
    """Convert Eb/N0 (per payload bit) to Es/N0 (per transmitted symbol).

    Both counts must be positive integers; the result accounts for code
    rate, framing overhead and padding in one exact ratio (no
    hand-estimated dB fudge factors).
    """
    if n_info_bits <= 0 or n_symbols <= 0:
        raise ValueError("n_info_bits and n_symbols must be positive")
    if not math.isfinite(ebn0_db):
        raise ValueError(f"ebn0_db must be finite, got {ebn0_db!r}")
    return ebn0_db + 10.0 * math.log10(n_info_bits / n_symbols)


def esn0_to_noise_variance(esn0_db: float) -> float:
    """Complex noise variance ``N0 = E[|n|^2]`` for unit-energy symbols.

    Real and imaginary noise components each carry ``N0 / 2``.
    """
    if not math.isfinite(esn0_db):
        raise ValueError(f"esn0_db must be finite, got {esn0_db!r}")
    return 10.0 ** (-esn0_db / 10.0)


@dataclass(frozen=True)
class LinkConfig:
    """Full description of one reproducible link experiment.

    Two :func:`config_from_preset` presets ship with the platform:

    ``debug``
        25 frames at 3 SNR points - runs in a couple of seconds, used by
        tests and for smoke checks.
    ``montecarlo``
        1000 frames at 11 SNR points (0..10 dB, 1 dB steps) - the longer
        statistical run used for the recorded baseline curves.
    """

    modulation: str = "bpsk"
    mode: str = "uncoded"                    # uncoded | rs255_223
    payload_bytes: int = 64
    frames: int = 25
    ebn0_db: tuple = (0.0, 4.0, 8.0)
    seed: int = 20261020
    name: str = "debug"
    description: str = "ASTRA Gate 1 baseline link experiment"

    def __post_init__(self):
        object.__setattr__(self, "ebn0_db", tuple(float(x) for x in self.ebn0_db))
        if self.modulation not in MODULATIONS:
            raise ValueError(f"modulation must be one of {MODULATIONS}, got {self.modulation!r}")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if not isinstance(self.payload_bytes, int) or not (0 < self.payload_bytes <= 65535):
            raise ValueError("payload_bytes must be an int in 1..65535")
        if not isinstance(self.frames, int) or self.frames <= 0:
            raise ValueError("frames must be a positive int")
        if not self.ebn0_db:
            raise ValueError("ebn0_db must contain at least one point")
        for x in self.ebn0_db:
            if not math.isfinite(x):
                raise ValueError(f"non-finite Eb/N0 point: {x!r}")

    # ---- derived frame geometry -------------------------------------
    @property
    def frame_header_bytes(self) -> int:
        """magic(2) + version(1) + type(1) + seq(2) + payload_len(2)."""
        return 8

    @property
    def crc_bytes(self) -> int:
        return 4

    @property
    def frame_bytes(self) -> int:
        """Exact serialized frame size (header + payload + CRC)."""
        return self.frame_header_bytes + self.payload_bytes + self.crc_bytes

    @property
    def info_bits(self) -> int:
        """Information (payload) bits - the Eb in Eb/N0 counts these."""
        return 8 * self.payload_bytes

    def coded_bytes(self) -> int:
        """Bytes actually modulated for one frame in the configured mode."""
        if self.mode == "uncoded":
            return self.frame_bytes
        # RS(255,223): frame zero-padded to a 223-byte multiple, then
        # emitted as 255-byte codewords (see comms.fec.rs).
        n_blocks = -(-self.frame_bytes // 223)
        return n_blocks * 255

    def coded_bits(self) -> int:
        return 8 * self.coded_bytes()


PRESETS: dict = {
    "debug": dict(frames=25, ebn0_db=(0.0, 4.0, 8.0), name="debug",
                  description="fast debug sweep (25 frames x 3 points)"),
    "montecarlo": dict(frames=1000, ebn0_db=tuple(float(x) for x in range(11)),
                       name="montecarlo",
                       description="Monte-Carlo baseline (1000 frames x 0..10 dB)"),
}


def config_from_preset(preset: str, **overrides) -> LinkConfig:
    """Build a :class:`LinkConfig` from a named preset, then override fields."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r} (expected one of {sorted(PRESETS)})")
    kwargs = dict(PRESETS[preset])
    kwargs.update(overrides)
    return LinkConfig(**kwargs)
