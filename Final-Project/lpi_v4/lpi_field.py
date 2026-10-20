#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lpi_field.py -- the channel a field deployment actually has.
===========================================================

``apply_channel`` (lpi_core) models a *bench*: IQ imbalance, CFO, LO phase,
phase noise, DC offset, AWGN.  It is the channel the v4 checkpoint was trained
and gated on, and it is still what the trainer uses unless you ask for this one.

What a real 2.4 GHz field link adds, and why each one is here:

  1. **multipath.**  A radio on a hill, in a vehicle, or near a building line
     does not see one path.  The delayed copies destroy the "every sample is an
     independent sum of keyed chips" property that the KS/kurtosis pass leans
     on, and -- because the spreading code spans the whole frame with no cyclic
     prefix -- they put inter-chip interference straight into the correlator.
     This is the single biggest reason a link that scores BER 0 on the bench
     fails on the first field trial, so it is the reason this module exists.

  2. **fractional-sample timing.**  ``sync_and_correct`` searches *integer*
     sample offsets (and +-``timing_refine`` around the preamble lock), so
     everything between two sample points is uncorrected by construction.  A
     real receiver always lands off-grid -- by the timing estimator's own
     noise, by SFO, and by the multipath itself.

  3. **sampling clock offset (SFO).**  Two free-running radios' ADCs disagree
     by a few ppm.  Within one 2.34 ms frame the walk is a fraction of a
     sample, but it accumulates across a burst -- which is exactly why the
     field receiver re-locks per frame -- and the residue that reaches the
     decoder is modelled here.

  4. **Doppler.**  At 2.484 GHz a walking person is ~11 Hz, a vehicle at 60
     km/h is ~138 Hz.  Per path it is a phase ramp; differential across paths
     it is time-varying selective fading.

  5. **the ADC.**  A B210's converter has 12 bits and the AGC parks the signal
     ``clip_headroom_db`` below full scale, so the peaks of a near-Gaussian
     waveform do get clipped.  At 12 bits the quantisation floor is ~72 dBc and
     invisible next to a -2..12 dB SNR link; the *clipping* is the part that
     can actually be felt, so both are modelled and you can make them harsher
     (``adc_bits=8``) to see what a cheaper radio does to you.

Ordering matches the physics: TX -> multipath -> (per-frame AGC) -> LO/IQ/CFO
-> thermal noise -> fractional timing (receiver-side: signal *and* noise pass
the interpolator together, exactly as they do in a real sampler) -> ADC -> (the
RX front end's own AGC, in ``channel_and_sync_field``).

Two decisions here are judgement calls, and they are called out because a
field model you cannot audit is worse than no field model at all:

  * **flat fading is removed before the noise is added.**  The receiver's AGC
    does exactly that in hardware (it amplifies signal *and* noise together, so
    a flat fade costs no SNR), and it keeps ``apply_channel``'s noise contract
    valid: the SNR the trainer asks for is the SNR the converter sees.  What
    survives normalisation is the *selective* part -- the notches and the ISI
    -- which is also the only part an AGC cannot fix.
  * **tap gains are redrawn independently per frame and held constant inside a
    frame** (with a per-path Doppler phase ramp across it).  Frames are 2.34 ms
    and are generated independently anyway, so consecutive frames are fully
    decorrelated: slightly harsher than a slowly varying real channel, and a
    lot cheaper than a Jakes generator.

Everything is opt-in and the presets are numbers a field radio can actually
achieve.  The v4 pipeline and its published metrics are untouched:

    python lpi_train.py --field
    python lpi_train.py --field --field-preset vehicle
"""
from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from lpi_core import LPIConfig, apply_channel, receiver_front_end, unit_power

TWO_PI = 2.0 * math.pi

#: One 24-frame AES/RS burst at the shipped 245.76 kS/s = 13824 samples =
#: 56.2 ms.  SFO accumulates over the *burst*, not over a single frame -- that
#: is the whole point of modelling it separately from the fractional timing.
DEFAULT_BURST_S = 13824.0 / 245_760.0

#: Every field parameter in one place.  ``PRESETS`` overrides on top of this.
#: Nothing here is exotic: each is a number a $300 SDR pair can hit.
DEFAULT_FIELD: Dict[str, Any] = {
    "enabled": True,
    # samples; 1 sample at 245.76 kS/s = 4.07 us = 1.22 km of extra path length
    "path_delays": (0, 1, 3),
    "path_db": (0.0, -6.0, -12.0),   # power delay profile, relative to tap 0
    "k_db": 6.0,                     # Rician K of tap 0 (0 dB = pure Rayleigh = NLOS)
    "doppler_hz": 15.0,              # +-max Doppler per path (~3-5 km/h, a walking team)
    "timing_frac": 0.5,              # +-samples of unsearchable fractional timing error
    "sfo_ppm": 5.0,                  # ADC clock disagreement between the two radios
    "burst_s": DEFAULT_BURST_S,
    "adc_bits": 12,                  # USRP B210
    "clip_headroom_db": 12.0,        # AGC: per-dim RMS -> ADC full scale
}

#: Field-achievable scenarios.  ``{}`` means "the defaults above".
PRESETS: Dict[str, Dict[str, Any]] = {
    # two fixed radios, one reflector: almost flat, no motion
    "static": {"path_delays": (0, 1), "path_db": (0.0, -9.0), "k_db": 10.0,
               "doppler_hz": 0.0, "sfo_ppm": 3.0},
    # the default: an infantry/patrol team on the move at ~3-5 km/h
    "team": {},
    # a mounted link at 60 km/h: 138 Hz Doppler at 2.484 GHz, a cheaper TCXO
    "vehicle": {"path_delays": (0, 2, 6), "path_db": (0.0, -5.0, -10.0),
                "k_db": 3.0, "doppler_hz": 140.0, "sfo_ppm": 10.0,
                "clip_headroom_db": 10.0},
    # NLOS: hillsides / urban canyon, reflectors kilometres out, pure Rayleigh
    "nlos": {"path_delays": (0, 3, 8), "path_db": (0.0, -4.0, -9.0),
             "k_db": 0.0, "doppler_hz": 40.0, "sfo_ppm": 10.0},
}


def field_preset(name: str) -> Dict[str, Any]:
    """A resolved field config: ``PRESETS[name]`` merged over ``DEFAULT_FIELD``.

    Raises KeyError with the list of known names, because a typo silently
    falling back to "static" would look like a lucky field trial.
    """
    if name not in PRESETS:
        raise KeyError(f"unknown field preset {name!r}; known: "
                       f"{', '.join(sorted(PRESETS))}")
    return {**DEFAULT_FIELD, **PRESETS[name]}


def describe_field(f: Mapping[str, Any]) -> str:
    """One human line for the trainer's log / run manifest."""
    d = "x".join(str(int(s)) for s in f["path_delays"])
    pdb = "/".join(f"{float(v):g}" for v in f["path_db"])
    return (f"delays {d} samp | PDP {pdb} dB | K {float(f['k_db']):g} dB | "
            f"doppler +-{float(f['doppler_hz']):g} Hz | "
            f"timing +-{float(f['timing_frac']):g} samp "
            f"+SFO {float(f['sfo_ppm']):g} ppm/{float(f['burst_s'])*1e3:.0f} ms | "
            f"adc {int(f['adc_bits'])} bit @ {float(f['clip_headroom_db']):g} dB headroom")


# =========================================================================
# The three field impairments.  Everything stays in real arithmetic (I/Q
# split) -- torch 2.2 MPS has no complex tensors to speak of, and the rest of
# lpi_core already decomposes atan2/CFO for exactly that reason.
# =========================================================================
def _multipath(x: torch.Tensor, cfg: LPIConfig, f: Mapping[str, Any]) -> torch.Tensor:
    """Tapped-delay-line channel with per-path Doppler phase ramps.

    Tap 0 is Rician with K = ``f["k_db"]`` (a line-of-sight component along I);
    the rest are Rayleigh with the power delay profile ``f["path_db"]``.  Each
    path p gets a Doppler shift drawn uniform in +-``doppler_hz`` and applied as
    a phase ramp across the frame, so differential motion between paths is
    time-varying selective fading rather than a second copy of CFO.

    Output is ``unit_power``-normalised: that is the per-frame AGC, and it is
    what keeps apply_channel's "input is unit power per real dimension" noise
    contract true (see the module docstring).  The *selective* damage -- the
    notches and the ISI -- survives that normalisation, which is the damage a
    real receiver cannot AGC away.
    """
    B, _, T = x.shape
    dev, dt = x.device, x.dtype
    delays = [int(d) for d in f["path_delays"]]
    pdb = [float(v) for v in f["path_db"]]
    if len(delays) != len(pdb):
        raise ValueError(f"path_delays ({len(delays)}) and path_db ({len(pdb)}) "
                         f"must have the same length")
    P = len(delays)
    sigma = torch.tensor([10.0 ** (v / 20.0) for v in pdb], device=dev, dtype=dt)
    # CN(0,1) = (n1 + j n2)/sqrt(2); tap 0 adds a deterministic LOS along I.
    n_re = torch.randn(B, P, device=dev, dtype=dt) / math.sqrt(2.0)
    n_im = torch.randn(B, P, device=dev, dtype=dt) / math.sqrt(2.0)
    k_lin = 10.0 ** (float(f["k_db"]) / 10.0)
    los = math.sqrt(k_lin / (k_lin + 1.0))
    scat = math.sqrt(1.0 / (k_lin + 1.0))
    g_re = sigma * (los + scat * n_re)
    g_im = sigma * (scat * n_im)

    # Doppler: per-path phase ramp across the frame (uniform in +-f_d).
    fd = (torch.rand(B, P, device=dev, dtype=dt) * 2.0 - 1.0) * float(f["doppler_hz"])
    n = torch.arange(T, device=dev, dtype=dt) / float(cfg.fs)
    ang = TWO_PI * fd.unsqueeze(-1) * n.view(1, 1, T)          # (B,P,T)
    ca, sa = torch.cos(ang), torch.sin(ang)
    gr, gi = g_re.unsqueeze(-1), g_im.unsqueeze(-1)
    hr = gr * ca - gi * sa                                     # h[n] = g*e^{j2 pi f n/fs}
    hi = gr * sa + gi * ca

    xi, xq = x[:, :1], x[:, 1:]
    yi, yq = torch.zeros_like(xi), torch.zeros_like(xq)
    for p, d in enumerate(delays):
        if d < 0 or d >= T:
            raise ValueError(f"path delay {d} outside the frame ({T} samples)")
        # (I + jQ) * (hr + j hi)
        pi_ = xi * hr[:, p:p + 1] - xq * hi[:, p:p + 1]
        pq_ = xi * hi[:, p:p + 1] + xq * hr[:, p:p + 1]
        if d == 0:
            yi = yi + pi_
            yq = yq + pq_
        else:
            yi = yi + F.pad(pi_, (d, 0))[..., :T]              # y[n] += h * x[n-d]
            yq = yq + F.pad(pq_, (d, 0))[..., :T]
    return unit_power(torch.cat([yi, yq], dim=1))


def _timing(x: torch.Tensor, cfg: LPIConfig, f: Mapping[str, Any]) -> torch.Tensor:
    """Fractional-sample timing error, including the SFO drift over a burst.

    ``tau`` is drawn uniform in +-(timing_frac + sfo_walk) samples, clamped to
    +-0.99 so a linear interpolation always has two real taps.  The search in
    ``sync_and_correct`` is integer-sample, so *this entire offset is
    invisible to acquisition*: it is the residual the learned front end and the
    ZF detector have to absorb.
    """
    B, C, T = x.shape
    dev, dt = x.device, x.dtype
    # SFO: ppm of clock disagreement, accumulated over a whole burst.
    sfo_walk = float(f["sfo_ppm"]) * 1e-6 * float(cfg.fs) * float(f["burst_s"])
    tau = ((torch.rand(B, device=dev, dtype=dt) * 2.0 - 1.0)
           * (float(f["timing_frac"]) + sfo_walk))
    tau = tau.clamp(-0.99, 0.99).view(B, 1, 1)
    idx = torch.arange(T, device=dev, dtype=dt).view(1, 1, T) - tau   # (B,1,T)
    flo = torch.floor(idx)
    frac = (idx - flo).expand(B, C, T)
    # +1/+2: one sample of zero pad either side, so idx in [-0.99, T-0.01] is
    # always inside the padded tensor (indices 0 .. T+1 of a T+2 tensor).
    i0 = (flo.long() + 1).expand(B, C, T).contiguous()
    i1 = (flo.long() + 2).expand(B, C, T).contiguous()
    pad = torch.cat([x.new_zeros(B, C, 1), x, x.new_zeros(B, C, 1)], dim=2)
    return torch.gather(pad, 2, i0) * (1.0 - frac) + torch.gather(pad, 2, i1) * frac


def _adc(x: torch.Tensor, f: Mapping[str, Any]) -> torch.Tensor:
    """Clip to AGC headroom, then quantise to ``adc_bits``.

    ``unit_power`` gives per-dim RMS = 1, so full scale sits
    ``clip_headroom_db`` above that.  At 12 bits the step is ~4e-3 of an LSB of
    RMS -- a ~72 dBc quantisation floor, invisible next to a -2..12 dB SNR
    link, which is worth stating plainly: this term buys honesty, not drama.
    The *clipping* is what bites, and it is what ``adc_bits=8`` or a tighter
    headroom will show you.
    """
    full = 10.0 ** (float(f["clip_headroom_db"]) / 20.0)
    levels = float(2 ** (max(1, int(f["adc_bits"])) - 1))
    step = full / levels
    return torch.round(x.clamp(-full, full) / step) * step


def apply_field_channel(x: torch.Tensor, cfg: LPIConfig, snr_db=None,
                        impairments: bool = True, *,
                        field: Optional[Mapping[str, Any]] = None
                        ) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Drop-in ``apply_channel`` plus the field impairments listed above.

    Returns ``(y, p)`` where ``p`` carries ``apply_channel``'s drawn parameters
    (snr_db/cfo/phi/dc/shift) **plus** the field ones, so a caller can model
    what the synchroniser would estimate.  ``p["field"]`` is True when the field
    path ran at all.

    With ``field={"enabled": False}`` (or ``impairments=False``) this is
    bit-identical to ``apply_channel``: the field path draws nothing extra, so
    a test can assert exactly that.
    """
    f = dict(DEFAULT_FIELD) if field is None else {**DEFAULT_FIELD, **dict(field)}
    if not (impairments and f.get("enabled", True)):
        return apply_channel(x, cfg, snr_db, impairments)

    y = _multipath(x, cfg, f)
    y, p = apply_channel(y, cfg, snr_db, impairments)
    # timing after the noise: sampling is a *receiver* operation, so the
    # interpolator sees signal and thermal noise together.  Interpolating the
    # signal alone (noise added after) would attenuate only the signal's high
    # band and fake an SNR loss no real sampler has.
    y = _timing(y, cfg, f)
    y = _adc(y, f)
    p = dict(p)
    p.update(field=True,
             path_delays=tuple(int(d) for d in f["path_delays"]),
             doppler_hz=float(f["doppler_hz"]),
             adc_bits=int(f["adc_bits"]))
    return y, p


def channel_and_sync_field(x: torch.Tensor, cfg: LPIConfig, snr_db=None,
                           impairments: bool = True, *,
                           field: Optional[Mapping[str, Any]] = None
                           ) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """The field twin of ``lpi_core.channel_and_sync`` (what the trainer calls).

    Same contract: TX->RX front end, plus ``receiver_front_end``'s AGC/phase
    estimate when impairments are on.  The field impairments land *before* that
    AGC, exactly as they land before the real radio's.
    """
    y, p = apply_field_channel(x, cfg, snr_db, impairments, field=field)
    if impairments:
        y = receiver_front_end(y, p, cfg)
    else:
        y = unit_power(y)
    return y, p


# =========================================================================
# The numpy twin, for link_ber
# =========================================================================
def apply_field_np(sig: np.ndarray, cfg: LPIConfig, f: Mapping[str, Any],
                   rng: Optional[np.random.Generator] = None) -> np.ndarray:
    """Multipath + Doppler + fractional timing on a *burst*, in numpy.

    ``link_ber`` builds one complex64 burst (every frame concatenated, plus the
    guard pad), runs it through CFO/DC/noise in numpy and then calls
    ``sync_and_correct`` -- the actual field path, and the number the gate
    reads.  If training used the field channel and this did not, the gate would
    score a clean bench and call it a field pass.  So both paths read the same
    ``field`` dict.

    Same physics as the torch path, one difference forced by the caller: no
    ``unit_power`` here, because ``link_ber`` computes its noise from the
    post-field signal's own std (``cap.std()/snr``), which is the receiver's
    AGC in one line -- flat fading cancels, selectivity and ISI do not.
    """
    rng = np.random.default_rng() if rng is None else rng
    delays = [int(d) for d in f["path_delays"]]
    pdb = [float(v) for v in f["path_db"]]
    n = np.arange(sig.size) / float(cfg.fs)
    out = np.zeros_like(sig, dtype=np.complex128)
    k_lin = 10.0 ** (float(f["k_db"]) / 10.0)
    los = math.sqrt(k_lin / (k_lin + 1.0))
    scat = math.sqrt(1.0 / (k_lin + 1.0))
    for p, d in enumerate(delays):
        sigma = 10.0 ** (pdb[p] / 20.0)
        scatter = (rng.standard_normal() + 1j * rng.standard_normal()) / math.sqrt(2.0)
        h = sigma * ((los + scat * scatter) if p == 0 else scatter)
        fd = rng.uniform(-1.0, 1.0) * float(f["doppler_hz"])
        ramp = np.exp(1j * TWO_PI * fd * n)
        contrib = h * ramp * sig
        if d == 0:
            out += contrib
        else:
            out[d:] += contrib[:sig.size - d]      # y[n] += h * x[n-d]

    tau = rng.uniform(-(float(f["timing_frac"]) + float(f["sfo_ppm"]) * 1e-6
                        * float(cfg.fs) * float(f["burst_s"])),
                      float(f["timing_frac"]) + float(f["sfo_ppm"]) * 1e-6
                      * float(cfg.fs) * float(f["burst_s"]))
    tau = float(np.clip(tau, -0.99, 0.99))
    idx = np.arange(sig.size) - tau
    i0 = np.floor(idx).astype(np.int64)
    w = idx - i0
    i0c = np.clip(i0, -1, sig.size - 1)
    i1c = np.clip(i0 + 1, 0, sig.size)
    pad = np.concatenate([np.zeros(1, dtype=np.complex128), out,
                          np.zeros(1, dtype=np.complex128)])   # index 0..T+1 with the +1 shift
    return pad[i0c + 1] * (1.0 - w) + pad[i1c + 1] * w
