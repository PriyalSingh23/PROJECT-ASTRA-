"""ASTRA communications platform core (Gate 1 baseline).

Deterministic, hardware-free link simulation with measurable outputs:

    bits -> frame (CRC-32) -> [RS(255,223)] -> modulate -> AWGN ->
    demodulate -> [RS decode] -> parse -> metrics

Conventions and honesty rules (see also comms/config.py docstrings):

* ``Eb/N0`` is energy per *information payload* bit; every overhead bit
  (header, CRC, FEC parity, symbol padding) is accounted for when
  converting to ``Es/N0`` per experiment point.
* Metrics never silently drop failed frames: PER/PDR denominators always
  include every transmitted frame, and the effective payload BER counts
  undecodable frames as fully erroneous (documented upper-bound style).
* Every saved number originates from a seeded run; plots are rendered
  only from saved experiment records.

Submodules are imported explicitly (``from comms import framing`` etc.)
so that importing this package stays dependency-light.
"""

__version__ = "0.1.0"
